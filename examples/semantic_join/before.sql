SELECT
    o.order_total AS order_total
FROM order_entry_db.order_entry.orders AS o
LEFT JOIN order_entry_db.analytics.order_history AS h
    ON o.order_total = h.order_total
