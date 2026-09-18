"""
Merchant catalog — loads the `merchants` dimension table once and builds
per-category sampling structures with realistic popularity skew (a few
major merchants take most of the volume, long tail gets little).

This is what makes "top affected merchants" queries return meaningful,
concentrated results instead of every merchant showing 1-2 transactions.

Also guarantees category consistency: once a merchant_id is sampled, its
merchant_category is READ from the catalog, never independently re-rolled.
"""

import numpy as np


class MerchantCatalog:
    def __init__(self, client, zipf_s: float = 1.3):
        """
        zipf_s: skew exponent. Higher = more concentrated in top merchants.
        1.3 gives a noticeably "80/20"-ish distribution without making the
        long tail literally invisible.
        """
        rows = client.query(
            "SELECT merchant_id, merchant_category, gateway, region FROM merchants"
        ).result_rows

        self.by_category = {}   # category -> dict(ids=[], probs=[], gateways=[], regions=[])
        grouped = {}
        for merchant_id, category, gateway, region in rows:
            grouped.setdefault(category, []).append((merchant_id, gateway, region))

        for category, entries in grouped.items():
            n = len(entries)
            # Rank-based Zipf weights: rank 1 (most "popular") gets highest weight.
            # Shuffle first so popularity isn't correlated with merchant_id order.
            rng = np.random.default_rng(abs(hash(category)) % (2**32))
            order = rng.permutation(n)
            ranks = np.arange(1, n + 1)
            weights = 1.0 / np.power(ranks, zipf_s)
            weights = weights / weights.sum()

            ids = np.array([entries[order[i]][0] for i in range(n)])
            gateways = np.array([entries[order[i]][1] for i in range(n)])
            regions = np.array([entries[order[i]][2] for i in range(n)])

            self.by_category[category] = {
                "ids": ids, "probs": weights,
                "gateways": gateways, "regions": regions,
            }

    def sample(self, category: str, rng: np.random.Generator, size: int = None):
        """Returns (merchant_id, merchant_home_gateway, merchant_home_region) for
        `size` samples (or a single tuple if size is None), skewed by popularity."""
        cat = self.by_category[category]
        idx = rng.choice(len(cat["ids"]), size=size, p=cat["probs"])
        return cat["ids"][idx], cat["gateways"][idx], cat["regions"][idx]
