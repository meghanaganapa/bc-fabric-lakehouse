# Pipeline: `pl_bc_daily`

A Fabric data pipeline that runs the notebooks in order.

```
Bronze ─✔─► Silver sales ─✔─► Silver customers orders ─✔─► Gold ─✔─► Quality gate ─✖─► Office 365 email
```

| Activity | Type | Notebook | Settings |
|---|---|---|---|
| Bronze | Notebook | `01_bronze_ingest` | Retry 1, interval 120 s |
| Silver sales | Notebook | `02_silver_sales` | Retry 1, interval 120 s |
| Silver customers orders | Notebook | `03_silver_customers_orders` | Retry 1, interval 120 s |
| Gold | Notebook | `04_gold` | Retry 1, interval 120 s |
| Quality gate | Notebook | `05_quality_gate` | No retry; failure is intentional |
| Office365Email1 | Office 365 Outlook | – | On **failure** of Quality gate: "CCG pipeline failed – check the Monitor hub" |

- Activities are chained **on success** (green), so a failed step stops everything after it.
- The quality gate raises an exception when a check fails, which triggers the **on failure** (red) path to the email.
- Schedule: daily (disabled when not needed, to save capacity).
- On a small capacity, enable **high concurrency for pipelines** and give every notebook activity the same **session tag**, so all notebooks share one Spark session instead of hitting the concurrency limit.
