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



# Package quantities are extracted only when an explicit unit is present.
# Do not treat model numbers, strengths without units, or SKU as pack size.
_SIZE_UNITS = {
    "ml": ("حجم", "ml", "1"), "مل": ("حجم", "ml", "1"), "ملل": ("حجم", "ml", "1"),
    "ملليلتر": ("حجم", "ml", "1"), "مليلتر": ("حجم", "ml", "1"),
    "لتر": ("حجم", "ml", "1000"), "liter": ("حجم", "ml", "1000"), "litre": ("حجم", "ml", "1000"),
    "l": ("حجم", "ml", "1000"),
    "g": ("وزن", "g", "1"), "gr": ("وزن", "g", "1"), "gm": ("وزن", "g", "1"),
    "جرام": ("وزن", "g", "1"), "جم": ("وزن", "g", "1"), "غرام": ("وزن", "g", "1"),
    "kg": ("وزن", "g", "1000"), "كجم": ("وزن", "g", "1000"), "كيلو": ("وزن", "g", "1000"),
    "كيلوجرام": ("وزن", "g", "1000"),
    "mg": ("تركيز/جرعة", "mg", "1"), "مجم": ("تركيز/جرعة", "mg", "1"),
    "ملجم": ("تركيز/جرعة", "mg", "1"), "ملغ": ("تركيز/جرعة", "mg", "1"),
    "mcg": ("تركيز/جرعة", "mg", "0.001"), "ميكروجرام": ("تركيز/جرعة", "mg", "0.001"),
    "حبة": ("عدد", "حبة", "1"), "حبات": ("عدد", "حبة", "1"), "حب": ("عدد", "حبة", "1"),
    "قرص": ("عدد", "حبة", "1"), "اقراص": ("عدد", "حبة", "1"), "أقراص": ("عدد", "حبة", "1"),
    "tablet": ("عدد", "حبة", "1"), "tablets": ("عدد", "حبة", "1"), "tabs": ("عدد", "حبة", "1"),
    "كبسولة": ("عدد كبسولات", "كبسولة", "1"), "كبسولات": ("عدد كبسولات", "كبسولة", "1"),
    "capsule": ("عدد كبسولات", "كبسولة", "1"), "capsules": ("عدد كبسولات", "كبسولة", "1"),
    "قطعة": ("عدد قطع", "قطعة", "1"), "قطع": ("عدد قطع", "قطعة", "1"),
    "pcs": ("عدد قطع", "قطعة", "1"), "pieces": ("عدد قطع", "قطعة", "1"),
    "كيس": ("عدد أكياس", "كيس", "1"), "أكياس": ("عدد أكياس", "كيس", "1"),
    "sachet": ("عدد أكياس", "كيس", "1"), "sachets": ("عدد أكياس", "كيس", "1"),
    "شريط": ("عدد شرائط", "شريط", "1"), "شرائط": ("عدد شرائط", "شريط", "1"),
    "عبوة": ("عدد عبوات", "عبوة", "1"), "عبوات": ("عدد عبوات", "عبوة", "1"),
}
_UNIT_PATTERN = "|".join(sorted((re.escape(k) for k in _SIZE_UNITS), key=len, reverse=True))
# Match stand-alone digits in labels, not embedded into model identifiers such as X100ML2.
_PACKAGE_PATTERN = re.compile(
    r"(?<![\w])(?P<amount>[0-9]+(?:[.,٫][0-9]+)?)\s*(?P<unit>" + _UNIT_PATTERN + r")(?![\w])",
    flags=re.IGNORECASE,
)


def _canonical_package_specs(name: Any):
    label = unicodedata.normalize("NFKC", normalize_name(name)).translate(_ARABIC_DIGITS)
    # Normalize the Arabic decimal mark and optional arabic comma for numbers.
    label = label.replace("٫", ".")
    found = []
    spans = []
    for match in _PACKAGE_PATTERN.finditer(label):
        unit = match.group("unit").casefold()
        kind, common_unit, factor = _SIZE_UNITS[unit]
        try:
            value = Decimal(match.group("amount").replace(",", ".")) * Decimal(factor)
        except InvalidOperation:
            continue
        found.append((kind, common_unit, value))
        spans.append(match.span())
    remainder_parts = []
    last = 0
    for start, end in spans:
        remainder_parts.append(label[last:start]); last = end
    remainder_parts.append(label[last:])
    remainder = re.sub(r"[^\w\u0600-\u06ff]+", " ", " ".join(remainder_parts))
    remainder = re.sub(r"\s+", " ", remainder).strip()
    return sorted(found), remainder


def classify_pack_difference(system_name: Any, salla_name: Any) -> dict:
    """Separate confirmed quantitative changes from incomplete package descriptions.

    This is an explicit-units heuristic, not proof of product identity.
    """
    system_specs, system_rest = _canonical_package_specs(system_name)
    salla_specs, salla_rest = _canonical_package_specs(salla_name)

    def format_decimal(value):
        normal = format(value, "f")
        return normal.rstrip("0").rstrip(".") if "." in normal else normal

    fmt = lambda specs: "، ".join(f"{format_decimal(v)} {unit}" for _, unit, v in specs)
    ret = {
        "الكمية/الحجم في النظام": fmt(system_specs),
        "الكمية/الحجم في سلة": fmt(salla_specs),
        "نوع اختلاف الاسم": "اختلاف نص الاسم", "درجة تأكيد المقاس": "—"
    }
    if system_specs and salla_specs:
        from collections import defaultdict
        def by_kind(specs):
            groups = defaultdict(list)
            for kind, unit, value in specs:
                groups[(kind, unit)].append(value)
            return {k: sorted(v) for k, v in groups.items()}
        system_groups, salla_groups = by_kind(system_specs), by_kind(salla_specs)
        common = system_groups.keys() & salla_groups.keys()
        changed = [kind for kind in common if system_groups[kind] != salla_groups[kind]]
        if changed:
            kind = " / ".join(sorted({item[0] for item in changed}))
            suffix = "فقط" if system_rest == salla_rest and system_groups.keys() == salla_groups.keys() else "مع اختلافات إضافية"
            ret["نوع اختلاف الاسم"] = f"اختلاف {kind} {suffix}"
            ret["درجة تأكيد المقاس"] = "مرتفع" if suffix == "فقط" else "مرشح — مراجعة"
        elif not common and len(system_specs) == len(salla_specs) == 1:
            kinds = " / ".join(sorted({item[0] for item in system_specs + salla_specs}))
            ret["نوع اختلاف الاسم"] = f"اختلاف نوع الوحدة ({kinds}) — مراجعة"
            ret["درجة تأكيد المقاس"] = "تحتاج مراجعة"
        elif system_groups != salla_groups:
            ret["نوع اختلاف الاسم"] = "وحدات/تفاصيل عبوة غير متطابقة — مراجعة"
            ret["درجة تأكيد المقاس"] = "غير محسوم"
    elif bool(system_specs) != bool(salla_specs):
        ret["نوع اختلاف الاسم"] = "وجود مقدار بوصف واحد فقط — مراجعة"
        ret["درجة تأكيد المقاس"] = "غير محسوم"
    return ret


def normalize_exclusion_skus(exclusions) -> set[str]:
    """Accept an iterable of identifiers; never exclude on vague name matches."""
    if exclusions is None:
        return set()
    return {normalized for item in exclusions if (normalized := normalize_sku(item))}

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
    excluded_name_skus=None,
    excluded_price_skus=None,
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

    name_excluded = normalize_exclusion_skus(excluded_name_skus)
    price_excluded = normalize_exclusion_skus(excluded_price_skus)

    # On common SKUs, ignore invalid values in a discrepancy claim; show them as issues instead.
    different_name = common.loc[common["_name_system"].ne(common["_name_salla"]) & ~common["_sku"].isin(name_excluded)].copy()
    if not different_name.empty:
        variations = different_name.apply(
            lambda r: classify_pack_difference(r["اسم المنتج_system"], r["اسم المنتج_salla"]), axis=1
        ).tolist()
        for field in ("نوع اختلاف الاسم", "الكمية/الحجم في النظام", "الكمية/الحجم في سلة", "درجة تأكيد المقاس"):
            different_name[field] = [v[field] for v in variations]
    else:
        for field in ("نوع اختلاف الاسم", "الكمية/الحجم في النظام", "الكمية/الحجم في سلة", "درجة تأكيد المقاس"):
            different_name[field] = pd.Series(dtype="string")
    significant_name = different_name.loc[
        different_name["نوع اختلاف الاسم"].ne("اختلاف نص الاسم")
    ].copy()
    different_price = common.loc[common.apply(
        lambda row: row["_price_system"] is not None and row["_price_salla"] is not None
        and abs(row["_price_system"] - row["_price_salla"]) > tolerance and row["_sku"] not in price_excluded, axis=1
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
        cols += [c for c in ("نوع اختلاف الاسم", "الكمية/الحجم في النظام", "الكمية/الحجم في سلة", "درجة تأكيد المقاس") if c in paired.columns]
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
            "size_count_differences": len(significant_name),
            "confirmed_size_count_differences": int(significant_name["درجة تأكيد المقاس"].eq("مرتفع").sum()) if not significant_name.empty else 0,
            "name_exclusions_applied": len(name_excluded & set(common["_sku"])),
            "price_exclusions_applied": len(price_excluded & set(common["_sku"])),
            "problems": len(problems),
            "ambiguous_skus": len(ambiguities),
        },
        "new": clean_new.reset_index(drop=True),
        "names": display(different_name),
        "sizes": display(significant_name),
        "name_exclusions": pd.DataFrame({"SKU": sorted(name_excluded), "سبب الاستبعاد": "مستبعد من الأسماء فقط"}),
        "price_exclusions": pd.DataFrame({"SKU": sorted(price_excluded), "سبب الاستبعاد": "مستبعد من الأسعار فقط"}),
        "prices": display(different_price, include_diff=True),
        "taxes": display(different_tax),
        "salla_only": display(salla_only),
        "problems": problems.reset_index(drop=True),
    }
