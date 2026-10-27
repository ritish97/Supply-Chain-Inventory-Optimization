Live demo : https://supply-chain-inventory-optimization-ehjdrvhf8es39hj6b3z4fm.streamlit.app/
# Enterprise Supply Chain & Inventory Optimization Intelligence

A full-stack analytics portfolio project demonstrating how **Excel, Python,
SQL, and Power BI** work together to optimize inventory positioning,
forecast demand, and minimize warehouse holding costs and stockout risk —
built on the schema of the **DataCo Smart Supply Chain for Big Data**
dataset.

---

## Executive Summary

Retail and CPG supply chains routinely carry too much of the wrong
inventory and too little of the right inventory at the same time. This
project builds an end-to-end analytics stack — from a spreadsheet-native
EOQ calculator that a planner can hand-edit, through a production-style
Python ETL pipeline, into a PostgreSQL star-schema warehouse, and finally
into a Power BI executive dashboard — to answer three questions every
supply chain leader needs answered continuously:

1. **How much should we order, and when?** (Economic Order Quantity,
   Safety Stock, Reorder Point)
2. **Which suppliers are putting our service levels at risk?** (OTIF %,
   lead time variance, performance tiering)
3. **Where is capital being tied up unnecessarily, and where are we
   exposed to stockouts?** (holding cost vs. stockout cost trade-off,
   warehouse capacity utilization)

## Architecture Overview

```
┌──────────────────┐      ┌───────────────────────┐      ┌────────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│   EXCEL LAYER     │      │    PYTHON LAYER        │      │    SQL LAYER        │      │  POWER BI LAYER   │      │ STREAMLIT LAYER  │
│ (Planner Tool)     │      │  (ETL / Analytics)      │      │ (Data Warehouse)     │      │  (Executive View)  │      │ (Interactive App)│
│                    │      │                         │      │                      │      │                    │      │                  │
│ supply_chain_eoq_  │      │ supply_chain_          │      │ schema_and_          │      │ dashboard_spec.md  │      │ app.py           │
│ calculator.xlsx    │      │ pipeline.py             │─────▶│ queries.sql           │─────▶│ (DAX + layout)      │─────▶│ (.streamlit/     │
│                    │      │                         │      │                      │      │                    │      │  config.toml)    │
│ - EOQ_Calculator   │      │ - Synthetic DataCo-style│      │ - Star schema DDL     │      │ - Control Tower    │      │ - Control Tower  │
│ - Reorder_Point_   │      │   telemetry generator   │      │ - Stockout alerts     │      │   (Page 1)          │      │ - Scorecard      │
│   Model            │      │ - OTIF % / lead time    │      │ - Supplier ranking    │      │ - Supplier          │      │ - EOQ Simulator  │
│ - Holding_vs_       │      │   variance              │      │   (window functions)  │      │   Scorecard         │      │ - Demand Trend   │
│   Stockout_Cost     │      │ - 3-mo moving avg       │      │ - Warehouse capacity  │      │   (Page 2)          │      │ - SQL Explorer   │
│                    │      │   demand forecast        │      │   utilization          │      │                    │      │                  │
│                    │      │ - Safety stock / ROP     │      │                      │      │                    │      │                  │
└──────────────────┘      └───────────────────────┘      └────────────────────┘      └──────────────────┘      └──────────────────┘
     Live formulas               Produces CSVs                 Loads CSVs into            Connects live or
     for planner edits           for downstream use             normalized tables           via CSV import
```

**Data flow:** the Python pipeline generates realistic order telemetry and
writes clean CSVs → those CSVs are loaded into the PostgreSQL star schema
→ Power BI connects to either the warehouse tables or the CSVs directly →
the Excel workbook operates independently as a lightweight, formula-driven
planning tool for spot-checking EOQ/ROP assumptions without needing the
full stack running.

---

## Business Problem Statement

A mid-size multi-category retailer (modeled on the DataCo Smart Supply
Chain dataset's product/order structure) is experiencing two symptoms of
the same underlying problem — **inventory policy is not systematically
tied to actual demand variability or supplier reliability**:

- Warehouses are simultaneously over-stocked on slow-moving SKUs and
  under-stocked on fast-moving ones, inflating holding costs while
  stockout risk remains elevated on high-velocity items.
- Reorder decisions are made on gut feel or static min/max levels that
  don't account for supplier-specific lead time variability.
- There is no single source of truth connecting product-level inventory
  policy (EOQ, safety stock, ROP) to supplier performance (OTIF %, lead
  time deviation) to warehouse-level financial impact (holding cost,
  capacity utilization).

## Key Recommendations Derived from the Analysis

1. **Tier suppliers and renegotiate or re-source the bottom tier.** The
   supplier scorecard consistently separates suppliers into A/B/C/D
   performance tiers by OTIF %; category-level lead time deviation
   rankings (via the SQL `RANK() OVER (PARTITION BY category ...)` query)
   pinpoint exactly which supplier is the worst performer *within each
   product category* — the right unit of comparison, since a supplier
   that's average overall may be the worst-in-class for a specific
   category the business depends on.
2. **Move from static reorder levels to statistically-derived Safety
   Stock and ROP.** The pipeline calculates safety stock using both a
   deterministic max/avg method and a statistical (demand-variability ×
   √lead-time) method side by side — the statistical method should
   become the standing policy, refreshed on each pipeline run, rather
   than a once-a-year manual estimate.
3. **Prioritize replenishment by financial exposure, not just unit
   count.** The Stockout Alert Query surfaces `estimated_reorder_value`
   alongside the stockout flag, so planners can triage the SKUs with the
   largest dollar exposure first, not simply the ones furthest below
   their reorder point.
4. **Right-size holding cost against actual stockout risk, per SKU.** The
   Excel `Holding_vs_Stockout_Cost` tab flags SKUs where the carrying
   cost of current inventory materially exceeds the expected cost of a
   stockout (over-invested, capital to release) and vice versa
   (under-protected, safety stock candidates) — this trade-off should be
   reviewed quarterly per category.
5. **Monitor warehouse capacity utilization against an 85% threshold.**
   The SQL warehouse capacity query flags any DC trending above 85%
   utilization as needing either demand rebalancing across warehouses or
   a capacity expansion conversation before it becomes a fulfillment risk.

---

## Repository Structure

```
.
├── .streamlit/
│   └── config.toml                   # Custom enterprise theme configuration
├── app.py                            # Deliverable 6: Streamlit interactive frontend application
├── generate_excel_model.py           # Deliverable 1: builds the Excel EOQ/ROP/cost workbook
├── supply_chain_eoq_calculator.xlsx  # Output of generate_excel_model.py (generated, not tracked)
├── supply_chain_pipeline.py          # Deliverable 2: synthetic data + demand/supplier analytics
├── processed_inventory_metrics.csv   # Output: SKU-level safety stock / ROP / stockout flags
├── supplier_scorecard.csv            # Output: supplier OTIF % / lead time variance / tiering
├── demand_forecast_by_category.csv   # Output: 3-month moving average demand forecast
├── raw_order_telemetry.csv           # Output: synthetic DataCo-style order-line telemetry
├── warehouse_stock_snapshot.csv      # Output: synthetic point-in-time stock snapshot
├── schema_and_queries.sql            # Deliverable 3: star schema DDL + 3 analytical queries
├── dashboard_spec.md                 # Deliverable 4: Power BI schema, DAX measures, layout blueprint
└── README.md                         # Deliverable 5: this file
```

---

## Step-by-Step Setup & Execution

### Prerequisites

- Python 3.9+
- PostgreSQL 13+ (for the SQL layer)
- Microsoft Excel or LibreOffice Calc (to open the generated workbook)
- Power BI Desktop (optional, to build the dashboard from `dashboard_spec.md`)

### 1. Run the Python demand & supplier pipeline

```bash
pip install pandas numpy
python supply_chain_pipeline.py
```

This generates 15,000 synthetic order-line records and writes five CSV
files to the current directory, including the two primary deliverables:
`processed_inventory_metrics.csv` and `supplier_scorecard.csv`. The
script prints a run summary and sample rows to the console so you can
sanity-check the output without opening the files.

### 2. Build and inspect the Excel EOQ/ROP model

```bash
pip install openpyxl
python generate_excel_model.py
```

This writes `supply_chain_eoq_calculator.xlsx` with three tabs
(`EOQ_Calculator`, `Reorder_Point_Model`, `Holding_vs_Stockout_Cost`), all
driven by live Excel formulas — no hardcoded results. Open the file in
Excel; on first open, Excel will recalculate all formulas automatically.
If you edit any blue input cell (e.g., annual demand or ordering cost),
every downstream formula — including the cross-sheet links in
`Reorder_Point_Model` — updates immediately.

> **Tip:** If you inspect the file with a non-Excel tool (e.g., a Python
> script using `openpyxl`), remember that `openpyxl` writes formulas
> without cached values. Open the file once in Excel/LibreOffice (or run
> it through a headless recalculation utility) before reading calculated
> values programmatically.

### 3. Load and run the SQL data warehouse

```bash
# Create the database
createdb supply_chain_dw

# Build the star schema and run the three analytical queries
psql -d supply_chain_dw -f schema_and_queries.sql
```

`schema_and_queries.sql` will drop and recreate the four tables
(`Fact_Inventory_Orders`, `Dim_Products`, `Dim_Suppliers`,
`Dim_Warehouses`), then execute the three analytical queries in sequence
against whatever data has been loaded. To populate the warehouse with the
synthetic data generated in Step 1:

1. Load `raw_order_telemetry.csv`, `warehouse_stock_snapshot.csv`, and
   `supplier_scorecard.csv` into staging tables (via `\copy` in `psql` or
   any ETL tool of choice).
2. Insert into `Dim_Products`, `Dim_Suppliers`, and `Dim_Warehouses` first
   (dimensions must exist before the fact table, due to foreign key
   constraints).
3. Insert into `Fact_Inventory_Orders`, resolving each natural key
   (`sku_id`, `supplier_id`, `warehouse_code`) to its corresponding
   surrogate key (`product_key`, `supplier_key`, `warehouse_key`) via a
   join against the dimension tables.
4. Re-run just the three query sections (Sections 2-4 of the SQL file) to
   see live stockout alerts, supplier rankings, and warehouse utilization
   against your loaded data.

### 4. Build the Power BI dashboard

Open Power BI Desktop and follow `dashboard_spec.md`:

1. Connect to the PostgreSQL warehouse (**Get Data → PostgreSQL
   database**) or import the CSVs directly (**Get Data → Text/CSV**).
2. Build the star-schema relationships exactly as documented in Section 1
   of the spec.
3. Create the `_Measures` table and paste in the DAX measures from
   Section 2 (OTIF %, Total Holding Cost, Inventory Turnover Ratio,
   Stockout Risk SKU Count, plus the supporting measures).
4. Lay out Page 1 (Executive Inventory Control Tower) and Page 2
   (Supplier Scorecard & Lead Time Analysis) per the visual blueprint in
   Section 3.

### 5. Launch the Streamlit Interactive Frontend Application

```bash
streamlit run app.py
```

The app loads the DataCo order telemetry and star schema into an interactive enterprise control tower configured with corporate theme tokens:
- **Primary Color:** `#0052CC` (Deep Corporate Blue)
- **Background Color:** `#FFFFFF` (Crisp White)
- **Secondary Background:** `#F4F5F7` (Slate Gray)
- **Text Color:** `#172B4D` (Navy/Charcoal)

Features included in the web app:
- **🏢 Executive Control Tower:** Real-time KPI cards (`OTIF %`, `Total Holding Cost`, `Inventory Turnover`, `Stockout Risk SKUs`), interactive Warehouse Capacity visual with 85% utilization threshold warning, and stockout triage table with CSV export.
- **🚚 Supplier Scorecard:** Parity scatter plot ($y = x$) for scheduled vs. actual shipping days, supplier performance tiers (A/B/C/D), OTIF & late delivery rates, and category-level delay rankings.
- **📐 EOQ & Safety Stock Simulator:** Interactive formula engine to simulate Economic Order Quantity, Statistical vs. Deterministic Safety Stock, Reorder Points, and live EOQ cost curve visualizations.
- **📈 Demand Forecasting:** 3-month trailing moving average historical curves and next-month projections across all product categories.
- **🗄️ SQL Data Warehouse Analytics:** In-memory execution of the star schema analytical queries from `schema_and_queries.sql` with a custom SQL query playground.

---

## Methodology Notes

- **EOQ formula:** `EOQ = SQRT((2 × Annual Demand × Ordering Cost) / Holding Cost)`
- **Safety Stock (deterministic method, used in Excel):**
  `Safety Stock = (Max Daily Demand × Max Lead Time) − (Avg Daily Demand × Avg Lead Time)`
- **Safety Stock (statistical method, used in the Python pipeline):**
  `Safety Stock = Z × σ(demand) × √(Avg Lead Time)`, using a 95% service
  level (Z = 1.65). Both methods are computed in the pipeline output for
  transparency and side-by-side comparison.
- **Reorder Point:** `ROP = (Avg Daily Demand × Avg Lead Time) + Safety Stock`
- **OTIF %:** percentage of orders that were both delivered on-time
  (`actual_shipping_days ≤ scheduled_shipping_days`) **and** in full
  (`delivered_in_full = 1`).
- **Synthetic data disclaimer:** all order, supplier, and stock-level data
  in this repository is randomly generated to match the *schema and
  statistical shape* of the DataCo Smart Supply Chain for Big Data
  dataset — it does not contain real transactional data. Replace the
  synthetic generator in `supply_chain_pipeline.py` with a real ERP/WMS
  extract to use this stack in production.

---

## License

This project is provided as a educational reference
implementation.
