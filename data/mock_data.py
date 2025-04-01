"""Mock data for BigQuery query analysis"""

MOCK_QUERY_DATA = [
    {
        "query_id": "1",
        "query_text": "SELECT * FROM sales_data WHERE date > '2023-01-01'",
        "runtime_ms": 15000,
        "user": "analyst1",
        "timestamp": "2023-03-15T14:25:10",
        "bytes_processed": 250000000
    },
    {
        "query_id": "2",
        "query_text": """
        WITH customer_orders AS (
            SELECT customer_id, COUNT(DISTINCT order_id) as order_count
            FROM orders
            GROUP BY customer_id
        ),
        customer_items AS (
            SELECT customer_id, COUNT(DISTINCT item_id) as item_count
            FROM order_items
            GROUP BY customer_id
        )
        SELECT c.*, co.order_count, ci.item_count
        FROM customers c
        LEFT JOIN customer_orders co ON c.customer_id = co.customer_id
        LEFT JOIN customer_items ci ON c.customer_id = ci.customer_id
        WHERE c.region = 'NORTH'
        """,
        "runtime_ms": 45000,
        "user": "analyst2",
        "timestamp": "2023-03-16T10:15:22",
        "bytes_processed": 750000000
    },
    {
        "query_id": "3",
        "query_text": """
        SELECT 
            date, 
            store_id, 
            SUM(amount) as total_sales,
            COUNT(DISTINCT customer_id) as unique_customers
        FROM sales_data
        WHERE date BETWEEN '2023-01-01' AND '2023-01-31'
        GROUP BY date, store_id
        HAVING SUM(amount) > 1000
        ORDER BY date, total_sales DESC
        """,
        "runtime_ms": 8000,
        "user": "analyst1",
        "timestamp": "2023-03-16T11:30:45",
        "bytes_processed": 120000000
    },
    {
        "query_id": "4",
        "query_text": """
        SELECT 
            t1.*,
            t2.dimension1,
            t2.dimension2
        FROM 
            huge_fact_table t1
        JOIN 
            (SELECT id, dimension1, dimension2 FROM dimension_table WHERE region = 'WEST') t2
        ON 
            t1.dimension_id = t2.id
        WHERE 
            t1.date > '2023-01-01'
        """,
        "runtime_ms": 65000,
        "user": "analyst3",
        "timestamp": "2023-03-17T09:05:18",
        "bytes_processed": 1200000000
    },
    {
        "query_id": "5",
        "query_text": """
        SELECT 
            *
        FROM 
            transactions
        WHERE 
            date = '2023-03-15'
            AND (
                SELECT COUNT(DISTINCT product_id) 
                FROM transaction_items 
                WHERE transaction_id = transactions.id
            ) > 3
        """,
        "runtime_ms": 85000,
        "user": "analyst2",
        "timestamp": "2023-03-17T14:22:33",
        "bytes_processed": 900000000
    }
]