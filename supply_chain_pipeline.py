"""
supply_chain_pipeline.py
------------------------------------------------------------------------------
Enterprise Supply Chain & Inventory Optimization Intelligence
Deliverable 2: Python Demand & Supplier Analytics Pipeline

This script is fully self-contained and runs out of the box. It:

  1. Generates realistic synthetic supply chain telemetry that mirrors the
     schema of the "DataCo Smart Supply Chain for Big Data" dataset
     (orders, shipping days, late_delivery_risk, unit_cost, quantity,
     stock_levels, supplier_id, warehouse_code, product category, etc.).
  2. Calculates Supplier Lead Time Variance and On-Time In-Full (OTIF) %.
  3. Performs time-series demand analysis with a 3-month moving average
     forecast per product category.
  4. Calculates Safety Stock and Reorder Point (ROP) for every SKU.
  5. Writes two clean, analysis-ready CSV outputs:
        - processed_inventory_metrics.csv
        - supplier_scorecard.csv

Run:
    python supply_chain_pipeline.py

Dependencies:
    pip install pandas numpy
------------------------------------------------------------------------------
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# ------------------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------------------
RANDOM_SEED = 42
N_ORDERS = 15000                 # synthetic order-line records
START_DATE = datetime(2023, 1, 1)
END_DATE = datetime(2024, 12, 31)
SERVICE_Z_SCORE = 1.65           # ~95% service level for safety stock

rng = np.random.default_rng(RANDOM_SEED)

# ------------------------------------------------------------------------------
# REFERENCE DIMENSIONS (mirrors DataCo categorical structure)
# ------------------------------------------------------------------------------
CATEGORIES = [
    "Fitness", "Apparel", "Outdoor", "Sports Equipment",
    "Electronics", "Footwear", "Accessories"
]

PRODUCTS = [
    ("SKU-1001", "Diamondback Bike",        "Fitness",          185.00),
    ("SKU-1002", "Perfect Fitness Trainer", "Fitness",           58.00),
    ("SKU-1003", "Nike Men's Shorts",       "Apparel",           22.50),
    ("SKU-1004", "Field & Stream Tent",     "Outdoor",          210.00),
    ("SKU-1005", "Under Armour Hoodie",     "Apparel",           34.00),
    ("SKU-1006", "Yoga Mat Premium",        "Fitness",           18.00),
    ("SKU-1007", "Coleman Cooler 50QT",     "Outdoor",          120.00),
    ("SKU-1008", "Wilson Golf Balls (Dz)",  "Sports Equipment",  15.00),
    ("SKU-1009", "Nike Dri-FIT Polo",       "Apparel",           28.00),
    ("SKU-1010", "Garmin Running Watch",    "Electronics",      249.00),
    ("SKU-1011", "Asics Running Shoes",     "Footwear",          72.00),
    ("SKU-1012", "North Face Backpack",     "Outdoor",           95.00),
    ("SKU-1013", "Bluetooth Earbuds",       "Electronics",       45.00),
    ("SKU-1014", "Wilson Tennis Racket",    "Sports Equipment", 110.00),
    ("SKU-1015", "Baseball Cap",            "Accessories",       14.00),
]

SUPPLIERS = [f"SUP-{100 + i}" for i in range(12)]
SUPPLIER_QUALITY = {s: rng.uniform(0.55, 0.98) for s in SUPPLIERS}   # base on-time propensity
SUPPLIER_SCHEDULED_LEAD = {s: int(rng.integers(3, 12)) for s in SUPPLIERS}  # contracted lead days

WAREHOUSES = [
    ("WH-EAST", "Newark, NJ", 50000),
    ("WH-CENTRAL", "Columbus, OH", 65000),
    ("WH-WEST", "Reno, NV", 55000),
    ("WH-SOUTH", "Dallas, TX", 60000),
]
WAREHOUSE_CODES = [w[0] for w in WAREHOUSES]

SHIPPING_MODES = ["Standard Class", "First Class", "Second Class", "Same Day"]
MARKETS = ["US", "EU", "LATAM", "APAC"]


# ------------------------------------------------------------------------------
# STEP 1: GENERATE SYNTHETIC ORDER TELEMETRY (DataCo-style schema)
# ------------------------------------------------------------------------------
def generate_order_telemetry(n_orders: int = N_ORDERS) -> pd.DataFrame:
    """Generates a synthetic order-line fact table matching DataCo's core fields."""
    date_range_days = (END_DATE - START_DATE).days
    order_dates = [START_DATE + timedelta(days=int(d)) for d in rng.integers(0, date_range_days, n_orders)]

    product_idx = rng.integers(0, len(PRODUCTS), n_orders)
    sku_ids = [PRODUCTS[i][0] for i in product_idx]
    product_names = [PRODUCTS[i][1] for i in product_idx]
    categories = [PRODUCTS[i][2] for i in product_idx]
    unit_costs = np.array([PRODUCTS[i][3] for i in product_idx])

    suppliers = rng.choice(SUPPLIERS, n_orders)
    warehouses = rng.choice(WAREHOUSE_CODES, n_orders)
    shipping_modes = rng.choice(SHIPPING_MODES, n_orders, p=[0.55, 0.20, 0.15, 0.10])
    markets = rng.choice(MARKETS, n_orders, p=[0.55, 0.20, 0.15, 0.10])

    quantity = rng.integers(1, 25, n_orders)

    # Scheduled shipping days pulled from the supplier's contracted lead time,
    # with small noise to reflect route/mode variability.
    scheduled_shipping_days = np.array([SUPPLIER_SCHEDULED_LEAD[s] for s in suppliers]) + \
        rng.integers(-1, 2, n_orders)
    scheduled_shipping_days = np.clip(scheduled_shipping_days, 1, None)

    # Actual shipping days driven directly by supplier quality: each order is
    # independently "late" with probability (1 - quality), so higher-quality
    # suppliers cleanly separate into better OTIF tiers.
    quality = np.array([SUPPLIER_QUALITY[s] for s in suppliers])
    is_late = rng.random(n_orders) > quality
    on_time_adjustment = rng.integers(-1, 1, n_orders)          # arrive same day or 1 day early
    late_adjustment = rng.integers(1, 6, n_orders)              # arrive 1-5 days late
    delay_days = np.where(is_late, late_adjustment, on_time_adjustment)
    actual_shipping_days = np.clip(scheduled_shipping_days + delay_days, 1, None).astype(int)

    late_delivery_risk = (actual_shipping_days > scheduled_shipping_days).astype(int)

    # Order was fulfilled "in full" (no partial shipment) ~92% of the time, correlated with quality
    in_full_prob = np.clip(quality + 0.05, 0, 0.99)
    delivered_in_full = (rng.random(n_orders) < in_full_prob).astype(int)

    order_item_total = quantity * unit_costs * rng.uniform(0.95, 1.35, n_orders)  # incl. margin/tax noise

    df = pd.DataFrame({
        "order_id": np.arange(1, n_orders + 1),
        "order_date": order_dates,
        "sku_id": sku_ids,
        "product_name": product_names,
        "category": categories,
        "supplier_id": suppliers,
        "warehouse_code": warehouses,
        "market": markets,
        "shipping_mode": shipping_modes,
        "quantity": quantity,
        "unit_cost": np.round(unit_costs, 2),
        "order_item_total": np.round(order_item_total, 2),
        "scheduled_shipping_days": scheduled_shipping_days,
        "actual_shipping_days": actual_shipping_days,
        "late_delivery_risk": late_delivery_risk,
        "delivered_in_full": delivered_in_full,
    })

    df["order_date"] = pd.to_datetime(df["order_date"])
    df["order_month"] = df["order_date"].dt.to_period("M").astype(str)
    return df.sort_values("order_date").reset_index(drop=True)


def generate_current_stock_levels() -> pd.DataFrame:
    """Generates a synthetic point-in-time stock snapshot per SKU per warehouse."""
    records = []
    for sku_id, name, category, unit_cost in PRODUCTS:
        for wh in WAREHOUSE_CODES:
            records.append({
                "sku_id": sku_id,
                "product_name": name,
                "category": category,
                "warehouse_code": wh,
                "current_stock_level": int(rng.integers(5, 100)),
                "unit_cost": unit_cost,
                "holding_cost_per_unit": round(unit_cost * rng.uniform(0.08, 0.18), 2),  # 8-18% of unit cost / yr
            })
    return pd.DataFrame(records)


# ------------------------------------------------------------------------------
# STEP 2: SUPPLIER LEAD TIME VARIANCE + OTIF %
# ------------------------------------------------------------------------------
def calculate_supplier_scorecard(orders: pd.DataFrame) -> pd.DataFrame:
    """
    Lead Time Variance = actual_shipping_days - scheduled_shipping_days
    OTIF % = % of orders delivered both On-Time (not late) AND In-Full
    """
    df = orders.copy()
    df["lead_time_variance_days"] = df["actual_shipping_days"] - df["scheduled_shipping_days"]
    df["on_time_in_full"] = ((df["late_delivery_risk"] == 0) & (df["delivered_in_full"] == 1)).astype(int)

    scorecard = df.groupby("supplier_id").agg(
        total_orders=("order_id", "count"),
        avg_scheduled_lead_days=("scheduled_shipping_days", "mean"),
        avg_actual_lead_days=("actual_shipping_days", "mean"),
        avg_lead_time_variance_days=("lead_time_variance_days", "mean"),
        max_lead_time_variance_days=("lead_time_variance_days", "max"),
        late_delivery_rate_pct=("late_delivery_risk", "mean"),
        in_full_rate_pct=("delivered_in_full", "mean"),
        otif_pct=("on_time_in_full", "mean"),
        total_order_value=("order_item_total", "sum"),
    ).reset_index()

    for col in ["late_delivery_rate_pct", "in_full_rate_pct", "otif_pct"]:
        scorecard[col] = (scorecard[col] * 100).round(2)

    for col in ["avg_scheduled_lead_days", "avg_actual_lead_days", "avg_lead_time_variance_days"]:
        scorecard[col] = scorecard[col].round(2)

    scorecard["total_order_value"] = scorecard["total_order_value"].round(2)

    # Performance tier for quick triage
    def tier(otif):
        if otif >= 95:
            return "A - Preferred"
        elif otif >= 85:
            return "B - Acceptable"
        elif otif >= 70:
            return "C - Watch List"
        else:
            return "D - At Risk"

    scorecard["performance_tier"] = scorecard["otif_pct"].apply(tier)
    scorecard["rank_by_otif"] = scorecard["otif_pct"].rank(ascending=False, method="min").astype(int)

    return scorecard.sort_values("otif_pct", ascending=False).reset_index(drop=True)


# ------------------------------------------------------------------------------
# STEP 3: TIME SERIES DEMAND ANALYSIS (3-MONTH MOVING AVERAGE, PER CATEGORY)
# ------------------------------------------------------------------------------
def calculate_demand_forecast(orders: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregates monthly demand (units) per product category, then computes a
    3-month trailing moving average as a simple, transparent forecast baseline.
    """
    monthly = (
        orders.groupby(["category", "order_month"])["quantity"]
        .sum()
        .reset_index()
        .rename(columns={"quantity": "monthly_demand_units"})
    )
    monthly = monthly.sort_values(["category", "order_month"]).reset_index(drop=True)

    monthly["moving_avg_3mo_demand"] = (
        monthly.groupby("category")["monthly_demand_units"]
        .transform(lambda s: s.rolling(window=3, min_periods=1).mean())
        .round(1)
    )

    # Naive next-month forecast = latest 3-month moving average carried forward
    monthly["forecast_next_month_units"] = monthly["moving_avg_3mo_demand"].round(0)

    # Demand volatility (rolling std dev) — useful input for safety-stock sizing
    monthly["demand_std_dev_3mo"] = (
        monthly.groupby("category")["monthly_demand_units"]
        .transform(lambda s: s.rolling(window=3, min_periods=1).std())
        .fillna(0)
        .round(1)
    )

    return monthly


# ------------------------------------------------------------------------------
# STEP 4: SAFETY STOCK + REORDER POINT PER SKU
# ------------------------------------------------------------------------------
def calculate_safety_stock_and_rop(orders: pd.DataFrame, stock_levels: pd.DataFrame) -> pd.DataFrame:
    """
    Safety Stock = Z * demand_std_dev * SQRT(avg_lead_time_days)   [statistical method]
    Reorder Point (ROP) = (Avg Daily Demand * Avg Lead Time) + Safety Stock
    """
    daily = (
        orders.groupby(["sku_id", "order_date"])["quantity"].sum().reset_index()
    )
    demand_stats = (
        daily.groupby("sku_id")["quantity"]
        .agg(avg_daily_demand="mean", std_daily_demand="std", max_daily_demand="max")
        .reset_index()
    )
    demand_stats["std_daily_demand"] = demand_stats["std_daily_demand"].fillna(0)

    lead_stats = (
        orders.groupby("sku_id")
        .agg(
            avg_lead_time_days=("actual_shipping_days", "mean"),
            max_lead_time_days=("actual_shipping_days", "max"),
        )
        .reset_index()
    )

    sku_metrics = demand_stats.merge(lead_stats, on="sku_id", how="left")

    # Safety Stock (statistical method, accounts for demand variability under lead time)
    sku_metrics["safety_stock_units"] = (
        SERVICE_Z_SCORE * sku_metrics["std_daily_demand"] * np.sqrt(sku_metrics["avg_lead_time_days"])
    ).round(0)

    # Deterministic cross-check safety stock (max/avg method), reported alongside for transparency
    sku_metrics["safety_stock_units_maxavg_method"] = (
        (sku_metrics["max_daily_demand"] * sku_metrics["max_lead_time_days"])
        - (sku_metrics["avg_daily_demand"] * sku_metrics["avg_lead_time_days"])
    ).round(0).clip(lower=0)

    sku_metrics["reorder_point_units"] = (
        sku_metrics["avg_daily_demand"] * sku_metrics["avg_lead_time_days"] + sku_metrics["safety_stock_units"]
    ).round(0)

    # Merge with current stock snapshot (aggregated to SKU level across warehouses)
    stock_by_sku = (
        stock_levels.groupby(["sku_id", "product_name", "category"])
        .agg(
            current_stock_level=("current_stock_level", "sum"),
            unit_cost=("unit_cost", "first"),
            holding_cost_per_unit=("holding_cost_per_unit", "mean"),
        )
        .reset_index()
    )

    result = stock_by_sku.merge(sku_metrics, on="sku_id", how="left")

    result["stockout_flag"] = np.where(
        result["current_stock_level"] < result["reorder_point_units"], "REORDER NOW", "OK"
    )
    result["units_below_rop"] = (
        result["reorder_point_units"] - result["current_stock_level"]
    ).clip(lower=0).round(0)

    round_cols = [
        "avg_daily_demand", "std_daily_demand", "avg_lead_time_days",
        "holding_cost_per_unit"
    ]
    for c in round_cols:
        result[c] = result[c].round(2)

    ordered_cols = [
        "sku_id", "product_name", "category", "current_stock_level", "unit_cost",
        "holding_cost_per_unit", "avg_daily_demand", "std_daily_demand", "max_daily_demand",
        "avg_lead_time_days", "max_lead_time_days", "safety_stock_units",
        "safety_stock_units_maxavg_method", "reorder_point_units", "units_below_rop",
        "stockout_flag"
    ]
    return result[ordered_cols].sort_values("sku_id").reset_index(drop=True)


# ------------------------------------------------------------------------------
# STEP 5: ASSEMBLE FINAL PROCESSED OUTPUT + SAVE CSVS
# ------------------------------------------------------------------------------
def main():
    print("=" * 78)
    print("SUPPLY CHAIN & INVENTORY OPTIMIZATION PIPELINE")
    print("=" * 78)

    print("\n[1/5] Generating synthetic DataCo-style order telemetry...")
    orders = generate_order_telemetry()
    print(f"      -> {len(orders):,} order-line records generated "
          f"({orders['order_date'].min().date()} to {orders['order_date'].max().date()})")

    print("[2/5] Generating current warehouse stock snapshot...")
    stock_levels = generate_current_stock_levels()
    print(f"      -> {len(stock_levels):,} SKU/warehouse stock records generated")

    print("[3/5] Calculating supplier lead time variance and OTIF %...")
    supplier_scorecard = calculate_supplier_scorecard(orders)
    print(f"      -> Scorecard built for {len(supplier_scorecard)} suppliers")

    print("[4/5] Running 3-month moving average demand forecast by category...")
    demand_forecast = calculate_demand_forecast(orders)
    print(f"      -> {len(demand_forecast)} category-month demand rows generated")

    print("[5/5] Calculating Safety Stock and Reorder Points per SKU...")
    inventory_metrics = calculate_safety_stock_and_rop(orders, stock_levels)
    print(f"      -> Inventory metrics computed for {len(inventory_metrics)} SKUs")

    # Enrich the SKU-level inventory metrics with the latest forecast signal per category
    latest_forecast = (
        demand_forecast.sort_values("order_month")
        .groupby("category")
        .tail(1)[["category", "forecast_next_month_units", "demand_std_dev_3mo"]]
        .rename(columns={
            "forecast_next_month_units": "category_forecast_next_month_units",
            "demand_std_dev_3mo": "category_demand_volatility_3mo",
        })
    )
    processed_inventory_metrics = inventory_metrics.merge(latest_forecast, on="category", how="left")

    # -------------------- SAVE OUTPUTS --------------------
    processed_inventory_metrics.to_csv("processed_inventory_metrics.csv", index=False)
    supplier_scorecard.to_csv("supplier_scorecard.csv", index=False)

    # Also persist the raw synthetic telemetry and demand forecast for audit / BI ingestion
    orders.to_csv("raw_order_telemetry.csv", index=False)
    demand_forecast.to_csv("demand_forecast_by_category.csv", index=False)
    stock_levels.to_csv("warehouse_stock_snapshot.csv", index=False)

    print("\n" + "=" * 78)
    print("OUTPUT FILES WRITTEN:")
    print("  - processed_inventory_metrics.csv   (SKU-level safety stock / ROP / stockout flags)")
    print("  - supplier_scorecard.csv            (supplier OTIF % / lead-time variance / tiering)")
    print("  - demand_forecast_by_category.csv   (3-month moving average forecast, supporting detail)")
    print("  - raw_order_telemetry.csv           (synthetic DataCo-style order lines, supporting detail)")
    print("  - warehouse_stock_snapshot.csv       (synthetic point-in-time stock snapshot, supporting detail)")
    print("=" * 78)

    print("\nSAMPLE: processed_inventory_metrics.csv (top 5 rows)")
    print(processed_inventory_metrics.head(5).to_string(index=False))

    print("\nSAMPLE: supplier_scorecard.csv (top 5 rows)")
    print(supplier_scorecard.head(5).to_string(index=False))

    n_reorder = (processed_inventory_metrics["stockout_flag"] == "REORDER NOW").sum()
    print(f"\n{n_reorder} of {len(processed_inventory_metrics)} SKUs are currently below their Reorder Point.")


if __name__ == "__main__":
    main()
