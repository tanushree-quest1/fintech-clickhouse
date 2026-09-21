"""
Gradient-boosted anomaly detector for the Banking Control Tower demo.

Trains a LightGBM binary classifier on labeled transactions from ClickHouse
(`is_synthetic_incident` = 1 marks the Card/California/E-commerce/Gateway Y
incident slice). The model learns the performance fingerprint of the injected
incident so it can flag similar conditions in live traffic.

Only features observable before an authorization decision are used, so the
model does not peek at `authorization_status` / `response_code` /
`settlement_status` (those are the delays/downtime we want to predict).

Usage:
    pip install lightgbm clickhouse-connect numpy pandas
    python ml_anomaly.py --train
    python ml_anomaly.py --predict '{"gateway":"Gateway Y","region":"California",...}'

Artifacts are written to the --model-dir:
    anomaly_lgbm.txt       LightGBM booster dump (portable)
    anomaly_meta.json      features, category encodings, threshold, metrics
"""

import argparse
import json
import os
import random
from datetime import datetime

import clickhouse_connect
import lightgbm as lgb
import numpy as np
import pandas as pd

from backend.langfuse_observability import langfuse_observer

TARGET = "label"

CATEGORICAL_FEATURES = [
    "bank", "payment_rail", "region", "merchant_category", "gateway",
    "payment_method",
]

NUMERIC_FEATURES = [
    "amount", "latency_ms", "fraud_score", "hour", "dow",
]

FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES

FEATURE_COLUMNS = [
    "bank", "payment_rail", "region", "merchant_category", "gateway",
    "payment_method", "amount", "latency_ms", "fraud_score",
]

SELECT_SQL = """
SELECT
    bank, payment_rail, region, merchant_category, gateway, payment_method,
    amount, latency_ms, fraud_score,
    toHour(event_time) AS hour,
    toDayOfWeek(event_time) AS dow,
    is_synthetic_incident AS label
FROM {schema}.transactions
"""


def _connect(args):
    return clickhouse_connect.get_client(
        host=args.host, port=args.port, database=args.database,
        username=args.user, password=args.password,
    )


def load_training_data(args):
    """Pull labeled positives plus a capped random sample of negatives."""
    where = []
    params = {}
    if args.hours_back:
        where.append("event_time >= now() - INTERVAL %(hours)s HOUR")
        params["hours"] = args.hours_back

    client = _connect(args)
    sql = SELECT_SQL.format(schema=args.database)

    print(f"Loading up to {args.max_negatives:,} labeled negatives...")
    neg_sql = sql + " WHERE " + " AND ".join([*where, "is_synthetic_incident = 0"])
    neg_sql += " ORDER BY rand() LIMIT %(limit)s"
    params_neg = {**params, "limit": args.max_negatives}
    neg_rows = client.query(neg_sql, parameters=params_neg).result_rows

    print("Loading all labeled positives (incident rows)...")
    pos_sql = sql + " WHERE " + " AND ".join([*where, "is_synthetic_incident = 1"])
    pos_rows = client.query(pos_sql, parameters=params).result_rows

    if len(pos_rows) == 0:
        raise SystemExit(
            "No is_synthetic_incident = 1 rows found in ClickHouse.\n"
            "Run the live incident first (POST /incident/start, let the 30s ramp "
            "complete, then /incident/stop) so the producer stamps labeled "
            "incident rows, then re-run --train."
        )

    columns = FEATURE_COLUMNS + ["hour", "dow", TARGET]
    df = pd.DataFrame(list(pos_rows) + list(neg_rows), columns=columns)
    print(f"Loaded {len(df):,} rows ({len(pos_rows):,} incident / {len(neg_rows):,} baseline)")
    return df


def build_encoders(df):
    """Map each categorical value to a stable integer (0 reserved = unknown)."""
    encoders = {}
    for col in CATEGORICAL_FEATURES:
        values = sorted(str(v) for v in df[col].unique())
        encoders[col] = {v: i + 1 for i, v in enumerate(values)}
    return encoders


def encode_features(df, encoders):
    out = pd.DataFrame(index=df.index)
    for col in CATEGORICAL_FEATURES:
        mapping = encoders[col]
        out[col] = df[col].map(lambda v: mapping.get(str(v), 0)).astype(np.int32)
    for col in NUMERIC_FEATURES:
        out[col] = df[col].astype(np.float64)
    return out


def stratified_split(df, val_frac: float = 0.2, seed: int = 42):
    rng = random.Random(seed)
    pos_idx = df.index[df[TARGET] == 1].tolist()
    neg_idx = df.index[df[TARGET] == 0].tolist()
    rng.shuffle(pos_idx)
    rng.shuffle(neg_idx)

    n_val_pos = max(1, int(len(pos_idx) * val_frac))
    n_val_neg = max(1, int(len(neg_idx) * val_frac))
    val_idx = pos_idx[:n_val_pos] + neg_idx[:n_val_neg]
    train_idx = list(set(df.index) - set(val_idx))

    print(f"Train: {len(train_idx):,} rows | Val: {len(val_idx):,} rows")
    return df.loc[train_idx], df.loc[val_idx]


def best_threshold(y_true, y_pred, min_precision: float = 0.80):
    """Highest-F1 threshold that keeps precision at or above min_precision."""
    order = np.argsort(-y_pred)
    y_sorted = np.asarray(y_true)[order]
    p_sorted = y_pred[order]
    tp = 0
    fp = 0
    n_pos = int(np.sum(y_sorted))
    n_neg = len(y_sorted) - n_pos
    best = (0.5, 0.0, 0.0)
    for i, label in enumerate(y_sorted):
        if label == 1:
            tp += 1
        else:
            fp += 1
        if tp + fp < 10 or tp == 0:
            continue
        precision = tp / (tp + fp)
        recall = tp / n_pos
        if precision >= min_precision:
            f1 = 2 * precision * recall / (precision + recall)
            if f1 > best[1]:
                best = (p_sorted[i], f1, precision)
    if best[1] > 0:
        return best
    return (0.5, 0.0, 0.0)


def roc_auc(y_true, y_pred):
    order = np.argsort(y_pred)
    ranks = np.empty(len(y_true), dtype=np.float64)
    ranks[order] = np.arange(1, len(y_true) + 1)
    n_pos = y_true.sum()
    n_neg = len(y_true) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    return (ranks[y_true == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def train(args):
    with langfuse_observer.span(
        "train-incident-anomaly-model",
        {"model_type": "lightgbm", "hours_back": args.hours_back, "max_negatives": args.max_negatives},
    ) as record_output:
        df = load_training_data(args)
        encoders = build_encoders(df)
        X = encode_features(df, encoders)
        y = df[TARGET].to_numpy()

        train_df, val_df = stratified_split(df, seed=args.seed)
        X_train = X.loc[train_df.index]
        y_train = train_df[TARGET].to_numpy()
        X_val = X.loc[val_df.index]
        y_val = val_df[TARGET].to_numpy()

        n_pos = int(y_train.sum())
        n_neg = len(y_train) - n_pos
        scale_pos_weight = min(max(1, n_neg / max(1, n_pos)), 60.0)

        params = {
        "objective": "binary",
        "metric": "auc",
        "boosting_type": "gbdt",
        "num_leaves": 63,
        "min_child_samples": 50,
        "learning_rate": 0.05,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 1,
        "lambda_l2": 1.0,
        "scale_pos_weight": scale_pos_weight,
        "seed": args.seed,
        "verbosity": -1,
        }

        lgb_train = lgb.Dataset(X_train, label=y_train,
                                categorical_feature=CATEGORICAL_FEATURES)
        lgb_val = lgb.Dataset(X_val, label=y_val, reference=lgb_train)

        print("Training LightGBM (up to 800 rounds, early stopping)...")
        booster = lgb.train(
        params, lgb_train, num_boost_round=800,
        valid_sets=[lgb_val],
        callbacks=[lgb.early_stopping(100), lgb.log_evaluation(100)],
        )

        y_pred_val = booster.predict(X_val, num_iteration=booster.best_iteration)
        auc = roc_auc(y_val, y_pred_val)
        thr, f1, precision = best_threshold(y_val, y_pred_val)
        recall = float(((y_pred_val >= thr) & (y_val == 1)).sum()) / max(1, int(y_val.sum()))
        print(f"\nValidation AUC: {auc:.4f}")
        print(f"Detection threshold (precision>=0.80): {thr:.4f} | F1 {f1:.4f} | "
              f"precision {precision:.4f} | recall {recall:.4f}")

        importances = sorted(
        zip(FEATURES, booster.feature_importance("gain")),
        key=lambda t: -t[1],
        )
        print("\nFeature importance (gain):")
        for name, gain in importances:
            print(f"  {name:<18} {gain:,.0f}")

        os.makedirs(args.model_dir, exist_ok=True)
        booster_path = os.path.join(args.model_dir, "anomaly_lgbm.txt")
        meta_path = os.path.join(args.model_dir, "anomaly_meta.json")
        booster.save_model(booster_path, num_iteration=booster.best_iteration)

        meta = {
        "trainer": "ml_anomaly.py",
        "trained_at": datetime.utcnow().isoformat(),
        "source": "clickhouse",
        "database": args.database,
        "hours_back": args.hours_back,
        "n_rows": int(len(df)),
        "n_positives": int((df[TARGET] == 1).sum()),
        "n_negatives": int((df[TARGET] == 0).sum()),
        "best_iteration": booster.best_iteration,
        "auc": round(auc, 4),
        "threshold": round(thr, 4),
        "val_f1": round(f1, 4),
        "val_precision": round(precision, 4),
        "val_recall": round(recall, 4),
        "features": {
            "categorical": CATEGORICAL_FEATURES,
            "numeric": NUMERIC_FEATURES,
        },
        "categorical_encoders": encoders,
        "feature_importance_gain": {
            name: round(float(gain), 2) for name, gain in importances
        },
        }
        with open(meta_path, "w") as fh:
            json.dump(meta, fh, indent=2)

        record_output({"auc": round(auc, 4), "f1": round(f1, 4), "precision": round(precision, 4), "recall": round(recall, 4), "training_rows": len(df)})
        print(f"\nSaved model -> {booster_path}")
        print(f"Saved meta  -> {meta_path}")


def predict(args):
    with open(args.model_dir + "/anomaly_meta.json") as fh:
        meta = json.load(fh)
    booster = lgb.Booster(model_file=args.model_dir + "/anomaly_lgbm.txt")

    events = json.loads(args.predict)
    if isinstance(events, dict):
        events = [events]

    rows = []
    for ev in events:
        row = {feat: ev.get(feat) for feat in FEATURE_COLUMNS}
        row["hour"] = ev.get("hour", 12)
        row["dow"] = ev.get("dow", 1)
        rows.append(row)
    raw = pd.DataFrame(rows)

    encoders = meta["categorical_encoders"]
    X = pd.DataFrame(index=raw.index)
    for col in CATEGORICAL_FEATURES:
        mapping = encoders[col]
        X[col] = raw[col].map(lambda v: mapping.get(str(v), 0)).astype(np.int32)
    for col in NUMERIC_FEATURES:
        X[col] = raw[col].astype(np.float64)

    probs = booster.predict(X)
    threshold = meta["threshold"]
    for ev, p in zip(events, probs):
        level = "ANOMALY" if p >= threshold else "NORMAL"
        print(f"{level:8s} p= {p:.4f}  gateway={ev.get('gateway')} "
              f"region={ev.get('region')} category={ev.get('merchant_category')} "
              f"rail={ev.get('payment_rail')} latency_ms={ev.get('latency_ms')}")


def main():
    parser = argparse.ArgumentParser(description="Gradient-boosted anomaly detector")
    parser.add_argument("--train", action="store_true", help="Train and save the model")
    parser.add_argument("--predict", metavar="JSON", help="Score one or more events (list or single dict)")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8123)
    parser.add_argument("--database", default="bank_demo")
    parser.add_argument("--user", default="demo")
    parser.add_argument("--password", default="demo_pass")
    parser.add_argument("--max-negatives", type=int, default=400_000,
                        help="Cap on baseline rows sampled for training")
    parser.add_argument("--hours-back", type=int, default=0,
                        help="Only train on the last N hours (0 = all history)")
    parser.add_argument("--model-dir", default="models")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.predict:
        predict(args)
    elif args.train:
        train(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
