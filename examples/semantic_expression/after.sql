SELECT
    o.order_total * 0.9 AS order_total
FROM order_entry_db.order_entry.orders AS o
