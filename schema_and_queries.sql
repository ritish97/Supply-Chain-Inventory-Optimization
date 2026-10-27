-- =============================================================================
-- Enterprise Supply Chain & Inventory Optimization Intelligence
-- Deliverable 3: SQL Data Warehousing & Analytics
-- Target: PostgreSQL 13+
--
-- Contents:
--   SECTION 1: Star Schema DDL (Fact_Inventory_Orders, Dim_Products,
--              Dim_Suppliers, Dim_Warehouses)
--   SECTION 2: Query 1 - Stockout Alert Query
--   SECTION 3: Query 2 - Supplier Lead Time Deviation (Window Functions)
--   SECTION 4: Query 3 - Warehouse Capacity Utilization
--
-- The schema mirrors the grain of the "DataCo Smart Supply Chain for Big
-- Data" dataset (order line = fact grain), denormalized into dimension
-- tables for product, supplier, and warehouse attributes.
-- =============================================================================


-- =============================================================================
-- SECTION 1: STAR SCHEMA DDL
-- =============================================================================

DROP TABLE IF EXISTS Fact_Inventory_Orders CASCADE;
DROP TABLE IF EXISTS Dim_Products CASCADE;
DROP TABLE IF EXISTS Dim_Suppliers CASCADE;
DROP TABLE IF EXISTS Dim_Warehouses CASCADE;

-- -----------------------------------------------------------------------------
-- Dim_Products
-- One row per SKU. Holds the static/slowly-changing attributes of a product,
-- plus the current computed inventory-policy fields (safety stock / ROP) that
-- the analytics pipeline (Deliverable 2) refreshes on each run.
-- -----------------------------------------------------------------------------
CREATE TABLE Dim_Products (
    product_key             SERIAL PRIMARY KEY,
    sku_id                  VARCHAR(20)     NOT NULL UNIQUE,
    product_name            VARCHAR(150)    NOT NULL,
    category                VARCHAR(50)     NOT NULL,
    unit_cost                NUMERIC(10, 2)  NOT NULL CHECK (unit_cost >= 0),
    selling_price            NUMERIC(10, 2)  CHECK (selling_price >= 0),
    holding_cost_per_unit    NUMERIC(10, 2)  NOT NULL DEFAULT 0 CHECK (holding_cost_per_unit >= 0),
    ordering_cost             NUMERIC(10, 2)  NOT NULL DEFAULT 0 CHECK (ordering_cost >= 0),
    safety_stock_units       NUMERIC(10, 2)  NOT NULL DEFAULT 0,
    reorder_point_units      NUMERIC(10, 2)  NOT NULL DEFAULT 0,
    economic_order_qty       NUMERIC(10, 2)  NOT NULL DEFAULT 0,
    is_active                BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at                TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at                TIMESTAMP       NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE Dim_Products IS 'Product dimension: one row per SKU, including current inventory policy values.';

-- -----------------------------------------------------------------------------
-- Dim_Suppliers
-- One row per supplier. Holds contracted service terms and the latest
-- rolled-up performance metrics (refreshed by the supplier scorecard job).
-- -----------------------------------------------------------------------------
CREATE TABLE Dim_Suppliers (
    supplier_key                SERIAL PRIMARY KEY,
    supplier_id                 VARCHAR(20)     NOT NULL UNIQUE,
    supplier_name                VARCHAR(150)    NOT NULL,
    contracted_lead_time_days   INTEGER         NOT NULL CHECK (contracted_lead_time_days > 0),
    country                      VARCHAR(60),
    otif_pct                     NUMERIC(5, 2)   DEFAULT 0 CHECK (otif_pct BETWEEN 0 AND 100),
    performance_tier             VARCHAR(30)     DEFAULT 'Unrated',
    is_active                    BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at                    TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at                    TIMESTAMP       NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE Dim_Suppliers IS 'Supplier dimension: one row per supplier, including latest OTIF % and tiering.';

-- -----------------------------------------------------------------------------
-- Dim_Warehouses
-- One row per warehouse/distribution center.
-- -----------------------------------------------------------------------------
CREATE TABLE Dim_Warehouses (
    warehouse_key            SERIAL PRIMARY KEY,
    warehouse_code            VARCHAR(20)     NOT NULL UNIQUE,
    warehouse_name             VARCHAR(150)    NOT NULL,
    region                      VARCHAR(50),
    max_capacity_units         NUMERIC(12, 2)  NOT NULL CHECK (max_capacity_units > 0),
    monthly_operating_cost      NUMERIC(12, 2)  DEFAULT 0,
    created_at                  TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMP       NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE Dim_Warehouses IS 'Warehouse dimension: one row per distribution center, including rated capacity.';

-- -----------------------------------------------------------------------------
-- Fact_Inventory_Orders
-- Grain: one row per order line (matches DataCo order-item grain), enriched
-- with a point-in-time snapshot of current_stock_level for the SKU/warehouse
-- at time of load, so stockout logic can be evaluated directly against facts.
-- -----------------------------------------------------------------------------
CREATE TABLE Fact_Inventory_Orders (
    order_line_key           BIGSERIAL PRIMARY KEY,
    order_id                  BIGINT          NOT NULL,
    order_date                 DATE            NOT NULL,
    product_key                INTEGER         NOT NULL REFERENCES Dim_Products(product_key),
    supplier_key                INTEGER         NOT NULL REFERENCES Dim_Suppliers(supplier_key),
    warehouse_key               INTEGER         NOT NULL REFERENCES Dim_Warehouses(warehouse_key),
    quantity                    INTEGER         NOT NULL CHECK (quantity > 0),
    unit_cost_at_order           NUMERIC(10, 2)  NOT NULL CHECK (unit_cost_at_order >= 0),
    order_item_total             NUMERIC(12, 2)  NOT NULL CHECK (order_item_total >= 0),
    scheduled_shipping_days      INTEGER         NOT NULL CHECK (scheduled_shipping_days > 0),
    actual_shipping_days         INTEGER         NOT NULL CHECK (actual_shipping_days > 0),
    late_delivery_risk           SMALLINT        NOT NULL DEFAULT 0 CHECK (late_delivery_risk IN (0, 1)),
    delivered_in_full            SMALLINT        NOT NULL DEFAULT 1 CHECK (delivered_in_full IN (0, 1)),
    current_stock_level          INTEGER         NOT NULL DEFAULT 0 CHECK (current_stock_level >= 0),
    shipping_mode                 VARCHAR(30),
    market                        VARCHAR(20),
    created_at                    TIMESTAMP       NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE Fact_Inventory_Orders IS 'Fact table at order-line grain; FKs to Dim_Products, Dim_Suppliers, Dim_Warehouses.';

-- -----------------------------------------------------------------------------
-- Indexes: support the analytic queries in Sections 2-4
-- -----------------------------------------------------------------------------
CREATE INDEX idx_fact_orders_product        ON Fact_Inventory_Orders(product_key);
CREATE INDEX idx_fact_orders_supplier       ON Fact_Inventory_Orders(supplier_key);
CREATE INDEX idx_fact_orders_warehouse      ON Fact_Inventory_Orders(warehouse_key);
CREATE INDEX idx_fact_orders_order_date     ON Fact_Inventory_Orders(order_date);
CREATE INDEX idx_fact_orders_late_delivery  ON Fact_Inventory_Orders(late_delivery_risk);
CREATE INDEX idx_dim_products_category      ON Dim_Products(category);
CREATE INDEX idx_dim_suppliers_tier         ON Dim_Suppliers(performance_tier);


-- =============================================================================
-- SECTION 2: QUERY 1 - STOCKOUT ALERT QUERY
-- Compares current_stock_level (latest fact snapshot per SKU/warehouse)
-- against the calculated reorder_point on Dim_Products and flags critical
-- items requiring immediate reorder.
-- =============================================================================

WITH latest_stock_snapshot AS (
    -- One row per product/warehouse: the most recent stock reading on file
    SELECT DISTINCT ON (f.product_key, f.warehouse_key)
        f.product_key,
        f.warehouse_key,
        f.current_stock_level,
        f.order_date AS snapshot_date
    FROM Fact_Inventory_Orders f
    ORDER BY f.product_key, f.warehouse_key, f.order_date DESC
)
SELECT
    p.sku_id,
    p.product_name,
    p.category,
    w.warehouse_code,
    w.warehouse_name,
    s.current_stock_level,
    p.reorder_point_units,
    p.safety_stock_units,
    (p.reorder_point_units - s.current_stock_level)                     AS units_below_rop,
    ROUND(p.unit_cost * (p.reorder_point_units - s.current_stock_level), 2) AS estimated_reorder_value,
    CASE
        WHEN s.current_stock_level <= p.safety_stock_units       THEN 'CRITICAL - BELOW SAFETY STOCK'
        WHEN s.current_stock_level <  p.reorder_point_units      THEN 'REORDER NOW'
        ELSE 'OK'
    END                                                                    AS stock_status,
    s.snapshot_date
FROM latest_stock_snapshot s
JOIN Dim_Products   p ON p.product_key   = s.product_key
JOIN Dim_Warehouses w ON w.warehouse_key = s.warehouse_key
WHERE s.current_stock_level < p.reorder_point_units      -- only surface items needing action
ORDER BY
    CASE
        WHEN s.current_stock_level <= p.safety_stock_units THEN 0   -- critical items first
        ELSE 1
    END,
    units_below_rop DESC;


-- =============================================================================
-- SECTION 3: QUERY 2 - SUPPLIER LEAD TIME DEVIATION (WINDOW FUNCTIONS)
-- Ranks suppliers by average delay days within each product category using
-- RANK() OVER (PARTITION BY category ORDER BY avg_delay_days DESC) to
-- surface the worst-performing supplier per category.
-- =============================================================================

WITH supplier_category_performance AS (
    SELECT
        p.category,
        s.supplier_id,
        s.supplier_name,
        COUNT(*)                                                         AS total_orders,
        ROUND(AVG(f.actual_shipping_days - f.scheduled_shipping_days), 2) AS avg_delay_days,
        ROUND(100.0 * SUM(f.late_delivery_risk) / COUNT(*), 2)            AS late_delivery_rate_pct,
        ROUND(100.0 * SUM(CASE WHEN f.late_delivery_risk = 0
                                 AND f.delivered_in_full = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS otif_pct
    FROM Fact_Inventory_Orders f
    JOIN Dim_Products  p ON p.product_key  = f.product_key
    JOIN Dim_Suppliers s ON s.supplier_key = f.supplier_key
    GROUP BY p.category, s.supplier_id, s.supplier_name
)
SELECT
    category,
    supplier_id,
    supplier_name,
    total_orders,
    avg_delay_days,
    late_delivery_rate_pct,
    otif_pct,
    RANK()       OVER (PARTITION BY category ORDER BY avg_delay_days DESC) AS delay_rank_in_category,
    DENSE_RANK() OVER (PARTITION BY category ORDER BY otif_pct ASC)        AS otif_risk_rank_in_category,
    ROUND(
        AVG(avg_delay_days) OVER (PARTITION BY category), 2
    )                                                                      AS category_avg_delay_days,
    ROUND(
        avg_delay_days - AVG(avg_delay_days) OVER (PARTITION BY category), 2
    )                                                                      AS delay_vs_category_avg
FROM supplier_category_performance
ORDER BY category, delay_rank_in_category;


-- =============================================================================
-- SECTION 4: QUERY 3 - WAREHOUSE CAPACITY UTILIZATION
-- Calculates total inventory holding cost per warehouse and flags
-- over-capacity warehouses (utilization > 85%).
-- =============================================================================

WITH latest_stock_snapshot AS (
    SELECT DISTINCT ON (f.product_key, f.warehouse_key)
        f.product_key,
        f.warehouse_key,
        f.current_stock_level
    FROM Fact_Inventory_Orders f
    ORDER BY f.product_key, f.warehouse_key, f.order_date DESC
),
warehouse_inventory AS (
    SELECT
        w.warehouse_key,
        w.warehouse_code,
        w.warehouse_name,
        w.max_capacity_units,
        w.monthly_operating_cost,
        SUM(s.current_stock_level)                              AS total_units_stored,
        SUM(s.current_stock_level * p.holding_cost_per_unit)     AS total_holding_cost
    FROM latest_stock_snapshot s
    JOIN Dim_Products   p ON p.product_key   = s.product_key
    JOIN Dim_Warehouses w ON w.warehouse_key = s.warehouse_key
    GROUP BY w.warehouse_key, w.warehouse_code, w.warehouse_name, w.max_capacity_units, w.monthly_operating_cost
)
SELECT
    warehouse_code,
    warehouse_name,
    total_units_stored,
    max_capacity_units,
    ROUND(100.0 * total_units_stored / max_capacity_units, 2)   AS utilization_pct,
    ROUND(total_holding_cost, 2)                                  AS total_holding_cost,
    monthly_operating_cost,
    ROUND(total_holding_cost + monthly_operating_cost, 2)        AS total_warehouse_carrying_cost,
    CASE
        WHEN 100.0 * total_units_stored / max_capacity_units > 85 THEN 'OVER CAPACITY - ACTION REQUIRED'
        WHEN 100.0 * total_units_stored / max_capacity_units > 70 THEN 'APPROACHING CAPACITY'
        ELSE 'HEALTHY'
    END                                                            AS capacity_status
FROM warehouse_inventory
ORDER BY utilization_pct DESC;
