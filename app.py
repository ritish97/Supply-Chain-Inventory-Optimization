"""
Enterprise Supply Chain & Inventory Optimization Intelligence
Streamlit Web Application Frontend

Built on the DataCo Smart Supply Chain architecture:
- Executive Inventory Control Tower
- Supplier Scorecard & Lead Time Analysis
- Interactive EOQ & Safety Stock Simulator
- Demand Forecasting & Category Trends
- Live SQL Data Warehouse Analytics
- Pipeline Simulation & Export
"""

import os
import math
import sqlite3
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import streamlit as st

# -----------------------------------------------------------------------------
# PAGE CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Supply Chain & Inventory Control Tower",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------------------------------------------------------
# THEME TOKENS & STYLES (Matching specified corporate palette)
# Primary: #0052CC, Canvas: #FFFFFF, Secondary: #F4F5F7, Text: #172B4D
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    /* Global Font & Text */
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        color: #172B4D;
    }
    
    /* Main Canvas styling */
    .stApp {
        background-color: #FFFFFF;
    }
    
    /* Top Header Bar */
    .enterprise-header {
        background: linear-gradient(90deg, #0052CC 0%, #0747A6 100%);
        padding: 20px 24px;
        border-radius: 10px;
        color: #FFFFFF;
        margin-bottom: 24px;
        box-shadow: 0 4px 12px rgba(0, 82, 204, 0.15);
    }
    .enterprise-header h1 {
        color: #FFFFFF !important;
        font-size: 26px;
        font-weight: 700;
        margin: 0 0 6px 0;
        letter-spacing: -0.3px;
    }
    .enterprise-header p {
        color: #DEEBFF !important;
        font-size: 14px;
        margin: 0;
        opacity: 0.95;
    }
    
    /* Metric Cards */
    .metric-card {
        background-color: #F4F5F7;
        border: 1px solid #DFE1E6;
        border-radius: 8px;
        padding: 16px 18px;
        margin-bottom: 12px;
        box-shadow: 0 1px 3px rgba(9, 30, 66, 0.08);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 10px rgba(9, 30, 66, 0.12);
        border-color: #0052CC;
    }
    .metric-label {
        font-size: 12px;
        font-weight: 600;
        color: #5E6C84;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 26px;
        font-weight: 700;
        color: #172B4D;
        line-height: 1.2;
    }
    .metric-sub {
        font-size: 12px;
        margin-top: 6px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    
    /* Status Badges */
    .badge-ok {
        background-color: #E3FCEF;
        color: #006644;
        font-weight: 600;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 11px;
    }
    .badge-warning {
        background-color: #FFF0B3;
        color: #172B4D;
        font-weight: 600;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 11px;
    }
    .badge-critical {
        background-color: #FFEBE6;
        color: #BF2600;
        font-weight: 600;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 11px;
    }
    .badge-info {
        background-color: #DEEBFF;
        color: #0747A6;
        font-weight: 600;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 11px;
    }
    
    /* Section Containers */
    .card-container {
        background-color: #FFFFFF;
        border: 1px solid #DFE1E6;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 1px 3px rgba(9, 30, 66, 0.05);
    }
    
    /* Custom Sidebar Header */
    .sidebar-brand {
        padding: 12px 0 20px 0;
        border-bottom: 1px solid #DFE1E6;
        margin-bottom: 18px;
    }
    .sidebar-brand h2 {
        color: #0052CC;
        font-size: 18px;
        font-weight: 700;
        margin: 0 0 4px 0;
    }
    .sidebar-brand p {
        color: #5E6C84;
        font-size: 12px;
        margin: 0;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# CONSTANTS & METADATA
# -----------------------------------------------------------------------------
APP_DIR = os.path.dirname(os.path.abspath(__file__))

WAREHOUSE_METADATA = {
    "WH-EAST": {"name": "Newark, NJ Distribution Center", "region": "East", "max_capacity": 50000, "op_cost": 45000},
    "WH-CENTRAL": {"name": "Columbus, OH Distribution Center", "region": "Central", "max_capacity": 65000, "op_cost": 52000},
    "WH-WEST": {"name": "Reno, NV Distribution Center", "region": "West", "max_capacity": 55000, "op_cost": 48000},
    "WH-SOUTH": {"name": "Dallas, TX Distribution Center", "region": "South", "max_capacity": 60000, "op_cost": 50000},
}

CATEGORIES_ALL = [
    "Fitness", "Apparel", "Outdoor", "Sports Equipment",
    "Electronics", "Footwear", "Accessories"
]

# -----------------------------------------------------------------------------
# DATA LOADING & CACHING
# -----------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_data():
    """Loads CSV files or generates them if not present."""
    metrics_path = os.path.join(APP_DIR, "processed_inventory_metrics.csv")
    scorecard_path = os.path.join(APP_DIR, "supplier_scorecard.csv")
    telemetry_path = os.path.join(APP_DIR, "raw_order_telemetry.csv")
    snapshot_path = os.path.join(APP_DIR, "warehouse_stock_snapshot.csv")
    forecast_path = os.path.join(APP_DIR, "demand_forecast_by_category.csv")

    # If any files are missing, run pipeline logic
    if not (os.path.exists(metrics_path) and os.path.exists(telemetry_path)):
        import supply_chain_pipeline
        supply_chain_pipeline.main()

    df_metrics = pd.read_csv(metrics_path)
    df_scorecard = pd.read_csv(scorecard_path)
    df_orders = pd.read_csv(telemetry_path)
    df_snapshot = pd.read_csv(snapshot_path)
    df_forecast = pd.read_csv(forecast_path)

    # Type conversions
    df_orders["order_date"] = pd.to_datetime(df_orders["order_date"])
    df_orders["lead_time_variance"] = df_orders["actual_shipping_days"] - df_orders["scheduled_shipping_days"]
    df_orders["on_time_in_full"] = ((df_orders["late_delivery_risk"] == 0) & (df_orders["delivered_in_full"] == 1)).astype(int)

    return df_metrics, df_scorecard, df_orders, df_snapshot, df_forecast

# -----------------------------------------------------------------------------
# IN-MEMORY SQL DATABASE INITIALIZATION
# -----------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_sqlite_warehouse(df_metrics, df_scorecard, df_orders, df_snapshot):
    """Creates an in-memory SQLite database matching the star schema from schema_and_queries.sql."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    
    # 1. Dim_Products
    products = df_metrics[[
        "sku_id", "product_name", "category", "unit_cost", "holding_cost_per_unit",
        "safety_stock_units", "reorder_point_units"
    ]].copy()
    products["product_key"] = range(1, len(products) + 1)
    products["selling_price"] = (products["unit_cost"] * 1.5).round(2)
    products["ordering_cost"] = 50.0
    products["economic_order_qty"] = np.sqrt(
        (2 * products["unit_cost"] * 300 * products["ordering_cost"]) / products["holding_cost_per_unit"]
    ).round(0)
    products.to_sql("Dim_Products", conn, if_exists="replace", index=False)

    # 2. Dim_Suppliers
    suppliers = df_scorecard[[
        "supplier_id", "avg_scheduled_lead_days", "otif_pct", "performance_tier"
    ]].copy()
    suppliers["supplier_key"] = range(1, len(suppliers) + 1)
    suppliers["supplier_name"] = suppliers["supplier_id"].apply(lambda s: f"Supplier {s}")
    suppliers["contracted_lead_time_days"] = suppliers["avg_scheduled_lead_days"].round(0).astype(int)
    suppliers["country"] = "United States"
    suppliers.to_sql("Dim_Suppliers", conn, if_exists="replace", index=False)

    # 3. Dim_Warehouses
    wh_data = []
    for i, (code, info) in enumerate(WAREHOUSE_METADATA.items(), start=1):
        wh_data.append({
            "warehouse_key": i,
            "warehouse_code": code,
            "warehouse_name": info["name"],
            "region": info["region"],
            "max_capacity_units": info["max_capacity"],
            "monthly_operating_cost": info["op_cost"]
        })
    df_wh = pd.DataFrame(wh_data)
    df_wh.to_sql("Dim_Warehouses", conn, if_exists="replace", index=False)

    # 4. Fact_Inventory_Orders
    orders_merged = df_orders.copy()
    orders_merged = orders_merged.merge(products[["sku_id", "product_key"]], on="sku_id", how="left")
    orders_merged = orders_merged.merge(suppliers[["supplier_id", "supplier_key"]], on="supplier_id", how="left")
    orders_merged = orders_merged.merge(df_wh[["warehouse_code", "warehouse_key"]], on="warehouse_code", how="left")
    
    # Merge stock snapshot
    orders_merged = orders_merged.merge(
        df_snapshot[["sku_id", "warehouse_code", "current_stock_level"]],
        on=["sku_id", "warehouse_code"],
        how="left"
    )
    orders_merged["current_stock_level"] = orders_merged["current_stock_level"].fillna(50).astype(int)
    orders_merged["order_line_key"] = range(1, len(orders_merged) + 1)
    orders_merged["unit_cost_at_order"] = orders_merged["unit_cost"]

    fact_cols = [
        "order_line_key", "order_id", "order_date", "product_key", "supplier_key",
        "warehouse_key", "quantity", "unit_cost_at_order", "order_item_total",
        "scheduled_shipping_days", "actual_shipping_days", "late_delivery_risk",
        "delivered_in_full", "current_stock_level", "shipping_mode", "market"
    ]
    orders_merged[fact_cols].to_sql("Fact_Inventory_Orders", conn, if_exists="replace", index=False)

    return conn

# -----------------------------------------------------------------------------
# LOAD DATA & WAREHOUSE
# -----------------------------------------------------------------------------
try:
    df_metrics, df_scorecard, df_orders, df_snapshot, df_forecast = load_data()
    sql_conn = get_sqlite_warehouse(df_metrics, df_scorecard, df_orders, df_snapshot)
except Exception as e:
    st.error(f"Error initializing data: {e}")
    st.stop()

# -----------------------------------------------------------------------------
# SIDEBAR FILTERS & NAVIGATION
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("""
    <div class="sidebar-brand">
        <h2>📦 DataCo Supply Chain</h2>
        <p>Enterprise Inventory & EOQ Control Tower</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### 🎛️ Global Slicers")

    # Category Filter
    all_categories = sorted(df_metrics["category"].unique())
    selected_categories = st.multiselect(
        "Product Category",
        options=all_categories,
        default=all_categories,
        help="Filters KPIs, Stockout Alerts, and Demand Curves"
    )
    if not selected_categories:
        selected_categories = all_categories

    # Warehouse Filter
    all_warehouses = sorted(df_snapshot["warehouse_code"].unique())
    selected_warehouses = st.multiselect(
        "Distribution Centers",
        options=all_warehouses,
        default=all_warehouses,
        help="Select one or more regional fulfillment hubs"
    )
    if not selected_warehouses:
        selected_warehouses = all_warehouses

    # Date Range Filter
    min_date = df_orders["order_date"].min().date()
    max_date = df_orders["order_date"].max().date()
    selected_date_range = st.date_input(
        "Order Timeline Window",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

    st.markdown("---")
    st.markdown("### 🛠️ Quick Actions")

    # Download Excel model button
    excel_path = os.path.join(APP_DIR, "supply_chain_eoq_calculator.xlsx")
    if os.path.exists(excel_path):
        with open(excel_path, "rb") as f:
            st.download_button(
                label="📥 Download Excel Model (.xlsx)",
                data=f,
                file_name="supply_chain_eoq_calculator.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

    st.markdown("""
    <div style="font-size: 11px; color: #5E6C84; margin-top: 15px; line-height: 1.4;">
        <b>Dataset:</b> DataCo Smart Supply Chain<br>
        <b>Star Schema:</b> 4 Tables &bull; 15,000 Orders<br>
        <b>Palette:</b> Corporate Blue & Slate
    </div>
    """, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# APPLY GLOBAL FILTERS TO DATASETS
# -----------------------------------------------------------------------------
if isinstance(selected_date_range, (tuple, list)) and len(selected_date_range) == 2:
    start_d, end_d = selected_date_range
    filtered_orders = df_orders[
        (df_orders["order_date"].dt.date >= start_d) &
        (df_orders["order_date"].dt.date <= end_d) &
        (df_orders["category"].isin(selected_categories)) &
        (df_orders["warehouse_code"].isin(selected_warehouses))
    ]
else:
    filtered_orders = df_orders[
        (df_orders["category"].isin(selected_categories)) &
        (df_orders["warehouse_code"].isin(selected_warehouses))
    ]

filtered_metrics = df_metrics[df_metrics["category"].isin(selected_categories)].copy()
filtered_snapshot = df_snapshot[
    (df_snapshot["category"].isin(selected_categories)) &
    (df_snapshot["warehouse_code"].isin(selected_warehouses))
].copy()

# -----------------------------------------------------------------------------
# APP HEADER
# -----------------------------------------------------------------------------
st.markdown("""
<div class="enterprise-header">
    <h1>Enterprise Supply Chain & Inventory Optimization Intelligence</h1>
    <p>Real-time inventory positioning, EOQ replenishment planning, supplier OTIF tracking, and warehouse capacity monitoring.</p>
</div>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# MAIN NAVIGATION TABS
# -----------------------------------------------------------------------------
tab_tower, tab_supplier, tab_eoq, tab_forecast, tab_sql = st.tabs([
    "🏢 Executive Control Tower",
    "🚚 Supplier Scorecard & Lead Times",
    "📐 EOQ & Safety Stock Planner",
    "📈 Demand Forecasting & Trends",
    "🗄️ SQL Data Warehouse Analytics",
])

# =============================================================================
# TAB 1: EXECUTIVE CONTROL TOWER (Power BI Page 1 Blueprint)
# =============================================================================
with tab_tower:
    # 1. High-Level Executive KPI Cards
    kpi_col1, kpi_col2, kpi_col3, kpi_col4, kpi_col5 = st.columns(5)
    
    # Measure 1: OTIF %
    tot_orders = len(filtered_orders)
    otif_count = filtered_orders["on_time_in_full"].sum() if tot_orders > 0 else 0
    otif_pct = (otif_count / tot_orders * 100) if tot_orders > 0 else 0.0
    otif_badge = "badge-ok" if otif_pct >= 95 else ("badge-warning" if otif_pct >= 85 else "badge-critical")
    otif_status = "Target Met (≥95%)" if otif_pct >= 95 else ("Acceptable (≥85%)" if otif_pct >= 85 else "Action Required (<85%)")

    # Measure 2: Total Holding Cost
    total_holding_cost = (filtered_snapshot["current_stock_level"] * filtered_snapshot["holding_cost_per_unit"]).sum()

    # Measure 3: Inventory Turnover Ratio
    cogs = filtered_orders["order_item_total"].sum()
    avg_inv_val = (filtered_snapshot["current_stock_level"] * filtered_snapshot["unit_cost"]).sum()
    inv_turnover = (cogs / avg_inv_val) if avg_inv_val > 0 else 0.0

    # Measure 4: Stockout Risk SKU Count
    stockout_skus = (filtered_metrics["stockout_flag"] == "REORDER NOW").sum()
    stockout_badge = "badge-critical" if stockout_skus > 5 else ("badge-warning" if stockout_skus > 0 else "badge-ok")

    # Measure 5: Total Order Value
    total_sales = filtered_orders["order_item_total"].sum()

    with kpi_col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">OTIF Delivery Rate</div>
            <div class="metric-value">{otif_pct:.1f}%</div>
            <div class="metric-sub"><span class="{otif_badge}">{otif_status}</span></div>
        </div>
        """, unsafe_allow_html=True)

    with kpi_col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Total Holding Cost</div>
            <div class="metric-value">${total_holding_cost:,.0f}</div>
            <div class="metric-sub"><span class="badge-info">Active Carrying Cost</span></div>
        </div>
        """, unsafe_allow_html=True)

    with kpi_col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Inventory Turnover</div>
            <div class="metric-value">{inv_turnover:.1f}x</div>
            <div class="metric-sub"><span class="badge-ok">Benchmark: 4x - 8x</span></div>
        </div>
        """, unsafe_allow_html=True)

    with kpi_col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Stockout Risk SKUs</div>
            <div class="metric-value">{stockout_skus}</div>
            <div class="metric-sub"><span class="{stockout_badge}">{stockout_skus} of {len(filtered_metrics)} Below ROP</span></div>
        </div>
        """, unsafe_allow_html=True)

    with kpi_col5:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Total Order Value</div>
            <div class="metric-value">${total_sales/1e6:.2f}M</div>
            <div class="metric-sub"><span class="badge-info">{tot_orders:,} Orders Filtered</span></div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # 2. Main Visual Grid: Warehouse Capacity & Stockout Alerts
    col_wh, col_alerts = st.columns([5, 7])

    with col_wh:
        st.markdown("### 🏭 Warehouse Capacity Utilization")
        st.caption("Distribution Centers capacity tracking vs. 85% operational threshold.")
        
        # Aggregate inventory per warehouse
        wh_summary = []
        for wh_code in selected_warehouses:
            wh_info = WAREHOUSE_METADATA.get(wh_code, {"name": wh_code, "max_capacity": 50000})
            units = filtered_snapshot[filtered_snapshot["warehouse_code"] == wh_code]["current_stock_level"].sum()
            cap = wh_info["max_capacity"]
            util_pct = (units / cap * 100) if cap > 0 else 0
            wh_summary.append({
                "Warehouse": wh_code,
                "Name": wh_info["name"].split(" Distribution")[0],
                "Units Stored": units,
                "Max Capacity": cap,
                "Utilization %": round(util_pct, 1),
                "Status": "OVER CAPACITY (>85%)" if util_pct > 85 else ("APPROACHING (>70%)" if util_pct > 70 else "HEALTHY")
            })
        df_wh_summary = pd.DataFrame(wh_summary)

        # Plotly Bar Chart for Warehouse Utilization
        fig_wh = go.Figure()
        
        colors = [
            "#FF5630" if u > 85 else ("#FFAB00" if u > 70 else "#0052CC")
            for u in df_wh_summary["Utilization %"]
        ]

        fig_wh.add_trace(go.Bar(
            x=df_wh_summary["Warehouse"],
            y=df_wh_summary["Utilization %"],
            text=[f"{u:.1f}%<br>({s:,} units)" for u, s in zip(df_wh_summary["Utilization %"], df_wh_summary["Units Stored"])],
            textposition="auto",
            marker_color=colors,
            hoverinfo="x+y+text"
        ))

        # 85% Warning threshold line
        fig_wh.add_shape(
            type="line",
            x0=-0.5,
            x1=len(df_wh_summary) - 0.5,
            y0=85,
            y1=85,
            line=dict(color="#BF2600", width=2, dash="dash")
        )
        fig_wh.add_annotation(
            x=len(df_wh_summary) - 1,
            y=88,
            text="85% Risk Threshold",
            showarrow=False,
            font=dict(color="#BF2600", size=11, family="sans-serif")
        )

        fig_wh.update_layout(
            height=360,
            margin=dict(l=10, r=10, t=25, b=10),
            plot_bgcolor="#FFFFFF",
            paper_bgcolor="#FFFFFF",
            yaxis=dict(title="Utilization %", range=[0, 110], gridcolor="#DFE1E6"),
            xaxis=dict(title=None, tickfont=dict(color="#172B4D")),
            font=dict(color="#172B4D")
        )
        st.plotly_chart(fig_wh, use_container_width=True)

        # Quick summary table for warehouses
        st.dataframe(
            df_wh_summary[["Warehouse", "Units Stored", "Max Capacity", "Utilization %", "Status"]],
            hide_index=True,
            use_container_width=True
        )

    with col_alerts:
        st.markdown("### ⚠️ SKU Stockout Alert & Triage Table")
        st.caption("Matches Deliverable 3 Query 1: Flagging SKUs below Safety Stock or Reorder Point.")

        # Prepare SKU stockout metrics
        triage_df = filtered_metrics[[
            "sku_id", "product_name", "category", "current_stock_level",
            "safety_stock_units", "reorder_point_units", "units_below_rop",
            "unit_cost", "stockout_flag"
        ]].copy()

        triage_df["estimated_reorder_value"] = (triage_df["units_below_rop"] * triage_df["unit_cost"]).round(2)
        
        # Classification
        def classify_stock(row):
            if row["current_stock_level"] <= row["safety_stock_units"]:
                return "CRITICAL - BELOW SAFETY STOCK"
            elif row["current_stock_level"] < row["reorder_point_units"]:
                return "REORDER NOW"
            return "OK - HEALTHY"

        triage_df["stock_status"] = triage_df.apply(classify_stock, axis=1)
        triage_df = triage_df.sort_values(by=["units_below_rop", "estimated_reorder_value"], ascending=[False, False])

        # Filter option for table
        status_filter = st.radio(
            "Filter Status:",
            ["All SKUs", "Needs Action Only (Critical & Reorder)", "Critical Only"],
            horizontal=True
        )
        if status_filter == "Needs Action Only (Critical & Reorder)":
            display_triage = triage_df[triage_df["stock_status"] != "OK - HEALTHY"]
        elif status_filter == "Critical Only":
            display_triage = triage_df[triage_df["stock_status"].str.startswith("CRITICAL")]
        else:
            display_triage = triage_df

        st.dataframe(
            display_triage[[
                "sku_id", "product_name", "category", "current_stock_level",
                "safety_stock_units", "reorder_point_units", "units_below_rop",
                "estimated_reorder_value", "stock_status"
            ]].rename(columns={
                "sku_id": "SKU",
                "product_name": "Product",
                "category": "Category",
                "current_stock_level": "Current Stock",
                "safety_stock_units": "Safety Stock",
                "reorder_point_units": "ROP",
                "units_below_rop": "Deficit",
                "estimated_reorder_value": "Reorder Value ($)",
                "stock_status": "Status"
            }),
            height=360,
            hide_index=True,
            use_container_width=True
        )

        csv_triage = display_triage.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Export Triage List (.csv)",
            data=csv_triage,
            file_name="stockout_triage_actions.csv",
            mime="text/csv"
        )

# =============================================================================
# TAB 2: SUPPLIER SCORECARD & LEAD TIME ANALYSIS (Power BI Page 2 Blueprint)
# =============================================================================
with tab_supplier:
    st.markdown("### 🚚 Supplier Performance & Contracted vs. Actual Lead Times")
    st.caption("Analyze on-time delivery rates, lead-time variance, and category-level supplier rankings.")

    # 1. Tier Summary Cards
    tier_counts = df_scorecard["performance_tier"].value_counts().to_dict()
    tier_cols = st.columns(4)
    tiers_info = [
        ("A - Preferred", "badge-ok", "OTIF ≥ 95%", "#36B37E"),
        ("B - Acceptable", "badge-info", "OTIF 85% - 94%", "#0052CC"),
        ("C - Watch List", "badge-warning", "OTIF 70% - 84%", "#FFAB00"),
        ("D - At Risk", "badge-critical", "OTIF < 70%", "#FF5630"),
    ]

    for col, (t_name, badge_cls, desc, hex_color) in zip(tier_cols, tiers_info):
        cnt = tier_counts.get(t_name, 0)
        with col:
            st.markdown(f"""
            <div class="metric-card" style="border-left: 5px solid {hex_color};">
                <div class="metric-label">{t_name}</div>
                <div class="metric-value">{cnt} Suppliers</div>
                <div class="metric-sub"><span class="{badge_cls}">{desc}</span></div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # 2. Scatter Plot: Scheduled Lead Time vs Actual Shipping Days (Deliverable 3 Query 2 & Spec)
    st.markdown("#### 📍 Scheduled Lead Time vs. Actual Shipping Days (Parity Chart)")
    st.caption("Points above the 45° red parity line indicate chronic shipping delays. Bubble size represents Total Order Value.")

    # Aggregate orders by supplier for scatter plot
    supplier_agg = filtered_orders.groupby("supplier_id").agg(
        scheduled_lead=("scheduled_shipping_days", "mean"),
        actual_lead=("actual_shipping_days", "mean"),
        total_orders=("order_id", "count"),
        total_value=("order_item_total", "sum"),
        late_rate=("late_delivery_risk", "mean"),
        otif=("on_time_in_full", "mean")
    ).reset_index()

    supplier_agg = supplier_agg.merge(df_scorecard[["supplier_id", "performance_tier"]], on="supplier_id", how="left")
    supplier_agg["lead_variance"] = supplier_agg["actual_lead"] - supplier_agg["scheduled_lead"]
    supplier_agg["otif_pct"] = (supplier_agg["otif"] * 100).round(1)

    max_axis = max(supplier_agg["scheduled_lead"].max(), supplier_agg["actual_lead"].max()) + 2

    fig_scatter = go.Figure()

    # 45-degree parity line
    fig_scatter.add_trace(go.Scatter(
        x=[0, max_axis],
        y=[0, max_axis],
        mode="lines",
        line=dict(color="#FF5630", dash="dash", width=2),
        name="Perfect On-Time Parity (y = x)",
        hoverinfo="name"
    ))

    # Supplier points
    tier_palette = {
        "A - Preferred": "#36B37E",
        "B - Acceptable": "#0052CC",
        "C - Watch List": "#FFAB00",
        "D - At Risk": "#FF5630"
    }

    for tier, group in supplier_agg.groupby("performance_tier"):
        fig_scatter.add_trace(go.Scatter(
            x=group["scheduled_lead"],
            y=group["actual_lead"],
            mode="markers+text",
            name=tier,
            text=group["supplier_id"],
            textposition="top center",
            marker=dict(
                size=group["total_value"] / 35000,
                color=tier_palette.get(tier, "#0052CC"),
                opacity=0.85,
                line=dict(width=1, color="#172B4D")
            ),
            hovertemplate=(
                "<b>%{text}</b> (%{data.name})<br>" +
                "Scheduled Lead: %{x:.2f} days<br>" +
                "Actual Lead: %{y:.2f} days<br>" +
                "Variance: +%{customdata[0]:.2f} days<br>" +
                "OTIF: %{customdata[1]}%<br>" +
                "Total Value: $%{customdata[2]:,.0f}<extra></extra>"
            ),
            customdata=group[["lead_variance", "otif_pct", "total_value"]].values
        ))

    fig_scatter.update_layout(
        height=450,
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis=dict(title="Contracted / Scheduled Lead Time (Days)", gridcolor="#DFE1E6", range=[0, max_axis]),
        yaxis=dict(title="Actual Observed Shipping Days (Days)", gridcolor="#DFE1E6", range=[0, max_axis]),
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        font=dict(color="#172B4D"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

    # 3. Bar Charts: Late Delivery % and Category Rank Table
    col_bar, col_rank = st.columns([6, 6])

    with col_bar:
        st.markdown("#### 📊 Supplier OTIF & Late Delivery Rates")
        scorecard_sorted = df_scorecard.sort_values(by="otif_pct", ascending=True)

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            y=scorecard_sorted["supplier_id"],
            x=scorecard_sorted["otif_pct"],
            orientation='h',
            name="OTIF %",
            marker_color="#0052CC",
            text=[f"{v:.1f}%" for v in scorecard_sorted["otif_pct"]],
            textposition="inside"
        ))
        fig_bar.add_trace(go.Bar(
            y=scorecard_sorted["supplier_id"],
            x=scorecard_sorted["late_delivery_rate_pct"],
            orientation='h',
            name="Late Delivery %",
            marker_color="#FF5630",
            text=[f"{v:.1f}%" for v in scorecard_sorted["late_delivery_rate_pct"]],
            textposition="inside"
        ))
        fig_bar.update_layout(
            barmode="group",
            height=380,
            margin=dict(l=20, r=20, t=25, b=20),
            plot_bgcolor="#FFFFFF",
            paper_bgcolor="#FFFFFF",
            xaxis=dict(title="Percentage (%)", range=[0, 105], gridcolor="#DFE1E6"),
            yaxis=dict(title=None),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            font=dict(color="#172B4D")
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_rank:
        st.markdown("#### 🏆 Category-Level Supplier Delay Ranking")
        st.caption("SQL Window Function: RANK() OVER (PARTITION BY category ORDER BY avg_delay_days DESC)")
        
        cat_supplier = filtered_orders.groupby(["category", "supplier_id"]).agg(
            total_orders=("order_id", "count"),
            avg_delay=("lead_time_variance", "mean"),
            otif_rate=("on_time_in_full", "mean")
        ).reset_index()

        cat_supplier["avg_delay"] = cat_supplier["avg_delay"].round(2)
        cat_supplier["otif_pct"] = (cat_supplier["otif_rate"] * 100).round(1)
        cat_supplier["delay_rank"] = cat_supplier.groupby("category")["avg_delay"].rank(ascending=False, method="min").astype(int)
        
        # Display top delay risks
        worst_delays = cat_supplier[cat_supplier["delay_rank"] == 1].sort_values("avg_delay", ascending=False)
        st.dataframe(
            worst_delays[["category", "supplier_id", "total_orders", "avg_delay", "otif_pct"]].rename(columns={
                "category": "Category",
                "supplier_id": "Worst Supplier",
                "total_orders": "Orders",
                "avg_delay": "Avg Delay (Days)",
                "otif_pct": "OTIF %"
            }),
            hide_index=True,
            use_container_width=True
        )
        
        st.info("💡 **Recommendation:** Suppliers ranked #1 in category delay should be prioritized for lead-time renegotiation or dual-sourcing.")

# =============================================================================
# TAB 3: EOQ & SAFETY STOCK PLANNER (Excel Layer Deliverable 1)
# =============================================================================
with tab_eoq:
    st.markdown("### 📐 Economic Order Quantity (EOQ) & Safety Stock Simulator")
    st.caption("Interactive formula model mirroring supply_chain_eoq_calculator.xlsx. Select an existing SKU or enter custom parameters.")

    # SKU Selector to pre-populate inputs
    col_sku_sel, col_mode = st.columns([4, 2])
    with col_sku_sel:
        selected_sku_for_eoq = st.selectbox(
            "Load Parameters from SKU:",
            options=df_metrics["sku_id"].tolist(),
            format_func=lambda s: f"{s} - {df_metrics[df_metrics['sku_id'] == s]['product_name'].iloc[0]} ({df_metrics[df_metrics['sku_id'] == s]['category'].iloc[0]})"
        )

    sku_row = df_metrics[df_metrics["sku_id"] == selected_sku_for_eoq].iloc[0]

    st.markdown("#### 📝 Model Assumptions & Inputs")
    p_col1, p_col2, p_col3, p_col4 = st.columns(4)

    with p_col1:
        annual_demand = st.number_input(
            "Annual Demand (D, units/yr)",
            min_value=100,
            max_value=100000,
            value=int(sku_row["avg_daily_demand"] * 365),
            step=250,
            help="Total annual customer demand in units"
        )
        unit_cost_input = st.number_input(
            "Unit Cost ($)",
            min_value=1.0,
            max_value=5000.0,
            value=float(sku_row["unit_cost"]),
            step=5.0
        )

    with p_col2:
        ordering_cost = st.number_input(
            "Ordering Cost (S, $/order)",
            min_value=5.0,
            max_value=1000.0,
            value=50.0,
            step=5.0,
            help="Fixed procurement & administrative cost per purchase order"
        )
        holding_cost_unit = st.number_input(
            "Holding Cost (H, $/unit/yr)",
            min_value=0.1,
            max_value=500.0,
            value=float(sku_row["holding_cost_per_unit"]),
            step=0.5,
            help="Carrying cost: capital cost, warehousing, insurance, obsolescence"
        )

    with p_col3:
        avg_lead_time = st.number_input(
            "Avg Lead Time (Days)",
            min_value=1.0,
            max_value=60.0,
            value=float(sku_row["avg_lead_time_days"]),
            step=0.5
        )
        max_lead_time = st.number_input(
            "Max Lead Time (Days)",
            min_value=1.0,
            max_value=90.0,
            value=float(sku_row["max_lead_time_days"]),
            step=1.0
        )

    with p_col4:
        service_level = st.selectbox(
            "Target Service Level (Z)",
            options=[(90, 1.28), (95, 1.65), (98, 2.05), (99, 2.33)],
            format_func=lambda x: f"{x[0]}% Service Level (Z = {x[1]})",
            index=1
        )
        z_score = service_level[1]
        
        avg_daily_d = st.number_input(
            "Avg Daily Demand",
            min_value=1.0,
            max_value=500.0,
            value=float(sku_row["avg_daily_demand"]),
            step=1.0
        )
        std_daily_d = st.number_input(
            "Std Dev Daily Demand",
            min_value=0.1,
            max_value=200.0,
            value=float(sku_row["std_daily_demand"]),
            step=0.5
        )

    # ------------------ FORMULA CALCULATIONS ------------------
    # EOQ = SQRT((2 * D * S) / H)
    eoq = math.sqrt((2 * annual_demand * ordering_cost) / holding_cost_unit)
    orders_per_year = annual_demand / eoq
    cycle_days = 365 / orders_per_year

    # Annual Cost components
    annual_order_cost = orders_per_year * ordering_cost
    annual_hold_cost = (eoq / 2) * holding_cost_unit
    total_policy_cost = annual_order_cost + annual_hold_cost

    # Safety Stock Calculations
    # 1. Statistical: Z * sigma * sqrt(L)
    ss_statistical = z_score * std_daily_d * math.sqrt(avg_lead_time)
    
    # 2. Deterministic: (Max D * Max L) - (Avg D * Avg L)
    max_daily_d = float(sku_row["max_daily_demand"])
    ss_deterministic = max(0, (max_daily_d * max_lead_time) - (avg_daily_d * avg_lead_time))

    # Reorder Point: (Avg D * Avg L) + Safety Stock
    rop = (avg_daily_d * avg_lead_time) + ss_statistical
    days_of_supply_rop = rop / avg_daily_d if avg_daily_d > 0 else 0

    st.markdown("---")
    st.markdown("#### ⚡ Calculated Policy Results")

    res_col1, res_col2, res_col3, res_col4 = st.columns(4)

    with res_col1:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 4px solid #0052CC;">
            <div class="metric-label">Economic Order Qty (EOQ)</div>
            <div class="metric-value">{eoq:,.0f} units</div>
            <div class="metric-sub"><span class="badge-info">{orders_per_year:.1f} orders/year &bull; every {cycle_days:.0f} days</span></div>
        </div>
        """, unsafe_allow_html=True)

    with res_col2:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 4px solid #0052CC;">
            <div class="metric-label">Reorder Point (ROP)</div>
            <div class="metric-value">{rop:,.0f} units</div>
            <div class="metric-sub"><span class="badge-info">{days_of_supply_rop:.1f} Days of Supply at trigger</span></div>
        </div>
        """, unsafe_allow_html=True)

    with res_col3:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 4px solid #36B37E;">
            <div class="metric-label">Statistical Safety Stock</div>
            <div class="metric-value">{ss_statistical:,.0f} units</div>
            <div class="metric-sub"><span class="badge-ok">Z = {z_score} ({service_level[0]}% protection)</span></div>
        </div>
        """, unsafe_allow_html=True)

    with res_col4:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 4px solid #0052CC;">
            <div class="metric-label">Total Annual Policy Cost</div>
            <div class="metric-value">${total_policy_cost:,.2f}</div>
            <div class="metric-sub"><span class="badge-info">Hold: ${annual_hold_cost:,.0f} | Order: ${annual_order_cost:,.0f}</span></div>
        </div>
        """, unsafe_allow_html=True)

    # EOQ Total Cost Curve Visualization
    st.markdown("#### 📈 EOQ Cost Trade-off Curve")
    st.caption("Visual proof of the EOQ minimum: Total Carrying Cost + Ordering Cost reaches global minimum where Holding Cost equals Ordering Cost.")

    q_range = np.linspace(max(10, eoq * 0.2), eoq * 2.5, 100)
    curve_holding = (q_range / 2) * holding_cost_unit
    curve_ordering = (annual_demand / q_range) * ordering_cost
    curve_total = curve_holding + curve_ordering

    fig_eoq = go.Figure()
    fig_eoq.add_trace(go.Scatter(x=q_range, y=curve_total, mode='lines', name='Total Inventory Cost', line=dict(color='#0052CC', width=3)))
    fig_eoq.add_trace(go.Scatter(x=q_range, y=curve_holding, mode='lines', name='Annual Holding Cost', line=dict(color='#36B37E', width=2, dash='dot')))
    fig_eoq.add_trace(go.Scatter(x=q_range, y=curve_ordering, mode='lines', name='Annual Ordering Cost', line=dict(color='#FF5630', width=2, dash='dash')))

    # Add optimal EOQ marker
    fig_eoq.add_trace(go.Scatter(
        x=[eoq],
        y=[total_policy_cost],
        mode='markers+text',
        name='Optimal EOQ (Q*)',
        text=[f"Optimal EOQ = {eoq:.0f} units<br>Min Cost = ${total_policy_cost:,.0f}"],
        textposition="top center",
        marker=dict(size=12, color='#0052CC', symbol='diamond')
    ))

    fig_eoq.update_layout(
        height=380,
        margin=dict(l=20, r=20, t=20, b=20),
        xaxis=dict(title='Order Quantity (Q, units)', gridcolor='#DFE1E6'),
        yaxis=dict(title='Annual Cost ($)', gridcolor='#DFE1E6'),
        plot_bgcolor='#FFFFFF',
        paper_bgcolor='#FFFFFF',
        font=dict(color='#172B4D'),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_eoq, use_container_width=True)

# =============================================================================
# TAB 4: DEMAND FORECASTING & TRENDS (Deliverable 2 Step 3)
# =============================================================================
with tab_forecast:
    st.markdown("### 📈 Time-Series Demand Analysis & 3-Month Moving Average Forecast")
    st.caption("Monthly historical demand units by category with trailing 3-month rolling average baseline.")

    # Filter forecast data
    filtered_forecast = df_forecast[df_forecast["category"].isin(selected_categories)].copy()

    # Category Selector
    col_fc_cat, col_fc_info = st.columns([4, 8])
    with col_fc_cat:
        forecast_cat = st.selectbox(
            "Select Category for Deep Dive:",
            options=selected_categories
        )

    cat_fc_data = filtered_forecast[filtered_forecast["category"] == forecast_cat].sort_values("order_month")

    # Time-series Plotly Chart
    fig_fc = go.Figure()

    fig_fc.add_trace(go.Bar(
        x=cat_fc_data["order_month"],
        y=cat_fc_data["monthly_demand_units"],
        name="Actual Monthly Demand (Units)",
        marker_color="#DEEBFF",
        marker_line=dict(color="#0052CC", width=1.5),
        opacity=0.85
    ))

    fig_fc.add_trace(go.Scatter(
        x=cat_fc_data["order_month"],
        y=cat_fc_data["moving_avg_3mo_demand"],
        name="3-Month Moving Average",
        mode="lines+markers",
        line=dict(color="#0052CC", width=3),
        marker=dict(size=6, color="#0052CC")
    ))

    fig_fc.update_layout(
        height=420,
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis=dict(title="Order Month", tickangle=-45, gridcolor="#DFE1E6"),
        yaxis=dict(title="Demand (Units)", gridcolor="#DFE1E6"),
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        font=dict(color="#172B4D"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_fc, use_container_width=True)

    # Category Summary Table across all selected categories
    st.markdown("#### 📋 Latest Category Demand Projections & Volatility")
    latest_cat_summary = (
        filtered_forecast.sort_values("order_month")
        .groupby("category")
        .tail(1)[["category", "order_month", "monthly_demand_units", "forecast_next_month_units", "demand_std_dev_3mo"]]
        .rename(columns={
            "category": "Category",
            "order_month": "Latest Month",
            "monthly_demand_units": "Latest Demand (Units)",
            "forecast_next_month_units": "Next Month Forecast (Units)",
            "demand_std_dev_3mo": "3-Mo Volatility (Std Dev)"
        })
    )
    st.dataframe(latest_cat_summary, hide_index=True, use_container_width=True)

# =============================================================================
# TAB 5: SQL DATA WAREHOUSE ANALYTICS (Deliverable 3 Live Explorer)
# =============================================================================
with tab_sql:
    st.markdown("### 🗄️ SQL Data Warehousing & Analytical Queries")
    st.caption("Interactive execution of the star schema queries defined in schema_and_queries.sql.")

    query_selection = st.selectbox(
        "Choose Analytical Query to Execute:",
        [
            "Query 1: Stockout Alert Query (Deliverable 3, Section 2)",
            "Query 2: Supplier Lead Time Deviation & Ranking (Deliverable 3, Section 3)",
            "Query 3: Warehouse Capacity Utilization (Deliverable 3, Section 4)",
            "Custom SQL Query..."
        ]
    )

    sql_q1 = """
    WITH latest_stock_snapshot AS (
        SELECT 
            f.product_key,
            f.warehouse_key,
            f.current_stock_level,
            MAX(f.order_date) AS snapshot_date
        FROM Fact_Inventory_Orders f
        GROUP BY f.product_key, f.warehouse_key
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
        (p.reorder_point_units - s.current_stock_level) AS units_below_rop,
        ROUND(p.unit_cost * (p.reorder_point_units - s.current_stock_level), 2) AS estimated_reorder_value,
        CASE
            WHEN s.current_stock_level <= p.safety_stock_units THEN 'CRITICAL - BELOW SAFETY STOCK'
            WHEN s.current_stock_level < p.reorder_point_units THEN 'REORDER NOW'
            ELSE 'OK'
        END AS stock_status,
        s.snapshot_date
    FROM latest_stock_snapshot s
    JOIN Dim_Products p ON p.product_key = s.product_key
    JOIN Dim_Warehouses w ON w.warehouse_key = s.warehouse_key
    WHERE s.current_stock_level < p.reorder_point_units
    ORDER BY 
        CASE WHEN s.current_stock_level <= p.safety_stock_units THEN 0 ELSE 1 END,
        units_below_rop DESC;
    """

    sql_q2 = """
    WITH supplier_category_performance AS (
        SELECT
            p.category,
            s.supplier_id,
            s.supplier_name,
            COUNT(*) AS total_orders,
            ROUND(AVG(f.actual_shipping_days - f.scheduled_shipping_days), 2) AS avg_delay_days,
            ROUND(100.0 * SUM(f.late_delivery_risk) / COUNT(*), 2) AS late_delivery_rate_pct,
            ROUND(100.0 * SUM(CASE WHEN f.late_delivery_risk = 0 AND f.delivered_in_full = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS otif_pct
        FROM Fact_Inventory_Orders f
        JOIN Dim_Products p ON p.product_key = f.product_key
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
        RANK() OVER (PARTITION BY category ORDER BY avg_delay_days DESC) AS delay_rank_in_category,
        DENSE_RANK() OVER (PARTITION BY category ORDER BY otif_pct ASC) AS otif_risk_rank_in_category
    FROM supplier_category_performance
    ORDER BY category, delay_rank_in_category;
    """

    sql_q3 = """
    WITH latest_stock_snapshot AS (
        SELECT 
            f.product_key,
            f.warehouse_key,
            f.current_stock_level
        FROM Fact_Inventory_Orders f
        GROUP BY f.product_key, f.warehouse_key
    ),
    warehouse_inventory AS (
        SELECT
            w.warehouse_key,
            w.warehouse_code,
            w.warehouse_name,
            w.max_capacity_units,
            w.monthly_operating_cost,
            SUM(s.current_stock_level) AS total_units_stored,
            SUM(s.current_stock_level * p.holding_cost_per_unit) AS total_holding_cost
        FROM latest_stock_snapshot s
        JOIN Dim_Products p ON p.product_key = s.product_key
        JOIN Dim_Warehouses w ON w.warehouse_key = s.warehouse_key
        GROUP BY w.warehouse_key, w.warehouse_code, w.warehouse_name, w.max_capacity_units, w.monthly_operating_cost
    )
    SELECT
        warehouse_code,
        warehouse_name,
        total_units_stored,
        max_capacity_units,
        ROUND(100.0 * total_units_stored / max_capacity_units, 2) AS utilization_pct,
        ROUND(total_holding_cost, 2) AS total_holding_cost,
        monthly_operating_cost,
        ROUND(total_holding_cost + monthly_operating_cost, 2) AS total_warehouse_carrying_cost,
        CASE
            WHEN 100.0 * total_units_stored / max_capacity_units > 85 THEN 'OVER CAPACITY - ACTION REQUIRED'
            WHEN 100.0 * total_units_stored / max_capacity_units > 70 THEN 'APPROACHING CAPACITY'
            ELSE 'HEALTHY'
        END AS capacity_status
    FROM warehouse_inventory;
    """

    if "Query 1" in query_selection:
        chosen_sql = sql_q1
    elif "Query 2" in query_selection:
        chosen_sql = sql_q2
    elif "Query 3" in query_selection:
        chosen_sql = sql_q3
    else:
        chosen_sql = st.text_area(
            "Enter SQL statement (SQLite dialect):",
            value="SELECT * FROM Dim_Products LIMIT 10;",
            height=150
        )

    st.code(chosen_sql.strip(), language="sql")

    try:
        sql_res = pd.read_sql_query(chosen_sql, sql_conn)
        st.success(f"Query returned {len(sql_res)} rows.")
        st.dataframe(sql_res, use_container_width=True)
    except Exception as err:
        st.error(f"SQL execution error: {err}")

# -----------------------------------------------------------------------------
# FOOTER
# -----------------------------------------------------------------------------
st.markdown("---")
st.markdown("""
<div style="text-align: center; font-size: 12px; color: #5E6C84; padding: 12px 0;">
    Enterprise Supply Chain & Inventory Optimization Intelligence &bull; Powered by Streamlit, Python & SQL
</div>
""", unsafe_allow_html=True)
