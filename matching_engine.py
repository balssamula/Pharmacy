"""Pure catalogue matching logic (no API calls and no Streamlit state).

All comparisons are keyed by SKU, never by product ID or by name.
Duplicate/missing SKUs are quarantined so that they are not imported accidentally.
"""
from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

import pandas as pd

REQUIRED_COLUMNS = ("رقم المنتج", "اسم المنتج", "سعر المنتج", "خاضع للضريبة؟")
EMPTY_WORDS = {"", "nan", "none", "null", "nat", "<na>"}
YES = {"نعم", "yes", "true", "1", "خاضع", "taxable"}
NO = {"لا", "no", "false", "0", "غير خاضع", "non-taxable", "not taxable"}
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def normalize_sku(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKC", str(value)).translate(_ARABIC_DIGITS)
    text = text.strip().replace("\u200e", "").replace("\u200f", "")
    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".")[0]
    return "" if text.casefold() in EMPTY_WORDS else text


def normalize_name(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    return re.sub(r"\s+", " ", text.replace("ـ", "").strip()).casefold()


def parse_tax(value: Any):
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return None
    text = unicodedata.normalize("NFKC", str(value)).translate(_ARABIC_DIGITS).strip().casefold()
    if text in YES:
        return True
    if text in NO:
        return False
    return None


def parse_price(value: Any):
    if pd.isna(value):
        return None
    text = unicodedata.normalize("NFKC", str(value)).translate(_ARABIC_DIGITS)
    text = text.strip().replace(",", "").replace("٬", "").replace("٫", ".").replace("ر.س", "").strip()
    try:
        amount = Decimal(text)
        if not amount.is_finite() or amount < 0:
            return None
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None


def _prepare(df: pd.DataFrame, sheet: str) -> pd.DataFrame:
    missing = [field for field in REQUIRED_COLUMNS if field not in df.columns]
    if missing:
        raise ValueError(f"ورقة {sheet}: الأعمدة المطلوبة غير موجودة: {', '.join(missing)}")
    frame = df.copy()
    frame["_sku"] = frame["رقم المنتج"].map(normalize_sku)
    frame["_name"] = frame["اسم المنتج"].map(normalize_name)
    frame["_price"] = frame["سعر المنتج"].map(parse_price)
    frame["_tax"] = frame["خاضع للضريبة؟"].map(parse_tax)
    return frame


def compare_catalogs(
    salla: pd.DataFrame,
    system: pd.DataFrame,
    excluded_categories: str = "",
    price_tolerance: Any = "0.01",
) -> dict:
    """Produce auditable, side-by-side DataFrames, with no writes to any store."""
    tolerance = Decimal(str(price_tolerance))
    if not tolerance.is_finite() or tolerance < 0:
        raise ValueError("هامش اختلاف السعر غير صالح")
    original_salla_len, original_system_len = len(salla), len(system)
    a = _prepare(salla, "salla")
    b = _prepare(system, "system")
    excluded_count = 0
    if excluded_categories:
        if "التصنيف" not in b.columns:
            raise ValueError("لا يوجد عمود 'التصنيف' بورقة system لتطبيق استبعاد التصنيفات")
        categories = {normalize_name(x) for x in excluded_categories.split(",") if x.strip()}
        excluded_rows = b["التصنيف"].map(normalize_name).isin(categories)
        skipped_skus = set(b.loc[excluded_rows, "_sku"]) - {""}
        excluded_count = int(excluded_rows.sum())
        b = b.loc[~excluded_rows].copy()
        a = a.loc[~a["_sku"].isin(skipped_skus)].copy()

    # Exclude ambiguous SKU groups *in either file* from both sides of the join.
    dup_a = set(a.loc[a["_sku"].ne("") & a["_sku"].duplicated(keep=False), "_sku"])
    dup_b = set(b.loc[b["_sku"].ne("") & b["_sku"].duplicated(keep=False), "_sku"])
    ambiguities = dup_a | dup_b
    problematic_a = a.loc[a["_sku"].eq("") | a["_sku"].isin(ambiguities)].copy()
    problematic_b = b.loc[b["_sku"].eq("") | b["_sku"].isin(ambiguities)].copy()
    problematic_a["المصدر"] = "سلة"
    problematic_b["المصدر"] = "النظام الداخلي"
    problems = pd.concat([problematic_a, problematic_b], ignore_index=True)
    if len(problems):
        problems["المشكلة"] = problems["_sku"].map(lambda sku: "SKU فارغ" if not sku else "SKU مكرر في أحد الملفين")

    a = a.loc[a["_sku"].ne("") & ~a["_sku"].isin(ambiguities)].copy()
    b = b.loc[b["_sku"].ne("") & ~b["_sku"].isin(ambiguities)].copy()
    joined = b.merge(a, on="_sku", how="outer", suffixes=("_system", "_salla"), indicator=True, validate="one_to_one")

    new = joined.loc[joined["_merge"].eq("left_only")].copy()
    salla_only = joined.loc[joined["_merge"].eq("right_only")].copy()
    common = joined.loc[joined["_merge"].eq("both")].copy()

    # On common SKUs, ignore invalid values in a discrepancy claim; show them as issues instead.
    different_name = common.loc[common["_name_system"].ne(common["_name_salla"])].copy()
    different_price = common.loc[common.apply(
        lambda row: row["_price_system"] is not None and row["_price_salla"] is not None
        and abs(row["_price_system"] - row["_price_salla"]) > tolerance, axis=1
    )].copy() if not common.empty else common.copy()
    if len(different_price):
        different_price["الفرق (النظام - سلة)"] = different_price.apply(
            lambda row: float(row["_price_system"] - row["_price_salla"]), axis=1
        )
    different_tax = common.loc[common.apply(
        lambda row: row["_tax_system"] is not None and row["_tax_salla"] is not None
        and row["_tax_system"] != row["_tax_salla"], axis=1
    )].copy() if not common.empty else common.copy()

    # Source data with unknown taxes/prices is not eligible for automated import.
    for source_name, frame in (("سلة", a), ("النظام الداخلي", b)):
        malformed = frame.loc[
            frame["_price"].isna() | frame["_tax"].isna() | frame["_name"].eq("")
        ].copy()
        if len(malformed):
            malformed["المصدر"] = source_name
            malformed["المشكلة"] = malformed.apply(
                lambda row: "؛ ".join(x for x, bad in (
                    ("سعر غير صالح", row["_price"] is None),
                    ("ضريبة غير واضحة", row["_tax"] is None),
                    ("اسم فارغ", not row["_name"]),
                ) if bad), axis=1
            )
            problems = pd.concat([problems, malformed], ignore_index=True)

    def display(paired: pd.DataFrame, include_diff: bool = False) -> pd.DataFrame:
        names = {
            "_sku": "SKU",
            "اسم المنتج_system": "الاسم في النظام",
            "اسم المنتج_salla": "الاسم في سلة",
            "سعر المنتج_system": "السعر في النظام",
            "سعر المنتج_salla": "السعر في سلة",
            "خاضع للضريبة؟_system": "الضريبة في النظام",
            "خاضع للضريبة؟_salla": "الضريبة في سلة",
            "التصنيف_system": "التصنيف",
        }
        cols = [c for c in names if c in paired.columns]
        if include_diff and "الفرق (النظام - سلة)" in paired.columns:
            cols += ["الفرق (النظام - سلة)"]
        return paired.loc[:, cols].rename(columns=names).reset_index(drop=True)

    clean_new = b.loc[b["_sku"].isin(set(new["_sku"]))].copy()
    if clean_new.empty:
        clean_new["صلاحية الرفع"] = pd.Series(dtype="string")
    else:
        clean_new["صلاحية الرفع"] = clean_new.apply(
            lambda r: "جاهز" if r["_price"] is not None and r["_price"] > 0 and r["_tax"] is not None and r["_name"] else "يتطلب مراجعة", axis=1
        )
    clean_new = clean_new.rename(columns={"_sku": "SKU", "اسم المنتج": "اسم المنتج", "سعر المنتج": "سعر المنتج", "خاضع للضريبة؟": "خاضع للضريبة؟"})
    clean_new = clean_new.loc[:, [x for x in ("SKU", "اسم المنتج", "سعر المنتج", "خاضع للضريبة؟", "التصنيف", "صلاحية الرفع") if x in clean_new.columns]]
    if not problems.empty:
        problems = problems.rename(columns={"_sku": "SKU"})
        problems = problems.loc[:, [x for x in ("المصدر", "SKU", "اسم المنتج", "سعر المنتج", "خاضع للضريبة؟", "المشكلة") if x in problems.columns]]
    else:
        problems = pd.DataFrame(columns=["المصدر", "SKU", "اسم المنتج", "سعر المنتج", "خاضع للضريبة؟", "المشكلة"])

    return {
        "summary": {
            "salla_rows": original_salla_len,
            "system_rows": original_system_len,
            "excluded_system_rows": excluded_count,
            "comparable_common_skus": len(common),
            "new_products": len(clean_new),
            "ready_to_upload": int(clean_new["صلاحية الرفع"].eq("جاهز").sum()),
            "salla_only": len(salla_only),
            "different_names": len(different_name),
            "different_prices": len(different_price),
            "different_taxes": len(different_tax),
            "problems": len(problems),
            "ambiguous_skus": len(ambiguities),
        },
        "new": clean_new.reset_index(drop=True),
        "names": display(different_name),
        "prices": display(different_price, include_diff=True),
        "taxes": display(different_tax),
        "salla_only": display(salla_only),
        "problems": problems.reset_index(drop=True),
    }
