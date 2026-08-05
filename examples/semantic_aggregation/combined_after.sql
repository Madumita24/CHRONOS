SELECT
    AVG(o.order_total) AS order_total
FROM order_entry_db.order_entry.orders AS o
WHERE o.order_status = 1
