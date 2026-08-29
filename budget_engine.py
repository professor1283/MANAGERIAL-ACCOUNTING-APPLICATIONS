"""Budget calculation engine for the Northbridge Components MBA simulation.

The engine uses deterministic, AI-generated assumptions.  It produces the
instructor solution, grading metadata, and student-facing schedule layouts.
Only Python's standard library is required.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List

QTRS = ["Q1", "Q2", "Q3", "Q4"]
ALL_COLS = QTRS + ["Total"]


def D(value: Any) -> Decimal:
    return Decimal(str(value))


def r2(value: Decimal | float | int) -> float:
    return float(D(value).quantize(D("0.01"), rounding=ROUND_HALF_UP))


def r0(value: Decimal | float | int) -> float:
    return float(D(value).quantize(D("1"), rounding=ROUND_HALF_UP))


ASSUMPTIONS: Dict[str, Any] = {
    "company_name": "Northbridge Components, Inc.",
    "industry": "Precision components for industrial automation equipment",
    "budget_year": 2027,
    "difficulty": "Medium — Graduate MBA",
    "sales_units": {"Q1": 24000, "Q2": 28000, "Q3": 32000, "Q4": 30000},
    "next_year_sales_units": {"Q1": 26000, "Q2": 29000},
    "selling_price": 185.00,
    "collection_current_pct": 0.35,
    "collection_next_pct": 0.65,
    "beginning_accounts_receivable": 2700000.00,
    "fg_inventory_pct_next_sales": 0.20,
    "beginning_fg_units": 4800,
    "dm_kg_per_unit": 4.5,
    "dm_cost_per_kg": 8.40,
    "rm_inventory_pct_next_production_needs": 0.15,
    "beginning_rm_kg": 16740,
    "materials_payment_current_pct": 0.50,
    "materials_payment_next_pct": 0.50,
    "beginning_accounts_payable": 500000.00,
    "dl_hours_per_unit": 1.8,
    "dl_rate_per_hour": 26.00,
    "variable_moh_per_dlh": 12.00,
    "fixed_moh_per_quarter": 760000.00,
    "moh_depreciation_per_quarter": 180000.00,
    "variable_sga_pct_sales": 0.07,
    "fixed_sga_per_quarter": 720000.00,
    "sga_depreciation_per_quarter": 40000.00,
    "capital_expenditures": {"Q1": 0, "Q2": 1200000, "Q3": 850000, "Q4": 0},
    "dividends": {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 400000},
    "income_tax_rate": 0.24,
    "minimum_cash_balance": 500000.00,
    "borrowing_increment": 100000.00,
    "annual_interest_rate": 0.08,
    "beginning_cash": 650000.00,
    "beginning_line_of_credit": 1500000.00,
    "beginning_gross_ppe": 12000000.00,
    "beginning_accumulated_depreciation": 4200000.00,
    "common_stock": 4000000.00,
}


def _sum(vals: Dict[str, Decimal]) -> Decimal:
    return sum(vals.values(), D(0))


def build_solution() -> Dict[str, float]:
    a = ASSUMPTIONS
    s: Dict[str, Decimal] = {}

    sales_units = {q: D(a["sales_units"][q]) for q in QTRS}
    price = D(a["selling_price"])
    sales = {q: sales_units[q] * price for q in QTRS}
    for q in QTRS:
        s[f"sales.units.{q}"] = sales_units[q]
        s[f"sales.revenue.{q}"] = sales[q]
    s["sales.units.Total"] = _sum(sales_units)
    s["sales.revenue.Total"] = _sum(sales)

    # Cash collections
    current_pct = D(a["collection_current_pct"])
    next_pct = D(a["collection_next_pct"])
    current_collections = {q: sales[q] * current_pct for q in QTRS}
    prior_collections: Dict[str, Decimal] = {
        "Q1": D(a["beginning_accounts_receivable"]),
        "Q2": sales["Q1"] * next_pct,
        "Q3": sales["Q2"] * next_pct,
        "Q4": sales["Q3"] * next_pct,
    }
    total_collections = {q: current_collections[q] + prior_collections[q] for q in QTRS}
    for q in QTRS:
        s[f"collections.current.{q}"] = current_collections[q]
        s[f"collections.prior.{q}"] = prior_collections[q]
        s[f"collections.total.{q}"] = total_collections[q]
    s["collections.current.Total"] = _sum(current_collections)
    s["collections.prior.Total"] = _sum(prior_collections)
    s["collections.total.Total"] = _sum(total_collections)
    ending_ar = sales["Q4"] * next_pct
    s["collections.ending_ar.Total"] = ending_ar

    # Production budget
    desired_fg = {
        "Q1": D(a["sales_units"]["Q2"]) * D(a["fg_inventory_pct_next_sales"]),
        "Q2": D(a["sales_units"]["Q3"]) * D(a["fg_inventory_pct_next_sales"]),
        "Q3": D(a["sales_units"]["Q4"]) * D(a["fg_inventory_pct_next_sales"]),
        "Q4": D(a["next_year_sales_units"]["Q1"]) * D(a["fg_inventory_pct_next_sales"]),
    }
    beginning_fg = {
        "Q1": D(a["beginning_fg_units"]),
        "Q2": desired_fg["Q1"],
        "Q3": desired_fg["Q2"],
        "Q4": desired_fg["Q3"],
    }
    total_needs = {q: sales_units[q] + desired_fg[q] for q in QTRS}
    production = {q: total_needs[q] - beginning_fg[q] for q in QTRS}
    for q in QTRS:
        s[f"production.desired_fg.{q}"] = desired_fg[q]
        s[f"production.total_needs.{q}"] = total_needs[q]
        s[f"production.beginning_fg.{q}"] = beginning_fg[q]
        s[f"production.units.{q}"] = production[q]
    s["production.units.Total"] = _sum(production)

    # Next-year Q1 production needed to establish Q4 raw material target.
    next_q1_desired_fg = D(a["next_year_sales_units"]["Q2"]) * D(a["fg_inventory_pct_next_sales"])
    next_q1_begin_fg = D(a["next_year_sales_units"]["Q1"]) * D(a["fg_inventory_pct_next_sales"])
    next_q1_production = D(a["next_year_sales_units"]["Q1"]) + next_q1_desired_fg - next_q1_begin_fg

    # Direct materials budget
    kg_per_unit = D(a["dm_kg_per_unit"])
    cost_per_kg = D(a["dm_cost_per_kg"])
    production_needs_kg = {q: production[q] * kg_per_unit for q in QTRS}
    desired_rm = {
        "Q1": production_needs_kg["Q2"] * D(a["rm_inventory_pct_next_production_needs"]),
        "Q2": production_needs_kg["Q3"] * D(a["rm_inventory_pct_next_production_needs"]),
        "Q3": production_needs_kg["Q4"] * D(a["rm_inventory_pct_next_production_needs"]),
        "Q4": next_q1_production * kg_per_unit * D(a["rm_inventory_pct_next_production_needs"]),
    }
    beginning_rm = {
        "Q1": D(a["beginning_rm_kg"]),
        "Q2": desired_rm["Q1"],
        "Q3": desired_rm["Q2"],
        "Q4": desired_rm["Q3"],
    }
    materials_total_needs = {q: production_needs_kg[q] + desired_rm[q] for q in QTRS}
    purchases_kg = {q: materials_total_needs[q] - beginning_rm[q] for q in QTRS}
    purchase_cost = {q: purchases_kg[q] * cost_per_kg for q in QTRS}
    cash_payments_materials = {
        "Q1": D(a["beginning_accounts_payable"]) + purchase_cost["Q1"] * D(a["materials_payment_current_pct"]),
        "Q2": purchase_cost["Q1"] * D(a["materials_payment_next_pct"]) + purchase_cost["Q2"] * D(a["materials_payment_current_pct"]),
        "Q3": purchase_cost["Q2"] * D(a["materials_payment_next_pct"]) + purchase_cost["Q3"] * D(a["materials_payment_current_pct"]),
        "Q4": purchase_cost["Q3"] * D(a["materials_payment_next_pct"]) + purchase_cost["Q4"] * D(a["materials_payment_current_pct"]),
    }
    for q in QTRS:
        s[f"materials.production_needs_kg.{q}"] = production_needs_kg[q]
        s[f"materials.desired_rm_kg.{q}"] = desired_rm[q]
        s[f"materials.total_needs_kg.{q}"] = materials_total_needs[q]
        s[f"materials.beginning_rm_kg.{q}"] = beginning_rm[q]
        s[f"materials.purchases_kg.{q}"] = purchases_kg[q]
        s[f"materials.purchase_cost.{q}"] = purchase_cost[q]
        s[f"materials.cash_payments.{q}"] = cash_payments_materials[q]
    for row, vals in [
        ("production_needs_kg", production_needs_kg),
        ("purchases_kg", purchases_kg),
        ("purchase_cost", purchase_cost),
        ("cash_payments", cash_payments_materials),
    ]:
        s[f"materials.{row}.Total"] = _sum(vals)
    ending_ap = purchase_cost["Q4"] * D(a["materials_payment_next_pct"])
    s["materials.ending_ap.Total"] = ending_ap

    # Direct labor
    dl_hours_per_unit = D(a["dl_hours_per_unit"])
    dl_rate = D(a["dl_rate_per_hour"])
    dl_hours = {q: production[q] * dl_hours_per_unit for q in QTRS}
    dl_cost = {q: dl_hours[q] * dl_rate for q in QTRS}
    for q in QTRS:
        s[f"labor.hours.{q}"] = dl_hours[q]
        s[f"labor.cost.{q}"] = dl_cost[q]
    s["labor.hours.Total"] = _sum(dl_hours)
    s["labor.cost.Total"] = _sum(dl_cost)

    # Manufacturing overhead
    variable_moh_rate = D(a["variable_moh_per_dlh"])
    fixed_moh = D(a["fixed_moh_per_quarter"])
    moh_dep = D(a["moh_depreciation_per_quarter"])
    variable_moh = {q: dl_hours[q] * variable_moh_rate for q in QTRS}
    total_moh = {q: variable_moh[q] + fixed_moh for q in QTRS}
    cash_moh = {q: total_moh[q] - moh_dep for q in QTRS}
    for q in QTRS:
        s[f"moh.variable.{q}"] = variable_moh[q]
        s[f"moh.total.{q}"] = total_moh[q]
        s[f"moh.cash.{q}"] = cash_moh[q]
    s["moh.variable.Total"] = _sum(variable_moh)
    s["moh.total.Total"] = _sum(total_moh)
    s["moh.cash.Total"] = _sum(cash_moh)

    # Inventory and cost of goods sold
    annual_production = _sum(production)
    dm_per_unit = kg_per_unit * cost_per_kg
    dl_per_unit = dl_hours_per_unit * dl_rate
    variable_oh_per_unit = dl_hours_per_unit * variable_moh_rate
    fixed_oh_per_unit = (fixed_moh * D(4)) / annual_production
    unit_product_cost = dm_per_unit + dl_per_unit + variable_oh_per_unit + fixed_oh_per_unit
    ending_rm_value = desired_rm["Q4"] * cost_per_kg
    ending_fg_value = desired_fg["Q4"] * unit_product_cost
    beginning_fg_value = D(a["beginning_fg_units"]) * unit_product_cost
    direct_material_used = _sum(production_needs_kg) * cost_per_kg
    cogm = direct_material_used + _sum(dl_cost) + _sum(total_moh)
    cogs = beginning_fg_value + cogm - ending_fg_value
    inventory_values = {
        "dm_per_unit": dm_per_unit,
        "dl_per_unit": dl_per_unit,
        "variable_oh_per_unit": variable_oh_per_unit,
        "fixed_oh_per_unit": fixed_oh_per_unit,
        "unit_product_cost": unit_product_cost,
        "ending_rm_value": ending_rm_value,
        "ending_fg_value": ending_fg_value,
        "cogm": cogm,
        "cogs": cogs,
    }
    for key, val in inventory_values.items():
        s[f"inventory.{key}.Total"] = val

    # Selling, general and administrative expense
    var_sga_pct = D(a["variable_sga_pct_sales"])
    fixed_sga = D(a["fixed_sga_per_quarter"])
    sga_dep = D(a["sga_depreciation_per_quarter"])
    variable_sga = {q: sales[q] * var_sga_pct for q in QTRS}
    total_sga = {q: variable_sga[q] + fixed_sga for q in QTRS}
    cash_sga = {q: total_sga[q] - sga_dep for q in QTRS}
    for q in QTRS:
        s[f"sga.variable.{q}"] = variable_sga[q]
        s[f"sga.total.{q}"] = total_sga[q]
        s[f"sga.cash.{q}"] = cash_sga[q]
    s["sga.variable.Total"] = _sum(variable_sga)
    s["sga.total.Total"] = _sum(total_sga)
    s["sga.cash.Total"] = _sum(cash_sga)

    # Quarterly pro-forma income statement data and cash/financing schedule.
    quarterly_cogs = {q: sales_units[q] * unit_product_cost for q in QTRS}
    operating_income = {q: sales[q] - quarterly_cogs[q] - total_sga[q] for q in QTRS}

    beginning_cash: Dict[str, Decimal] = {}
    total_cash_available: Dict[str, Decimal] = {}
    interest: Dict[str, Decimal] = {}
    pretax_income: Dict[str, Decimal] = {}
    taxes: Dict[str, Decimal] = {}
    total_disbursements: Dict[str, Decimal] = {}
    cash_before_financing: Dict[str, Decimal] = {}
    borrowing: Dict[str, Decimal] = {}
    repayment: Dict[str, Decimal] = {}
    ending_cash: Dict[str, Decimal] = {}
    ending_loc: Dict[str, Decimal] = {}

    min_cash = D(a["minimum_cash_balance"])
    increment = D(a["borrowing_increment"])
    q_interest_rate = D(a["annual_interest_rate"]) / D(4)
    loc_balance = D(a["beginning_line_of_credit"])
    cash_balance = D(a["beginning_cash"])

    def round_up_increment(amount: Decimal) -> Decimal:
        if amount <= 0:
            return D(0)
        units = (amount / increment).to_integral_value(rounding="ROUND_CEILING")
        return units * increment

    def round_down_increment(amount: Decimal) -> Decimal:
        if amount <= 0:
            return D(0)
        units = (amount / increment).to_integral_value(rounding="ROUND_FLOOR")
        return units * increment

    for q in QTRS:
        beginning_cash[q] = cash_balance
        total_cash_available[q] = cash_balance + total_collections[q]
        interest[q] = loc_balance * q_interest_rate
        pretax_income[q] = operating_income[q] - interest[q]
        taxes[q] = max(D(0), pretax_income[q] * D(a["income_tax_rate"]))
        disb = (
            cash_payments_materials[q]
            + dl_cost[q]
            + cash_moh[q]
            + cash_sga[q]
            + D(a["capital_expenditures"][q])
            + taxes[q]
            + interest[q]
            + D(a["dividends"][q])
        )
        total_disbursements[q] = disb
        cash_before_financing[q] = total_cash_available[q] - disb
        borrowing[q] = D(0)
        repayment[q] = D(0)
        if cash_before_financing[q] < min_cash:
            borrowing[q] = round_up_increment(min_cash - cash_before_financing[q])
            loc_balance += borrowing[q]
        else:
            max_repay = min(loc_balance, cash_before_financing[q] - min_cash)
            repayment[q] = round_down_increment(max_repay)
            loc_balance -= repayment[q]
        ending_cash[q] = cash_before_financing[q] + borrowing[q] - repayment[q]
        ending_loc[q] = loc_balance
        cash_balance = ending_cash[q]

    for q in QTRS:
        cash_rows = {
            "beginning_cash": beginning_cash[q],
            "total_available": total_cash_available[q],
            "taxes": taxes[q],
            "interest": interest[q],
            "total_disbursements": total_disbursements[q],
            "before_financing": cash_before_financing[q],
            "borrowing": borrowing[q],
            "repayment": repayment[q],
            "ending_cash": ending_cash[q],
            "ending_loc": ending_loc[q],
        }
        for row, val in cash_rows.items():
            s[f"cash.{row}.{q}"] = val
    for row, vals in [
        ("taxes", taxes),
        ("interest", interest),
        ("total_disbursements", total_disbursements),
        ("borrowing", borrowing),
        ("repayment", repayment),
    ]:
        s[f"cash.{row}.Total"] = _sum(vals)
    s["cash.ending_cash.Total"] = ending_cash["Q4"]
    s["cash.ending_loc.Total"] = ending_loc["Q4"]

    # Pro-forma income statement
    gross_margin = {q: sales[q] - quarterly_cogs[q] for q in QTRS}
    net_income = {q: pretax_income[q] - taxes[q] for q in QTRS}
    income_rows = {
        "sales": sales,
        "cogs": quarterly_cogs,
        "gross_margin": gross_margin,
        "sga": total_sga,
        "operating_income": operating_income,
        "interest": interest,
        "pretax": pretax_income,
        "taxes": taxes,
        "net_income": net_income,
    }
    for row, vals in income_rows.items():
        for q in QTRS:
            s[f"income.{row}.{q}"] = vals[q]
        s[f"income.{row}.Total"] = _sum(vals)

    # Beginning retained earnings is the balancing amount in the opening BS.
    beginning_rm_value = D(a["beginning_rm_kg"]) * cost_per_kg
    beginning_assets = (
        D(a["beginning_cash"])
        + D(a["beginning_accounts_receivable"])
        + beginning_rm_value
        + beginning_fg_value
        + D(a["beginning_gross_ppe"])
        - D(a["beginning_accumulated_depreciation"])
    )
    beginning_retained_earnings = (
        beginning_assets
        - D(a["beginning_accounts_payable"])
        - D(a["beginning_line_of_credit"])
        - D(a["common_stock"])
    )

    # Pro-forma balance sheet
    gross_ppe_end = D(a["beginning_gross_ppe"]) + sum(D(v) for v in a["capital_expenditures"].values())
    total_depreciation = (moh_dep + sga_dep) * D(4)
    accum_dep_end = D(a["beginning_accumulated_depreciation"]) + total_depreciation
    net_ppe_end = gross_ppe_end - accum_dep_end
    current_assets = ending_cash["Q4"] + ending_ar + ending_rm_value + ending_fg_value
    total_assets = current_assets + net_ppe_end
    total_liabilities = ending_ap + ending_loc["Q4"]
    retained_earnings_end = beginning_retained_earnings + _sum(net_income) - sum(D(v) for v in a["dividends"].values())
    total_equity = D(a["common_stock"]) + retained_earnings_end
    balance_rows = {
        "cash": ending_cash["Q4"],
        "accounts_receivable": ending_ar,
        "raw_materials": ending_rm_value,
        "finished_goods": ending_fg_value,
        "total_current_assets": current_assets,
        "gross_ppe": gross_ppe_end,
        "accumulated_depreciation": accum_dep_end,
        "net_ppe": net_ppe_end,
        "total_assets": total_assets,
        "accounts_payable": ending_ap,
        "line_of_credit": ending_loc["Q4"],
        "total_liabilities": total_liabilities,
        "common_stock": D(a["common_stock"]),
        "retained_earnings": retained_earnings_end,
        "total_equity": total_equity,
        "total_liabilities_equity": total_liabilities + total_equity,
    }
    for row, val in balance_rows.items():
        s[f"balance.{row}.Total"] = val

    # Pro-forma statement of cash flows, indirect method.
    increase_ar = ending_ar - D(a["beginning_accounts_receivable"])
    increase_rm = ending_rm_value - beginning_rm_value
    increase_fg = ending_fg_value - beginning_fg_value
    increase_ap = ending_ap - D(a["beginning_accounts_payable"])
    cfo = _sum(net_income) + total_depreciation - increase_ar - increase_rm - increase_fg + increase_ap
    capex_total = sum(D(v) for v in a["capital_expenditures"].values())
    cfi = -capex_total
    total_borrowings = _sum(borrowing)
    total_repayments = _sum(repayment)
    dividends_total = sum(D(v) for v in a["dividends"].values())
    cff = total_borrowings - total_repayments - dividends_total
    net_change_cash = cfo + cfi + cff
    cashflow_rows = {
        "net_income": _sum(net_income),
        "depreciation": total_depreciation,
        "increase_ar": -increase_ar,
        "increase_rm": -increase_rm,
        "increase_fg": -increase_fg,
        "increase_ap": increase_ap,
        "cfo": cfo,
        "capex": -capex_total,
        "cfi": cfi,
        "borrowings": total_borrowings,
        "repayments": -total_repayments,
        "dividends": -dividends_total,
        "cff": cff,
        "net_change_cash": net_change_cash,
        "beginning_cash": D(a["beginning_cash"]),
        "ending_cash": ending_cash["Q4"],
    }
    for row, val in cashflow_rows.items():
        s[f"cashflow.{row}.Total"] = val

    # Normalize all outputs to two decimals for serialization and grading.
    return {key: r2(value) for key, value in s.items()}


SOLUTION = build_solution()


def cells(prefix: str, cols: List[str], fmt: str = "currency") -> List[Dict[str, Any]]:
    return [{"key": f"{prefix}.{c}", "format": fmt} for c in cols]


def row(label: str, prefix: str | None = None, cols: List[str] | None = None,
        fmt: str = "currency", readonly: Dict[str, Any] | None = None,
        note: str = "") -> Dict[str, Any]:
    cols = cols or ALL_COLS
    result: Dict[str, Any] = {"label": label, "note": note, "cells": []}
    for c in cols:
        if readonly is not None and c in readonly:
            result["cells"].append({"column": c, "display": readonly[c], "format": fmt, "readonly": True})
        elif prefix:
            key = f"{prefix}.{c}"
            if key in SOLUTION:
                result["cells"].append({"column": c, "key": key, "format": fmt})
            else:
                result["cells"].append({"column": c, "display": "—", "readonly": True})
        else:
            result["cells"].append({"column": c, "display": "—", "readonly": True})
    return result


def qreadonly(values: Dict[str, Any], total: Any | None = None) -> Dict[str, Any]:
    result = {q: values[q] for q in QTRS}
    if total is not None:
        result["Total"] = total
    return result


SCHEDULES: List[Dict[str, Any]] = [
    {
        "id": "sales",
        "title": "A. Sales Budget",
        "weight": 5,
        "instructions": "Enter quarterly budgeted unit sales. The annual unit total and budgeted sales revenue are calculated automatically using the selling price per unit.",
        "columns": ALL_COLS,
        "rows": [
            {
                "label": "Budgeted unit sales",
                "note": "Enter Q1 through Q4; the annual total is calculated automatically.",
                "cells": [
                    *[{"column": q, "key": f"sales.units.{q}", "format": "units", "entry_mode": "student_input"} for q in QTRS],
                    {"column": "Total", "key": "sales.units.Total", "format": "units", "computed": True, "entry_mode": "system_calculated", "calculation_rule": "SUM(sales.units.Q1:sales.units.Q4)"},
                ],
            },
            row("Selling price per unit", readonly={**{q: ASSUMPTIONS["selling_price"] for q in QTRS}, "Total": "—"}, fmt="currency"),
            {
                "label": "Budgeted sales revenue",
                "note": "Automatically calculated as Budgeted Unit Sales × Selling Price per Unit.",
                "cells": [
                    *[{"column": q, "key": f"sales.revenue.{q}", "format": "currency", "computed": True, "entry_mode": "system_calculated", "calculation_rule": f"sales.units.{q} * selling_price_per_unit"} for q in QTRS],
                    {"column": "Total", "key": "sales.revenue.Total", "format": "currency", "computed": True, "entry_mode": "system_calculated", "calculation_rule": "sales.units.Total * selling_price_per_unit"},
                ],
            },
        ],
    },
    {
        "id": "collections",
        "title": "B. Cash Collections Budget",
        "weight": 8,
        "instructions": "Apply the 35% current-quarter and 65% following-quarter collection pattern. Beginning receivables are collected in Q1.",
        "columns": ALL_COLS,
        "rows": [
            row("Collections from current-quarter sales", "collections.current"),
            row("Collections from prior-quarter sales / beginning A/R", "collections.prior"),
            row("Total cash collections", "collections.total"),
            row("Ending accounts receivable", "collections.ending_ar", cols=["Total"], note="Year-end amount only"),
        ],
    },
    {
        "id": "production",
        "title": "C. Production Budget",
        "weight": 8,
        "instructions": "Maintain ending finished-goods inventory equal to 20% of the following quarter's unit sales.",
        "columns": ALL_COLS,
        "rows": [
            row("Budgeted unit sales", readonly=qreadonly(ASSUMPTIONS["sales_units"], sum(ASSUMPTIONS["sales_units"].values())), fmt="units"),
            row("Desired ending finished-goods units", "production.desired_fg", fmt="units"),
            row("Total unit requirements", "production.total_needs", fmt="units"),
            row("Less: beginning finished-goods units", "production.beginning_fg", fmt="units"),
            row("Required production units", "production.units", fmt="units"),
        ],
    },
    {
        "id": "materials",
        "title": "D. Direct Materials Purchases and Cash Payments Budget",
        "weight": 12,
        "instructions": "Each unit requires 4.5 kilograms. Maintain ending raw materials equal to 15% of the next quarter's production needs. Materials are paid 50% currently and 50% next quarter.",
        "columns": ALL_COLS,
        "rows": [
            row("Materials needed for production (kg)", "materials.production_needs_kg", fmt="units"),
            row("Desired ending raw-material inventory (kg)", "materials.desired_rm_kg", fmt="units"),
            row("Total material requirements (kg)", "materials.total_needs_kg", fmt="units"),
            row("Less: beginning raw-material inventory (kg)", "materials.beginning_rm_kg", fmt="units"),
            row("Required material purchases (kg)", "materials.purchases_kg", fmt="units"),
            row("Cost of material purchases", "materials.purchase_cost"),
            row("Cash payments for materials", "materials.cash_payments"),
            row("Ending accounts payable", "materials.ending_ap", cols=["Total"], note="Year-end amount only"),
        ],
    },
    {
        "id": "labor",
        "title": "E. Direct Labor Budget",
        "weight": 7,
        "instructions": "Each unit requires 1.8 direct-labor hours at $26 per hour.",
        "columns": ALL_COLS,
        "rows": [
            row("Required direct-labor hours", "labor.hours", fmt="hours"),
            row("Direct-labor cost", "labor.cost"),
        ],
    },
    {
        "id": "moh",
        "title": "F. Manufacturing Overhead Budget",
        "weight": 8,
        "instructions": "Variable manufacturing overhead is $12 per direct-labor hour. Quarterly fixed overhead is $760,000, including $180,000 of depreciation.",
        "columns": ALL_COLS,
        "rows": [
            row("Variable manufacturing overhead", "moh.variable"),
            row("Total manufacturing overhead", "moh.total"),
            row("Cash manufacturing overhead", "moh.cash"),
        ],
    },
    {
        "id": "inventory",
        "title": "G. Inventory and Cost of Goods Sold Budget",
        "weight": 10,
        "instructions": "Use absorption costing. Allocate annual fixed manufacturing overhead across annual budgeted production units. Assume no work-in-process inventory.",
        "columns": ["Total"],
        "rows": [
            row("Direct materials cost per finished unit", "inventory.dm_per_unit", cols=["Total"]),
            row("Direct labor cost per finished unit", "inventory.dl_per_unit", cols=["Total"]),
            row("Variable overhead cost per finished unit", "inventory.variable_oh_per_unit", cols=["Total"]),
            row("Fixed overhead cost per finished unit", "inventory.fixed_oh_per_unit", cols=["Total"]),
            row("Total budgeted unit product cost", "inventory.unit_product_cost", cols=["Total"]),
            row("Ending raw-material inventory value", "inventory.ending_rm_value", cols=["Total"]),
            row("Ending finished-goods inventory value", "inventory.ending_fg_value", cols=["Total"]),
            row("Cost of goods manufactured", "inventory.cogm", cols=["Total"]),
            row("Cost of goods sold", "inventory.cogs", cols=["Total"]),
        ],
    },
    {
        "id": "sga",
        "title": "H. Selling, General, and Administrative Expense Budget",
        "weight": 7,
        "instructions": "Variable SG&A is 7% of sales. Quarterly fixed SG&A is $720,000, including $40,000 of depreciation.",
        "columns": ALL_COLS,
        "rows": [
            row("Variable SG&A expense", "sga.variable"),
            row("Total SG&A expense", "sga.total"),
            row("Cash SG&A expense", "sga.cash"),
        ],
    },
    {
        "id": "cash",
        "title": "Supporting Cash and Financing Schedule",
        "weight": 10,
        "instructions": "Maintain at least $500,000 cash. Borrow or repay the line of credit in $100,000 increments at each quarter-end. Interest is 2% per quarter on beginning-of-quarter debt. Income taxes are paid in the quarter incurred.",
        "columns": ALL_COLS,
        "rows": [
            row("Beginning cash balance", "cash.beginning_cash"),
            row("Total cash available", "cash.total_available"),
            row("Income tax payments", "cash.taxes"),
            row("Interest payments", "cash.interest"),
            row("Total cash disbursements", "cash.total_disbursements"),
            row("Cash excess (deficiency) before financing", "cash.before_financing"),
            row("Borrowings", "cash.borrowing"),
            row("Repayments", "cash.repayment"),
            row("Ending cash balance", "cash.ending_cash"),
            row("Ending line-of-credit balance", "cash.ending_loc"),
        ],
    },
    {
        "id": "income",
        "title": "Pro-Forma Income Statement",
        "weight": 10,
        "instructions": "Prepare the quarterly and annual budgeted income statement using absorption costing.",
        "columns": ALL_COLS,
        "rows": [
            row("Sales", "income.sales"),
            row("Cost of goods sold", "income.cogs"),
            row("Gross margin", "income.gross_margin"),
            row("Selling, general, and administrative expense", "income.sga"),
            row("Operating income", "income.operating_income"),
            row("Interest expense", "income.interest"),
            row("Income before taxes", "income.pretax"),
            row("Income tax expense", "income.taxes"),
            row("Net income", "income.net_income"),
        ],
    },
    {
        "id": "balance",
        "title": "Pro-Forma Balance Sheet — December 31, 2027",
        "weight": 8,
        "instructions": "Prepare the year-end balance sheet. Enter accumulated depreciation as a positive contra-asset amount.",
        "columns": ["Total"],
        "rows": [
            row("Cash", "balance.cash", cols=["Total"]),
            row("Accounts receivable", "balance.accounts_receivable", cols=["Total"]),
            row("Raw-material inventory", "balance.raw_materials", cols=["Total"]),
            row("Finished-goods inventory", "balance.finished_goods", cols=["Total"]),
            row("Total current assets", "balance.total_current_assets", cols=["Total"]),
            row("Gross property, plant, and equipment", "balance.gross_ppe", cols=["Total"]),
            row("Accumulated depreciation", "balance.accumulated_depreciation", cols=["Total"]),
            row("Net property, plant, and equipment", "balance.net_ppe", cols=["Total"]),
            row("Total assets", "balance.total_assets", cols=["Total"]),
            row("Accounts payable", "balance.accounts_payable", cols=["Total"]),
            row("Line of credit", "balance.line_of_credit", cols=["Total"]),
            row("Total liabilities", "balance.total_liabilities", cols=["Total"]),
            row("Common stock", "balance.common_stock", cols=["Total"]),
            row("Retained earnings", "balance.retained_earnings", cols=["Total"]),
            row("Total stockholders' equity", "balance.total_equity", cols=["Total"]),
            row("Total liabilities and equity", "balance.total_liabilities_equity", cols=["Total"]),
        ],
    },
    {
        "id": "cashflow",
        "title": "Pro-Forma Statement of Cash Flows — Indirect Method",
        "weight": 7,
        "instructions": "Use negative numbers for increases in operating assets, capital expenditures, debt repayments, and dividends.",
        "columns": ["Total"],
        "rows": [
            row("Net income", "cashflow.net_income", cols=["Total"]),
            row("Depreciation expense", "cashflow.depreciation", cols=["Total"]),
            row("Increase in accounts receivable", "cashflow.increase_ar", cols=["Total"]),
            row("Increase in raw-material inventory", "cashflow.increase_rm", cols=["Total"]),
            row("Increase in finished-goods inventory", "cashflow.increase_fg", cols=["Total"]),
            row("Increase in accounts payable", "cashflow.increase_ap", cols=["Total"]),
            row("Net cash provided by operating activities", "cashflow.cfo", cols=["Total"]),
            row("Capital expenditures", "cashflow.capex", cols=["Total"]),
            row("Net cash used in investing activities", "cashflow.cfi", cols=["Total"]),
            row("Borrowings", "cashflow.borrowings", cols=["Total"]),
            row("Debt repayments", "cashflow.repayments", cols=["Total"]),
            row("Dividends paid", "cashflow.dividends", cols=["Total"]),
            row("Net cash provided by financing activities", "cashflow.cff", cols=["Total"]),
            row("Net change in cash", "cashflow.net_change_cash", cols=["Total"]),
            row("Beginning cash", "cashflow.beginning_cash", cols=["Total"]),
            row("Ending cash", "cashflow.ending_cash", cols=["Total"]),
        ],
    },
]


def get_all_gradable_keys() -> List[str]:
    keys: List[str] = []
    for schedule in SCHEDULES:
        for r in schedule["rows"]:
            for c in r["cells"]:
                if c.get("key"):
                    keys.append(c["key"])
    return keys


def schedule_key_map() -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {}
    for schedule in SCHEDULES:
        result[schedule["id"]] = []
        for r in schedule["rows"]:
            for c in r["cells"]:
                if c.get("key"):
                    result[schedule["id"]].append(c["key"])
    return result


def public_assumptions() -> List[Dict[str, str]]:
    a = ASSUMPTIONS
    return [
        {"category": "Company", "item": "Company and budget period", "value": f"{a['company_name']} — fiscal year {a['budget_year']}"},
        {"category": "Sales", "item": "Quarterly sales forecast", "value": "Q1 24,000; Q2 28,000; Q3 32,000; Q4 30,000 units"},
        {"category": "Sales", "item": "Following-year forecast", "value": "2028 Q1 26,000 units; 2028 Q2 29,000 units"},
        {"category": "Sales", "item": "Selling price", "value": "$185 per unit"},
        {"category": "Collections", "item": "Customer collections", "value": "35% in quarter of sale; 65% in following quarter"},
        {"category": "Collections", "item": "Beginning accounts receivable", "value": "$2,700,000, collectible in Q1"},
        {"category": "Production", "item": "Finished-goods policy", "value": "Ending units = 20% of following quarter's sales units"},
        {"category": "Production", "item": "Beginning finished goods", "value": "4,800 units"},
        {"category": "Materials", "item": "Material standard", "value": "4.5 kg per unit at $8.40 per kg"},
        {"category": "Materials", "item": "Raw-material policy", "value": "Ending kg = 15% of next quarter's production requirements"},
        {"category": "Materials", "item": "Beginning raw materials", "value": "16,740 kg"},
        {"category": "Materials", "item": "Supplier payments", "value": "50% in purchase quarter; 50% in following quarter"},
        {"category": "Materials", "item": "Beginning accounts payable", "value": "$500,000, paid in Q1"},
        {"category": "Labor", "item": "Direct labor standard", "value": "1.8 hours per unit at $26 per hour"},
        {"category": "Overhead", "item": "Manufacturing overhead", "value": "$12 per DLH plus $760,000 fixed per quarter; fixed amount includes $180,000 depreciation"},
        {"category": "SG&A", "item": "Selling, general, and administrative", "value": "7% of sales plus $720,000 fixed per quarter; fixed amount includes $40,000 depreciation"},
        {"category": "Capital", "item": "Capital expenditures", "value": "Q2 $1,200,000; Q3 $850,000"},
        {"category": "Capital", "item": "Dividends", "value": "Q4 $400,000"},
        {"category": "Financing", "item": "Minimum cash and line of credit", "value": "$500,000 minimum; borrow/repay in $100,000 increments; 8% annual interest on beginning quarterly balance"},
        {"category": "Tax", "item": "Income taxes", "value": "24% of positive pretax income, paid in the quarter incurred"},
        {"category": "Opening balance sheet", "item": "Cash / gross PPE / accumulated depreciation", "value": "$650,000 / $12,000,000 / $4,200,000"},
        {"category": "Opening balance sheet", "item": "Line of credit / common stock", "value": "$1,500,000 / $4,000,000"},
    ]


if __name__ == "__main__":
    import json
    print(json.dumps({"assumptions": ASSUMPTIONS, "solution": SOLUTION}, indent=2))
