# Phase 1.4 Field-Lineage Debug Graph

This is an engineering artifact, not a frontend or impact view. Every edge
below comes from a retained DataHub fine-grained mapping group.

## Depth view

```text
depth 0  postgres orders.order_total
  depth 1  S3 orders.order_total
    depth 2  Snowflake ORDER_ENTRY.ORDERS.order_total
      depth 3  dbt source orders.order_total
        depth 4  dbt model order_details.order_total
      depth 3  Snowflake ANALYTICS.ORDER_DETAILS.order_total
        depth 4  dbt order_history.order_total
        depth 4  Looker view order_details.order_total
          depth 5  Looker Explore order_details.order_total
        depth 4  Power BI Customer Analytics.ORDER_TOTAL
        depth 4  Power BI Essential KPI.ORDER_TOTAL
        depth 4  Power BI Essential KPI.Total Revenue
        depth 4  Power BI Geographic Measures.ORDER_TOTAL
        depth 4  Power BI ORDER_DETAILS.ORDER_TOTAL
        depth 4  Power BI Product Performance.ORDER_TOTAL
        depth 4  Power BI Time Intelligence.ORDER_TOTAL
        depth 4  Snowflake ORDER_DETAILS_REPLICA.order_total
        depth 4  Snowflake ORDER_HISTORY.order_total
        depth 4  Tableau custom SQL A.AVERAGE_ORDER_VALUE
          depth 5  Tableau embedded A.AVERAGE_ORDER_VALUE
        depth 4  Tableau custom SQL A.TOTAL_REVENUE
          depth 5  Tableau embedded A.TOTAL_REVENUE
        depth 4  Tableau custom SQL B.AVERAGE_ORDER_VALUE
          depth 5  Tableau embedded B.AVERAGE_ORDER_VALUE
        depth 4  Tableau custom SQL B.TOTAL_REVENUE
          depth 5  Tableau embedded B.TOTAL_REVENUE
```

The depth view shows one shortest-tree placement. The graph is a DAG with
additional paths: dbt model `order_details.order_total` also feeds Snowflake
`ANALYTICS.ORDER_DETAILS.order_total`, and dbt `order_history.order_total`
also feeds Snowflake `ORDER_HISTORY.order_total`.

## Explicit endpoint edges

`aspect[index]` identifies the retained source group. `unknown` means the
group proved dependency but supplied no transform semantics.

| # | Upstream field | Downstream field | Classification | Group evidence |
|---:|---|---|---|---|
| 1 | PostgreSQL `orders.order_total` | S3 `orders.order_total` | unknown | Spark export job `dataJobInputOutput[5]`, confidence 0.5 |
| 2 | S3 `orders.order_total` | Snowflake source `orders.order_total` | unknown | Spark import job `dataJobInputOutput[5]`, confidence 0.5 |
| 3 | Snowflake source `orders.order_total` | dbt source `orders.order_total` | unknown | dbt source `upstreamLineage[5]`, confidence 1.0 |
| 4 | Snowflake source `orders.order_total` | Snowflake `ANALYTICS.ORDER_DETAILS.order_total` | direct | `upstreamLineage[40]`, operation `NONE`, confidence 1.0 |
| 5 | dbt source `orders.order_total` | dbt model `order_details.order_total` | unknown | `upstreamLineage[4]`, confidence 0.9 |
| 6 | dbt model `order_details.order_total` | Snowflake `ANALYTICS.ORDER_DETAILS.order_total` | direct | `upstreamLineage[41]`, operation `NONE`, confidence 1.0 |
| 7 | Snowflake `ORDER_DETAILS.order_total` | dbt `order_history.order_total` | unknown | `upstreamLineage[3]`, confidence 0.9 |
| 8 | dbt `order_history.order_total` | Snowflake `ORDER_HISTORY.order_total` | direct | `upstreamLineage[4]`, operation `NONE`, confidence 1.0 |
| 9 | Snowflake `ORDER_DETAILS.order_total` | Looker view `order_total` | unknown | `upstreamLineage[30]`, confidence 1.0 |
| 10 | Looker view `order_total` | Looker Explore `order_details.order_total` | unknown | `upstreamLineage[30]`, confidence 1.0 |
| 11 | Snowflake `ORDER_DETAILS.order_total` | Power BI Customer Analytics `ORDER_TOTAL` | unknown | `upstreamLineage[4]`, confidence 1.0 |
| 12 | Snowflake `ORDER_DETAILS.order_total` | Power BI Essential KPI `ORDER_TOTAL` | unknown | `upstreamLineage[4]`, confidence 1.0 |
| 13 | Snowflake `ORDER_DETAILS.order_total` | Power BI Essential KPI `Total Revenue` | unknown | `upstreamLineage[57]`, confidence 1.0 |
| 14 | Snowflake `ORDER_DETAILS.order_total` | Power BI Geographic Measures `ORDER_TOTAL` | unknown | `upstreamLineage[4]`, confidence 1.0 |
| 15 | Snowflake `ORDER_DETAILS.order_total` | Power BI `ORDER_DETAILS.ORDER_TOTAL` | unknown | `upstreamLineage[4]`, confidence 1.0 |
| 16 | Snowflake `ORDER_DETAILS.order_total` | Power BI Product Performance `ORDER_TOTAL` | unknown | `upstreamLineage[4]`, confidence 1.0 |
| 17 | Snowflake `ORDER_DETAILS.order_total` | Power BI Time Intelligence `ORDER_TOTAL` | unknown | `upstreamLineage[4]`, confidence 1.0 |
| 18 | Snowflake `ORDER_DETAILS.order_total` | Snowflake replica `order_total` | direct | `upstreamLineage[4]`, `COPY...`, confidence 0.9 |
| 19 | Snowflake `ORDER_DETAILS.order_total` | Snowflake `ORDER_HISTORY.order_total` | direct | `upstreamLineage[3]` and `[5]`, operation `NONE`, confidence 1.0 and 0.4 |
| 20 | Snowflake `ORDER_DETAILS.order_total` | Tableau custom SQL A `AVERAGE_ORDER_VALUE` | unknown | `upstreamLineage[3]`, confidence 1.0 |
| 21 | Snowflake `ORDER_DETAILS.order_total` | Tableau custom SQL A `TOTAL_REVENUE` | unknown | `upstreamLineage[2]`, confidence 1.0 |
| 22 | Snowflake `ORDER_DETAILS.order_total` | Tableau custom SQL B `AVERAGE_ORDER_VALUE` | unknown | `upstreamLineage[3]`, confidence 1.0 |
| 23 | Snowflake `ORDER_DETAILS.order_total` | Tableau custom SQL B `TOTAL_REVENUE` | unknown | `upstreamLineage[2]`, confidence 1.0 |
| 24 | Tableau custom SQL A `AVERAGE_ORDER_VALUE` | Tableau embedded A `AVERAGE_ORDER_VALUE` | unknown | `upstreamLineage[0]`, confidence 1.0 |
| 25 | Tableau custom SQL A `TOTAL_REVENUE` | Tableau embedded A `TOTAL_REVENUE` | unknown | `upstreamLineage[3]`, confidence 1.0 |
| 26 | Tableau custom SQL B `AVERAGE_ORDER_VALUE` | Tableau embedded B `AVERAGE_ORDER_VALUE` | unknown | `upstreamLineage[1]`, confidence 1.0 |
| 27 | Tableau custom SQL B `TOTAL_REVENUE` | Tableau embedded B `TOTAL_REVENUE` | unknown | `upstreamLineage[4]`, confidence 1.0 |

The 27 endpoint edges retain 28 group IDs because edge 19 has two independent
mapping groups. No cycle or ambiguous many-to-many group was observed.
