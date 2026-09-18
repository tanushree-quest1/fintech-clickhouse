import clickhouse_connect
client = clickhouse_connect.get_client(host='localhost', port=8123, database='bank_demo', username='demo', password='demo_pass')
print(client.query('''SELECT toString(minute) AS bucket, formatDateTime(minute, '%H:%i') AS minute_str, countMerge(total) AS total, countIfMerge(failed) AS failed, round(100 * (1 - failed / total), 2) AS success_rate, round(avgMerge(avg_latency), 1) AS avg_latency FROM bank_demo.transactions_1m_agg WHERE minute >= now() - INTERVAL 20 MINUTE GROUP BY bucket, minute_str ORDER BY bucket ASC''').named_results())
