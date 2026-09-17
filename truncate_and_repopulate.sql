-- Truncate existing tables for fresh US data start
TRUNCATE TABLE transactions;
TRUNCATE TABLE customers;
TRUNCATE TABLE merchants;

-- Verify tables are empty
SELECT 'transactions' as table_name, count() as row_count FROM transactions
UNION ALL
SELECT 'customers', count() FROM customers
UNION ALL
SELECT 'merchants', count() FROM merchants;
