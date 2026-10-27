"""
generate_excel_model.py
------------------------------------------------------------------------------
Enterprise Supply Chain & Inventory Optimization Intelligence
Deliverable 1: Excel Generation Script

Builds a fully formatted, formula-driven Excel workbook named
'supply_chain_eoq_calculator.xlsx' with three tabs:

    1. EOQ_Calculator          - Economic Order Quantity + Safety Stock formulas
    2. Reorder_Point_Model     - Reorder Point (ROP) formulas across 10 SKUs
    3. Holding_vs_Stockout_Cost- Cost trade-off model (holding vs. stockout risk)

All calculated values are LIVE EXCEL FORMULAS (never hardcoded Python results),
so the workbook recalculates automatically when any input cell changes.

Run:
    python generate_excel_model.py

Output:
    supply_chain_eoq_calculator.xlsx  (written to the current working directory)

Dependencies:
    pip install openpyxl
------------------------------------------------------------------------------
"""

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import CellIsRule
from openpyxl.worksheet.worksheet import Worksheet

# ------------------------------------------------------------------------------
# GLOBAL STYLE CONSTANTS
# ------------------------------------------------------------------------------
FONT_NAME = "Arial"

TITLE_FONT = Font(name=FONT_NAME, size=16, bold=True, color="FFFFFF")
TITLE_FILL = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")

SUBTITLE_FONT = Font(name=FONT_NAME, size=10, italic=True, color="595959")

HEADER_FONT = Font(name=FONT_NAME, size=11, bold=True, color="FFFFFF")
HEADER_FILL = PatternFill(start_color="2E75B6", end_color="2E75B6", fill_type="solid")

SECTION_FONT = Font(name=FONT_NAME, size=12, bold=True, color="1F4E78")
SECTION_FILL = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")

INPUT_FONT = Font(name=FONT_NAME, size=11, color="0000FF")          # blue = hardcoded input
FORMULA_FONT = Font(name=FONT_NAME, size=11, color="000000")        # black = formula
LINK_FONT = Font(name=FONT_NAME, size=11, color="008000")           # green = cross-sheet link
ASSUMPTION_FILL = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")  # yellow = key assumption

LABEL_FONT = Font(name=FONT_NAME, size=11, bold=True)
NOTE_FONT = Font(name=FONT_NAME, size=9, italic=True, color="808080")

THIN_BORDER = Border(
    left=Side(style="thin", color="BFBFBF"),
    right=Side(style="thin", color="BFBFBF"),
    top=Side(style="thin", color="BFBFBF"),
    bottom=Side(style="thin", color="BFBFBF"),
)

CURRENCY_FMT = '$#,##0.00;($#,##0.00);"-"'
CURRENCY_FMT_0DP = '$#,##0;($#,##0);"-"'
NUMBER_FMT = '#,##0'
NUMBER_FMT_1DP = '#,##0.0'
PERCENT_FMT = '0.0%'

CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(horizontal="left", vertical="center")


def style_title(ws: Worksheet, cell_range: str, text: str, subtitle: str = ""):
    """Adds a banner title on row 1 and an optional subtitle on row 2, each merged
    across the same column span as the given range (e.g. 'A1:K2' -> title in A1:K1,
    subtitle in A2:K2)."""
    start_cell, end_cell = cell_range.split(":")
    start_col = "".join(ch for ch in start_cell if ch.isalpha())
    end_col = "".join(ch for ch in end_cell if ch.isalpha())
    start_row = int("".join(ch for ch in start_cell if ch.isdigit()))
    end_row = int("".join(ch for ch in end_cell if ch.isdigit()))

    title_range = f"{start_col}{start_row}:{end_col}{start_row}"
    ws.merge_cells(title_range)
    title_cell = f"{start_col}{start_row}"
    ws[title_cell] = text
    ws[title_cell].font = TITLE_FONT
    ws[title_cell].fill = TITLE_FILL
    ws[title_cell].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[start_row].height = 28

    if subtitle and end_row > start_row:
        sub_row = start_row + 1
        sub_range = f"{start_col}{sub_row}:{end_col}{sub_row}"
        ws.merge_cells(sub_range)
        sub_cell = f"{start_col}{sub_row}"
        ws[sub_cell] = subtitle
        ws[sub_cell].font = SUBTITLE_FONT
        ws[sub_cell].alignment = Alignment(horizontal="left", vertical="center", indent=1)


def style_header_row(ws: Worksheet, row: int, start_col: int, end_col: int):
    for col in range(start_col, end_col + 1):
        c = ws.cell(row=row, column=col)
        c.font = HEADER_FONT
        c.fill = HEADER_FILL
        c.alignment = CENTER
        c.border = THIN_BORDER
    ws.row_dimensions[row].height = 32


def apply_border_range(ws: Worksheet, start_row, end_row, start_col, end_col):
    for r in range(start_row, end_row + 1):
        for c in range(start_col, end_col + 1):
            ws.cell(row=r, column=c).border = THIN_BORDER


def autosize_columns(ws: Worksheet, widths: dict):
    for col_letter, width in widths.items():
        ws.column_dimensions[col_letter].width = width


# ------------------------------------------------------------------------------
# SAMPLE SKU DATA (10 SKUs) — INPUT ASSUMPTIONS
# Mirrors the "DataCo Smart Supply Chain for Big Data" product/category structure
# ------------------------------------------------------------------------------
SKU_DATA = [
    # SKU_ID, Product Name,              Category,               Annual_Demand, Ordering_Cost, Holding_Cost_Per_Unit, Max_Daily_Demand, Avg_Daily_Demand, Max_Lead_Time_Days, Avg_Lead_Time_Days, Unit_Cost
    ("SKU-1001", "Diamondback Bike",        "Fitness",              4200,  75.00, 6.20, 28, 12,  9, 5, 185.00),
    ("SKU-1002", "Perfect Fitness Trainer", "Fitness",              6100,  60.00, 3.10, 35, 17,  8, 4,  58.00),
    ("SKU-1003", "Nike Men's Shorts",       "Apparel",              9800,  40.00, 1.85, 55, 27,  6, 3,  22.50),
    ("SKU-1004", "Field & Stream Tent",     "Outdoor",              2300,  90.00, 8.40, 18,  7, 11, 6, 210.00),
    ("SKU-1005", "Under Armour Hoodie",     "Apparel",              7400,  45.00, 2.40, 42, 20,  7, 4,  34.00),
    ("SKU-1006", "Yoga Mat Premium",        "Fitness",              5600,  35.00, 1.20, 32, 15,  5, 3,  18.00),
    ("SKU-1007", "Coleman Cooler 50QT",     "Outdoor",              3100,  70.00, 5.60, 22,  9, 10, 5, 120.00),
    ("SKU-1008", "Wilson Golf Balls (Dz)",  "Sports Equipment",     8900,  30.00, 0.95, 48, 24,  6, 3,  15.00),
    ("SKU-1009", "Nike Dri-FIT Polo",       "Apparel",              6700,  38.00, 2.10, 38, 18,  7, 4,  28.00),
    ("SKU-1010", "Garmin Running Watch",    "Electronics",          2900, 110.00, 14.75, 16,  8, 12, 6, 249.00),
]

STOCKOUT_DATA = [
    # SKU_ID, Current_Stock, Selling_Price, Stockout_Prob_%, Customer_Loss_Factor(%), Avg_Daily_Demand, Holding_Cost_Per_Unit, Unit_Cost
    ("SKU-1001", 60,  299.99, 12, 8, 12, 6.20, 185.00),
    ("SKU-1002", 90,   89.99, 18, 6, 17, 3.10,  58.00),
    ("SKU-1003", 140,  34.99, 25, 4, 27, 1.85,  22.50),
    ("SKU-1004", 40,  349.99,  9, 10,  7, 8.40, 210.00),
    ("SKU-1005", 110,  54.99, 20, 5, 20, 2.40,  34.00),
    ("SKU-1006", 75,   29.99, 15, 3, 15, 1.20,  18.00),
    ("SKU-1007", 45,  199.99, 11, 7,  9, 5.60, 120.00),
    ("SKU-1008", 130,  24.99, 30, 2, 24, 0.95,  15.00),
    ("SKU-1009", 95,   44.99, 17, 5, 18, 2.10,  28.00),
    ("SKU-1010", 35,  399.99,  8, 12,  8, 14.75, 249.00),
]


# ------------------------------------------------------------------------------
# SHEET 1: EOQ_Calculator
# ------------------------------------------------------------------------------
def build_eoq_sheet(wb: Workbook):
    ws = wb.active
    ws.title = "EOQ_Calculator"

    style_title(
        ws, "A1:K2",
        "Economic Order Quantity (EOQ) & Safety Stock Calculator",
        "EOQ = SQRT((2 x Annual Demand x Ordering Cost) / Holding Cost)   |   "
        "Safety Stock = (Max Daily Demand x Max Lead Time) - (Avg Daily Demand x Avg Lead Time)"
    )

    # Legend
    ws["A4"] = "Legend:"
    ws["A4"].font = LABEL_FONT
    ws["B4"] = "Blue = input cell (editable)"
    ws["B4"].font = INPUT_FONT
    ws["D4"] = "Black = live formula"
    ws["D4"].font = FORMULA_FONT
    ws["F4"] = "Yellow = key assumption"
    ws["F4"].fill = ASSUMPTION_FILL
    ws["F4"].font = LABEL_FONT

    headers = [
        "SKU_ID", "Product Name", "Category", "Annual Demand\n(units/yr)",
        "Ordering Cost\n($/order)", "Holding Cost\n($/unit/yr)", "EOQ\n(units/order)",
        "Max Daily\nDemand", "Avg Daily\nDemand", "Max Lead\nTime (days)",
        "Avg Lead\nTime (days)", "Safety\nStock (units)"
    ]
    header_row = 6
    for i, h in enumerate(headers, start=1):
        ws.cell(row=header_row, column=i, value=h)
    style_header_row(ws, header_row, 1, len(headers))

    start_row = header_row + 1
    for i, row_data in enumerate(SKU_DATA):
        r = start_row + i
        sku, name, category, demand, order_cost, hold_cost, max_dd, avg_dd, max_lt, avg_lt, unit_cost = row_data

        ws.cell(row=r, column=1, value=sku).font = INPUT_FONT
        ws.cell(row=r, column=2, value=name).font = INPUT_FONT
        ws.cell(row=r, column=3, value=category).font = INPUT_FONT
        ws.cell(row=r, column=4, value=demand).font = INPUT_FONT
        ws.cell(row=r, column=5, value=order_cost).font = INPUT_FONT
        ws.cell(row=r, column=5).number_format = CURRENCY_FMT
        ws.cell(row=r, column=6, value=hold_cost).font = INPUT_FONT
        ws.cell(row=r, column=6).number_format = CURRENCY_FMT

        # EOQ formula = SQRT((2*Demand*OrderingCost)/HoldingCost)
        eoq_cell = ws.cell(row=r, column=7, value=f"=SQRT((2*D{r}*E{r})/F{r})")
        eoq_cell.font = FORMULA_FONT
        eoq_cell.number_format = NUMBER_FMT_1DP

        ws.cell(row=r, column=8, value=max_dd).font = INPUT_FONT
        ws.cell(row=r, column=9, value=avg_dd).font = INPUT_FONT
        ws.cell(row=r, column=10, value=max_lt).font = INPUT_FONT
        ws.cell(row=r, column=11, value=avg_lt).font = INPUT_FONT

        # Safety Stock = (Max Daily Demand * Max Lead Time) - (Avg Daily Demand * Avg Lead Time)
        ss_cell = ws.cell(row=r, column=12, value=f"=(H{r}*J{r})-(I{r}*K{r})")
        ss_cell.font = FORMULA_FONT
        ss_cell.number_format = NUMBER_FMT

    end_row = start_row + len(SKU_DATA) - 1
    apply_border_range(ws, header_row, end_row, 1, len(headers))
    for r in range(start_row, end_row + 1):
        for c in range(1, len(headers) + 1):
            ws.cell(row=r, column=c).alignment = CENTER if c not in (2,) else LEFT

    # Summary block
    summary_row = end_row + 3
    ws.cell(row=summary_row, column=1, value="Portfolio Summary").font = SECTION_FONT
    ws.cell(row=summary_row, column=1).fill = SECTION_FILL
    ws.merge_cells(start_row=summary_row, start_column=1, end_row=summary_row, end_column=3)

    ws.cell(row=summary_row + 1, column=1, value="Average EOQ (units):").font = LABEL_FONT
    avg_eoq = ws.cell(row=summary_row + 1, column=4, value=f"=AVERAGE(G{start_row}:G{end_row})")
    avg_eoq.font = FORMULA_FONT
    avg_eoq.number_format = NUMBER_FMT_1DP

    ws.cell(row=summary_row + 2, column=1, value="Total Safety Stock (units):").font = LABEL_FONT
    tot_ss = ws.cell(row=summary_row + 2, column=4, value=f"=SUM(L{start_row}:L{end_row})")
    tot_ss.font = FORMULA_FONT
    tot_ss.number_format = NUMBER_FMT

    ws.cell(row=summary_row + 3, column=1, value="Highest Holding Cost SKU:").font = LABEL_FONT
    max_hold = ws.cell(
        row=summary_row + 3, column=4,
        value=f"=INDEX(A{start_row}:A{end_row},MATCH(MAX(F{start_row}:F{end_row}),F{start_row}:F{end_row},0))"
    )
    max_hold.font = FORMULA_FONT

    note = ws.cell(
        row=summary_row + 5, column=1,
        value="Assumptions: Annual demand, ordering cost, and holding cost figures are illustrative sample "
              "inputs styled on the DataCo Smart Supply Chain schema (order item fields, product category, "
              "shipping fields). Replace blue input cells with sourced ERP/WMS extract values."
    )
    note.font = NOTE_FONT
    ws.merge_cells(start_row=summary_row + 5, start_column=1, end_row=summary_row + 5, end_column=12)
    ws.cell(row=summary_row + 5, column=1).alignment = Alignment(wrap_text=True, vertical="top")

    autosize_columns(ws, {
        "A": 12, "B": 22, "C": 16, "D": 14, "E": 13, "F": 13,
        "G": 12, "H": 11, "I": 11, "J": 11, "K": 11, "L": 12
    })
    ws.freeze_panes = "A7"
    ws.sheet_view.showGridLines = False
    return ws, start_row, end_row


# ------------------------------------------------------------------------------
# SHEET 2: Reorder_Point_Model
# ------------------------------------------------------------------------------
def build_rop_sheet(wb: Workbook, eoq_start_row: int, eoq_end_row: int):
    ws = wb.create_sheet("Reorder_Point_Model")

    style_title(
        ws, "A1:H2",
        "Reorder Point (ROP) Model",
        "ROP = (Avg Daily Demand x Avg Lead Time) + Safety Stock   |   "
        "Values pulled live from the EOQ_Calculator tab via cross-sheet formulas (green font)."
    )

    headers = [
        "SKU_ID", "Product Name", "Avg Daily\nDemand", "Avg Lead\nTime (days)",
        "Safety Stock\n(units)", "Reorder Point\n(ROP, units)", "EOQ\n(units/order)",
        "Days of Supply\nat ROP Trigger"
    ]
    header_row = 5
    for i, h in enumerate(headers, start=1):
        ws.cell(row=header_row, column=i, value=h)
    style_header_row(ws, header_row, 1, len(headers))

    start_row = header_row + 1
    n = eoq_end_row - eoq_start_row + 1
    for i in range(n):
        r = start_row + i
        src = eoq_start_row + i

        # Live cross-sheet links back to EOQ_Calculator (green font per convention)
        sku_cell = ws.cell(row=r, column=1, value=f"=EOQ_Calculator!A{src}")
        sku_cell.font = LINK_FONT
        name_cell = ws.cell(row=r, column=2, value=f"=EOQ_Calculator!B{src}")
        name_cell.font = LINK_FONT
        add_cell = ws.cell(row=r, column=3, value=f"=EOQ_Calculator!I{src}")
        add_cell.font = LINK_FONT
        alt_cell = ws.cell(row=r, column=4, value=f"=EOQ_Calculator!K{src}")
        alt_cell.font = LINK_FONT
        ss_cell = ws.cell(row=r, column=5, value=f"=EOQ_Calculator!L{src}")
        ss_cell.font = LINK_FONT
        ss_cell.number_format = NUMBER_FMT

        # ROP = (Avg Daily Demand * Avg Lead Time) + Safety Stock
        rop_cell = ws.cell(row=r, column=6, value=f"=(C{r}*D{r})+E{r}")
        rop_cell.font = FORMULA_FONT
        rop_cell.number_format = NUMBER_FMT

        eoq_cell = ws.cell(row=r, column=7, value=f"=EOQ_Calculator!G{src}")
        eoq_cell.font = LINK_FONT
        eoq_cell.number_format = NUMBER_FMT_1DP

        # Days of supply remaining once ROP is hit = ROP / Avg Daily Demand (guarded denominator)
        dos_cell = ws.cell(row=r, column=8, value=f"=IF(C{r}=0,0,F{r}/C{r})")
        dos_cell.font = FORMULA_FONT
        dos_cell.number_format = NUMBER_FMT_1DP

    end_row = start_row + n - 1
    apply_border_range(ws, header_row, end_row, 1, len(headers))
    for r in range(start_row, end_row + 1):
        for c in range(1, len(headers) + 1):
            ws.cell(row=r, column=c).alignment = CENTER if c != 2 else LEFT

    # Conditional formatting: flag ROP values in the top quartile as high-priority replenishment
    ws.conditional_formatting.add(
        f"F{start_row}:F{end_row}",
        CellIsRule(operator="greaterThan", formula=[f"AVERAGE(F{start_row}:F{end_row})"],
                   fill=PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid"))
    )

    note_row = end_row + 2
    note = ws.cell(
        row=note_row, column=1,
        value="Rows highlighted red have a Reorder Point above the portfolio average and should be "
              "prioritized in supplier PO cycles. This tab intentionally contains no hardcoded numbers — "
              "every value traces back to EOQ_Calculator inputs, so editing a demand or lead-time assumption "
              "there flows through automatically."
    )
    note.font = NOTE_FONT
    ws.merge_cells(start_row=note_row, start_column=1, end_row=note_row, end_column=8)
    ws.cell(row=note_row, column=1).alignment = Alignment(wrap_text=True, vertical="top")

    autosize_columns(ws, {"A": 12, "B": 22, "C": 12, "D": 12, "E": 13, "F": 15, "G": 12, "H": 16})
    ws.freeze_panes = "A6"
    ws.sheet_view.showGridLines = False
    return ws


# ------------------------------------------------------------------------------
# SHEET 3: Holding_vs_Stockout_Cost
# ------------------------------------------------------------------------------
def build_cost_tradeoff_sheet(wb: Workbook):
    ws = wb.create_sheet("Holding_vs_Stockout_Cost")

    style_title(
        ws, "A1:M2",
        "Holding Cost vs. Stockout Cost Trade-off Model",
        "Annual Holding Cost = Current Stock x Holding Cost/Unit   |   "
        "Expected Stockout Cost = Stockout Probability x (Lost Margin + Customer Loss Penalty) x Annual Demand Exposure"
    )

    headers = [
        "SKU_ID", "Current Stock\n(units)", "Unit Cost\n($)", "Selling Price\n($)",
        "Holding Cost\n($/unit/yr)", "Annual Holding\nCost ($)", "Stockout\nProbability (%)",
        "Avg Daily\nDemand", "Annual Demand\nExposure (units)", "Gross Margin\n($/unit)",
        "Customer Loss\nFactor (%)", "Expected Annual\nStockout Cost ($)", "Net Cost\nDelta ($)"
    ]
    header_row = 5
    for i, h in enumerate(headers, start=1):
        ws.cell(row=header_row, column=i, value=h)
    style_header_row(ws, header_row, 1, len(headers))

    start_row = header_row + 1
    for i, row_data in enumerate(STOCKOUT_DATA):
        r = start_row + i
        sku, stock, price, sopct, closs, avg_dd, hold_cost, unit_cost = row_data

        ws.cell(row=r, column=1, value=sku).font = INPUT_FONT
        ws.cell(row=r, column=2, value=stock).font = INPUT_FONT
        ws.cell(row=r, column=3, value=unit_cost).font = INPUT_FONT
        ws.cell(row=r, column=3).number_format = CURRENCY_FMT
        ws.cell(row=r, column=4, value=price).font = INPUT_FONT
        ws.cell(row=r, column=4).number_format = CURRENCY_FMT
        ws.cell(row=r, column=5, value=hold_cost).font = INPUT_FONT
        ws.cell(row=r, column=5).number_format = CURRENCY_FMT

        # Annual Holding Cost = Current Stock x Holding Cost/Unit
        hc_cell = ws.cell(row=r, column=6, value=f"=B{r}*E{r}")
        hc_cell.font = FORMULA_FONT
        hc_cell.number_format = CURRENCY_FMT_0DP

        so_prob = ws.cell(row=r, column=7, value=sopct / 100)
        so_prob.font = INPUT_FONT
        so_prob.fill = ASSUMPTION_FILL
        so_prob.number_format = PERCENT_FMT

        ws.cell(row=r, column=8, value=avg_dd).font = INPUT_FONT

        # Annual Demand Exposure = Avg Daily Demand * 365
        exp_cell = ws.cell(row=r, column=9, value=f"=H{r}*365")
        exp_cell.font = FORMULA_FONT
        exp_cell.number_format = NUMBER_FMT

        # Gross Margin per unit = Selling Price - Unit Cost
        margin_cell = ws.cell(row=r, column=10, value=f"=D{r}-C{r}")
        margin_cell.font = FORMULA_FONT
        margin_cell.number_format = CURRENCY_FMT

        cl_cell = ws.cell(row=r, column=11, value=closs / 100)
        cl_cell.font = INPUT_FONT
        cl_cell.fill = ASSUMPTION_FILL
        cl_cell.number_format = PERCENT_FMT

        # Expected Annual Stockout Cost = Stockout Prob x (Margin x (1+Customer Loss Factor)) x Demand Exposure
        sc_cell = ws.cell(
            row=r, column=12,
            value=f"=G{r}*(J{r}*(1+K{r}))*I{r}"
        )
        sc_cell.font = FORMULA_FONT
        sc_cell.number_format = CURRENCY_FMT_0DP

        # Net Cost Delta = Annual Holding Cost - Expected Stockout Cost (positive = over-invested in holding)
        delta_cell = ws.cell(row=r, column=13, value=f"=F{r}-L{r}")
        delta_cell.font = FORMULA_FONT
        delta_cell.number_format = CURRENCY_FMT_0DP

    end_row = start_row + len(STOCKOUT_DATA) - 1
    apply_border_range(ws, header_row, end_row, 1, len(headers))
    for r in range(start_row, end_row + 1):
        for c in range(1, len(headers) + 1):
            ws.cell(row=r, column=c).alignment = CENTER

    # Conditional formatting on Net Cost Delta: red if holding cost >> stockout cost (over-stocked),
    # green if stockout risk cost exceeds holding cost (under-stocked / at risk)
    ws.conditional_formatting.add(
        f"M{start_row}:M{end_row}",
        CellIsRule(operator="lessThan", formula=["0"],
                   fill=PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid"))
    )
    ws.conditional_formatting.add(
        f"M{start_row}:M{end_row}",
        CellIsRule(operator="greaterThanOrEqual", formula=["0"],
                   fill=PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid"))
    )

    summary_row = end_row + 3
    ws.cell(row=summary_row, column=1, value="Portfolio Cost Summary").font = SECTION_FONT
    ws.cell(row=summary_row, column=1).fill = SECTION_FILL
    ws.merge_cells(start_row=summary_row, start_column=1, end_row=summary_row, end_column=3)

    ws.cell(row=summary_row + 1, column=1, value="Total Annual Holding Cost:").font = LABEL_FONT
    tot_hc = ws.cell(row=summary_row + 1, column=4, value=f"=SUM(F{start_row}:F{end_row})")
    tot_hc.font = FORMULA_FONT
    tot_hc.number_format = CURRENCY_FMT_0DP

    ws.cell(row=summary_row + 2, column=1, value="Total Expected Stockout Cost:").font = LABEL_FONT
    tot_sc = ws.cell(row=summary_row + 2, column=4, value=f"=SUM(L{start_row}:L{end_row})")
    tot_sc.font = FORMULA_FONT
    tot_sc.number_format = CURRENCY_FMT_0DP

    ws.cell(row=summary_row + 3, column=1, value="Net Portfolio Position:").font = LABEL_FONT
    net_pos = ws.cell(row=summary_row + 3, column=4, value=f"=D{summary_row+1}-D{summary_row+2}")
    net_pos.font = FORMULA_FONT
    net_pos.number_format = CURRENCY_FMT_0DP

    ws.cell(row=summary_row + 4, column=1, value="SKUs at Stockout Risk (cost > holding):").font = LABEL_FONT
    risk_count = ws.cell(row=summary_row + 4, column=4, value=f"=COUNTIF(M{start_row}:M{end_row},\"<0\")")
    risk_count.font = FORMULA_FONT
    risk_count.number_format = NUMBER_FMT

    note = ws.cell(
        row=summary_row + 6, column=1,
        value="Green rows: holding investment currently outweighs stockout risk exposure (healthy buffer). "
              "Red rows: expected stockout cost exceeds the holding cost being carried — these SKUs are "
              "under-protected and are prime candidates for safety stock increases or expedited replenishment. "
              "Stockout probability and customer loss factor (highlighted yellow) are modeling assumptions; "
              "replace with historical fulfillment data where available."
    )
    note.font = NOTE_FONT
    ws.merge_cells(start_row=summary_row + 6, start_column=1, end_row=summary_row + 6, end_column=13)
    ws.cell(row=summary_row + 6, column=1).alignment = Alignment(wrap_text=True, vertical="top")

    autosize_columns(ws, {
        "A": 12, "B": 13, "C": 11, "D": 12, "E": 12, "F": 14, "G": 13,
        "H": 11, "I": 14, "J": 12, "K": 13, "L": 16, "M": 13
    })
    ws.freeze_panes = "A6"
    ws.sheet_view.showGridLines = False
    return ws


# ------------------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------------------
def main():
    wb = Workbook()

    _, eoq_start, eoq_end = build_eoq_sheet(wb)
    build_rop_sheet(wb, eoq_start, eoq_end)
    build_cost_tradeoff_sheet(wb)

    # Order tabs left-to-right: EOQ -> ROP -> Holding vs Stockout
    wb._sheets = [wb["EOQ_Calculator"], wb["Reorder_Point_Model"], wb["Holding_vs_Stockout_Cost"]]
    wb.active = 0

    out_path = "supply_chain_eoq_calculator.xlsx"
    wb.save(out_path)
    print(f"Workbook written to: {out_path}")
    print("Tabs created: EOQ_Calculator, Reorder_Point_Model, Holding_vs_Stockout_Cost")
    print("NOTE: openpyxl writes formulas without cached values. Open the file in Excel "
          "(or LibreOffice) once to force a recalculation, or run it through a recalculation "
          "utility (e.g. LibreOffice headless / scripts/recalc.py) before distributing.")


if __name__ == "__main__":
    main()
