# Power BI Dashboard Specification
## Enterprise Supply Chain & Inventory Optimization Intelligence

This document specifies the Power BI data model, DAX measures, and page-by-page
visual layout for the Supply Chain & Inventory Optimization dashboard. It is
designed to sit directly on top of the star schema defined in
`schema_and_queries.sql` (Deliverable 3) and the CSV outputs produced by
`supply_chain_pipeline.py` (Deliverable 2).

---

## 1. Data Schema Relationship Map (Star Schema)

Import or DirectQuery the four warehouse tables into Power BI and build the
following **1-to-Many** relationships, all filtering from the "1" side (the
dimension) to the "Many" side (the fact table):

```
                         ┌───────────────────┐
                         │   Dim_Products     │
                         │  (product_key PK)  │
                         └─────────┬──────────┘
                                   │ 1
                                   │
                                   │ *
┌───────────────────┐   1    ┌────┴───────────────────┐   *    1   ┌────────────────────┐
│   Dim_Suppliers    ├────────┤  Fact_Inventory_Orders  ├────────────┤   Dim_Warehouses    │
│ (supplier_key PK)  │        │  (order_line_key PK)    │            │ (warehouse_key PK) │
└────────────────────┘        │  - product_key (FK)     │            └────────────────────┘
                               │  - supplier_key (FK)    │
                               │  - warehouse_key (FK)   │
                               └─────────────┬────────────┘
                                              │ *
                                              │
                                              │ 1
                                    ┌─────────┴─────────┐
                                    │   Dim_Date          │
                                    │ (date_key PK)       │
                                    │ (auto date table or │
                                    │  generated calendar)│
                                    └──────────────────────┘
```

| Relationship | Cardinality | Cross-filter direction | Notes |
|---|---|---|---|
| `Dim_Products[product_key]` → `Fact_Inventory_Orders[product_key]` | 1 : * | Single | Powers category/SKU slicers |
| `Dim_Suppliers[supplier_key]` → `Fact_Inventory_Orders[supplier_key]` | 1 : * | Single | Powers supplier scorecard page |
| `Dim_Warehouses[warehouse_key]` → `Fact_Inventory_Orders[warehouse_key]` | 1 : * | Single | Powers warehouse capacity map |
| `Dim_Date[date]` → `Fact_Inventory_Orders[order_date]` | 1 : * | Single | Build via **Modeling → New Table → Calendar** or Power BI's auto date/time; required for the 3-month moving average visuals |

**Model type:** Star schema (denormalized dimensions, single fact table) —
the recommended pattern for Power BI's VertiPaq engine, avoiding
snowflaking and keeping DAX measures simple single-hop `RELATED()` /
filter-propagation calculations.

**Mark `Dim_Date` as a Date Table** (Modeling ribbon → Mark as Date Table)
so time-intelligence functions (`DATEADD`, `PARALLELPERIOD`, etc.) resolve
correctly.

---

## 2. DAX Measures

Create a dedicated **measures table** (a disconnected table named `_Measures`)
to keep all calculations organized outside the physical dimension/fact
tables. Below are the four required measures, written in full.

### 2.1 OTIF % (On-Time In-Full Delivery Rate)

```dax
OTIF % =
VAR OnTimeInFullOrders =
    CALCULATE(
        COUNTROWS( Fact_Inventory_Orders ),
        Fact_Inventory_Orders[late_delivery_risk] = 0,
        Fact_Inventory_Orders[delivered_in_full] = 1
    )
VAR TotalOrders =
    COUNTROWS( Fact_Inventory_Orders )
RETURN
    DIVIDE( OnTimeInFullOrders, TotalOrders, 0 )
```

*Format as Percentage, 1 decimal place. Add a KPI target line at 95% via a
constant measure `OTIF % Target = 0.95` for conditional formatting.*

### 2.2 Total Holding Cost

```dax
Total Holding Cost =
SUMX(
    Fact_Inventory_Orders,
    Fact_Inventory_Orders[current_stock_level]
        * RELATED( Dim_Products[holding_cost_per_unit] )
)
```

*Note: because `current_stock_level` is carried as a snapshot column on the
fact table, wrap this measure with `CALCULATE( ..., LASTNONBLANK( Fact_Inventory_Orders[order_date], 1 ) )`
per product/warehouse if the fact table contains multiple historical
snapshots rather than a single current one — see the "Latest Snapshot"
variant below for production use:*

```dax
Total Holding Cost (Latest Snapshot) =
VAR LatestSnapshot =
    SUMMARIZE(
        FILTER(
            Fact_Inventory_Orders,
            Fact_Inventory_Orders[order_date]
                = CALCULATE(
                    MAX( Fact_Inventory_Orders[order_date] ),
                    ALLEXCEPT(
                        Fact_Inventory_Orders,
                        Fact_Inventory_Orders[product_key],
                        Fact_Inventory_Orders[warehouse_key]
                    )
                )
        ),
        Fact_Inventory_Orders[product_key],
        Fact_Inventory_Orders[warehouse_key],
        "StockLevel", MAX( Fact_Inventory_Orders[current_stock_level] )
    )
RETURN
    SUMX(
        LatestSnapshot,
        [StockLevel] * RELATED( Dim_Products[holding_cost_per_unit] )
    )
```

*Format as Currency ($#,##0).*

### 2.3 Inventory Turnover Ratio

```dax
Inventory Turnover Ratio =
VAR CostOfGoodsSold =
    SUMX(
        Fact_Inventory_Orders,
        Fact_Inventory_Orders[quantity] * Fact_Inventory_Orders[unit_cost_at_order]
    )
VAR AvgInventoryValue =
    AVERAGEX(
        VALUES( Dim_Products[product_key] ),
        CALCULATE(
            SUMX(
                Fact_Inventory_Orders,
                Fact_Inventory_Orders[current_stock_level] * Fact_Inventory_Orders[unit_cost_at_order]
            )
        )
    )
RETURN
    DIVIDE( CostOfGoodsSold, AvgInventoryValue, 0 )
```

*Format as a decimal number with "x" suffix (e.g., `4.2x`) using a custom
format string `0.0"x"`. A higher ratio indicates inventory is selling
through faster relative to what is held — the industry benchmark for
general merchandise retail/CPG is typically 4x-8x per year.*

### 2.4 Stockout Risk SKU Count

```dax
Stockout Risk SKU Count =
VAR SKUsBelowROP =
    FILTER(
        VALUES( Dim_Products[sku_id] ),
        CALCULATE(
            MAX( Fact_Inventory_Orders[current_stock_level] )
        ) < CALCULATE( MAX( Dim_Products[reorder_point_units] ) )
    )
RETURN
    COUNTROWS( SKUsBelowROP )
```

*Format as a whole number. Pair with a card visual using conditional
formatting (red background) when this measure exceeds a threshold, e.g.
`Stockout Risk SKU Count > 5`.*

### 2.5 Supporting Measures (used by the visuals below)

```dax
Total Orders =
COUNTROWS( Fact_Inventory_Orders )

Late Delivery % =
DIVIDE(
    CALCULATE( COUNTROWS( Fact_Inventory_Orders ), Fact_Inventory_Orders[late_delivery_risk] = 1 ),
    [Total Orders],
    0
)

Avg Lead Time Variance (Days) =
AVERAGEX(
    Fact_Inventory_Orders,
    Fact_Inventory_Orders[actual_shipping_days] - Fact_Inventory_Orders[scheduled_shipping_days]
)

Warehouse Capacity Utilization % =
VAR UnitsStored =
    SUMX( Fact_Inventory_Orders, Fact_Inventory_Orders[current_stock_level] )
VAR MaxCapacity =
    SUM( Dim_Warehouses[max_capacity_units] )
RETURN
    DIVIDE( UnitsStored, MaxCapacity, 0 )

3-Month Moving Avg Demand =
AVERAGEX(
    DATESINPERIOD( 'Dim_Date'[date], MAX( 'Dim_Date'[date] ), -3, MONTH ),
    CALCULATE( SUM( Fact_Inventory_Orders[quantity] ) )
)

Total Order Value =
SUM( Fact_Inventory_Orders[order_item_total] )
```

---

## 3. Visual Layout Blueprint

### Page 1 — Executive Inventory Control Tower

**Purpose:** A single-screen view for supply chain leadership to assess
overall inventory health, spot capacity risk, and see which SKUs need
immediate action.

| Zone | Visual Type | Fields / Measures | Notes |
|---|---|---|---|
| Top banner (left) | KPI Card | `[OTIF %]` vs `[OTIF % Target]` | Conditional color: green ≥95%, amber 85-95%, red <85% |
| Top banner (center-left) | KPI Card | `[Total Holding Cost]` | Trend arrow vs. prior month using a quick measure |
| Top banner (center-right) | KPI Card | `[Inventory Turnover Ratio]` | Format `0.0"x"` |
| Top banner (right) | KPI Card | `[Stockout Risk SKU Count]` | Red background when >5, click-through to Page 1 table filter |
| Mid-left (large) | Filled/Shape Map or Matrix Heatmap | `Dim_Warehouses[warehouse_name]` (rows) × `[Warehouse Capacity Utilization %]` (color saturation) | Use a Shape Map with warehouse region shading, or a Matrix visual if geographic map licensing/data isn't available; flag >85% in red per the SQL warehouse-capacity query |
| Mid-right | Table (Stockout Alert Table) | `Dim_Products[sku_id]`, `[product_name]`, `[category]`, `Fact_Inventory_Orders[current_stock_level]`, `Dim_Products[reorder_point_units]`, `Dim_Products[safety_stock_units]`, calculated column `Stock Status` | Directly mirrors the SQL "Stockout Alert Query" (Deliverable 3, Query 1); sort descending by units below ROP; conditional formatting on `Stock Status` (red = Critical, amber = Reorder Now) |
| Bottom | Slicers | `Dim_Products[category]`, `Dim_Warehouses[region]`, `Dim_Date[Year-Month]` | Synced across both pages via the "Sync Slicers" pane |

**Layout notes:** 4 KPI cards across the top (25% height), warehouse
utilization visual bottom-left (45% width), stockout alert table
bottom-right (55% width), slicer bar pinned along the very bottom.

### Page 2 — Supplier Scorecard & Lead Time Analysis

**Purpose:** Procurement and supplier-management view to identify
underperforming suppliers and quantify lead-time risk by category.

| Zone | Visual Type | Fields / Measures | Notes |
|---|---|---|---|
| Top-left | Clustered Bar Chart | `Dim_Suppliers[supplier_name]` (axis) × `[Late Delivery %]` (value) | Sorted descending; top 10 shown by default via a Top N filter; color gradient tied to `[OTIF %]` |
| Top-right | KPI Multi-row Card | `[OTIF %]`, `[Avg Lead Time Variance (Days)]`, `Dim_Suppliers[performance_tier]` distribution | One row per performance tier (A/B/C/D) with count of suppliers in each |
| Mid (large, full width) | Scatter Plot | X-axis = `Fact_Inventory_Orders[scheduled_shipping_days]` (avg), Y-axis = `Fact_Inventory_Orders[actual_shipping_days]` (avg), Legend = `Dim_Suppliers[supplier_name]`, Size = `[Total Order Value]` | A 45-degree reference line (via an analytics "constant line" or a calculated `y = x` measure) shows perfect on-time performance; points above the line indicate systematic delay — directly visualizes the SQL "Supplier Lead Time Deviation" window-function query (Deliverable 3, Query 2) |
| Bottom-left | Ranked Table | `Dim_Suppliers[supplier_name]`, `Dim_Products[category]`, `[Avg Lead Time Variance (Days)]`, rank column (mirrors `RANK() OVER (PARTITION BY category ORDER BY avg_delay_days DESC)`) | Add a Power BI RANKX-based calculated column: `Delay Rank In Category = RANKX(FILTER(ALL(Dim_Suppliers), Dim_Products[category] = EARLIER(Dim_Products[category])), [Avg Lead Time Variance (Days)],, DESC)` |
| Bottom-right | Line Chart | X-axis = `Dim_Date[Year-Month]`, Y-axis = `[Late Delivery %]`, Legend = `Dim_Suppliers[performance_tier]` | Trended view of late-delivery rate by tier over time to spot degrading suppliers early |

**Layout notes:** Top row (30% height) split 60/40 between bar chart and
KPI card; scatter plot occupies the full middle band (35% height); bottom
row (35% height) split 50/50 between the ranked table and the trend line.

### Cross-page interactivity

- Enable **drillthrough** from the Page 1 Stockout Alert Table to a
  (optional) Page 3 "SKU Detail" page filtered to the selected `sku_id`.
- Enable **drillthrough** from the Page 2 scatter plot point to a filtered
  Page 1 view showing only that supplier's SKUs.
- Use **bookmarks** to toggle the Page 1 warehouse visual between "Units
  Stored" and "Utilization %" views.

---

## 4. Refresh & Data Source Notes

- **Source files:** point Power BI's Power Query at
  `processed_inventory_metrics.csv`, `supplier_scorecard.csv`,
  `raw_order_telemetry.csv`, and `warehouse_stock_snapshot.csv` (all
  produced by `supply_chain_pipeline.py`), or connect directly to the
  PostgreSQL warehouse defined in `schema_and_queries.sql` using Power
  BI's native PostgreSQL connector for a live/DirectQuery model.
- **Refresh cadence:** daily scheduled refresh recommended in the Power BI
  Service, aligned with the nightly run of `supply_chain_pipeline.py` /
  ETL load into the warehouse tables.
- **Row-level security (optional):** if multiple regional teams use the
  same report, add a RLS role filtering `Dim_Warehouses[region]` to the
  logged-in user's assigned region.
