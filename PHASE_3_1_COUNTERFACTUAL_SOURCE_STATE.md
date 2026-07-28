# CHRONOS Phase 3.1 - Counterfactual Source State

## Current and counterfactual source

```text
CERTIFIED CURRENT SOURCE

PostgreSQL orders
Dataset URN:
urn:li:dataset:(urn:li:dataPlatform:postgres,b2fd91.order_entry_db.order_entry.orders,PROD)

15 fields

position 5:
  field_path       = order_total
  field_name       = order_total
  native_type      = DOUBLE PRECISION
  normalized_type  = Number
  nullable         = true
  part_of_key      = false
  schema_field_urn = null

                    FIELD_RENAME
                         |
                         v

COUNTERFACTUAL SOURCE

PostgreSQL orders
Dataset URN:
urn:li:dataset:(urn:li:dataPlatform:postgres,b2fd91.order_entry_db.order_entry.orders,PROD)

15 fields

position 5:
  field_path       = order_amount
  field_name       = order_amount
  native_type      = DOUBLE PRECISION
  normalized_type  = Number
  nullable         = true
  part_of_key      = false
  schema_field_urn = null
```

`order_total` is certified current evidence. `order_amount` is a derived
counterfactual candidate and was not observed in DataHub.

## Field mappings

| Position | Certified current | Counterfactual candidate | Mapping |
|---:|---|---|---|
| 0 | `order_id` | `order_id` | `UNCHANGED` |
| 1 | `order_date` | `order_date` | `UNCHANGED` |
| 2 | `order_mode` | `order_mode` | `UNCHANGED` |
| 3 | `customer_id` | `customer_id` | `UNCHANGED` |
| 4 | `order_status` | `order_status` | `UNCHANGED` |
| 5 | `order_total` | `order_amount` | `RENAMED` |
| 6 | `sales_rep_id` | `sales_rep_id` | `UNCHANGED` |
| 7 | `promotion_id` | `promotion_id` | `UNCHANGED` |
| 8 | `warehouse_id` | `warehouse_id` | `UNCHANGED` |
| 9 | `delivery_type` | `delivery_type` | `UNCHANGED` |
| 10 | `cost_of_delivery` | `cost_of_delivery` | `UNCHANGED` |
| 11 | `wait_till_complete_yn` | `wait_till_complete_yn` | `UNCHANGED` |
| 12 | `billing_address_id` | `billing_address_id` | `UNCHANGED` |
| 13 | `delivery_address_id` | `delivery_address_id` | `UNCHANGED` |
| 14 | `payment_method_code` | `payment_method_code` | `UNCHANGED` |

## Transformation totals

| Measure | Count |
|---|---:|
| Unchanged source fields | 14 |
| Renamed source fields | 1 |
| Added source fields | 0 |
| Deleted source fields | 0 |
| Downstream fields transformed | 0 |
| Lineage edges transformed | 0 |
| Governance records transformed | 0 |

The certified current snapshot is unchanged. This artifact contains only the
counterfactual PostgreSQL source schema; it is not a Future Graph.
