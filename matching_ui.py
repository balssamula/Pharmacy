"""Streamlit SKU reconciliation UI. Import and review are read-only.

Only the explicit, confirmed 'رفع المنتجات الجديدة' action sends a Salla API call.
"""
from __future__ import annotations

import hashlib
import io
import math
import re

import pandas as pd
import requests
import streamlit as st

from matching_engine import compare_catalogs
from utils import generate_salla_new_products_file

_IMPORT_URL = "https://api.salla.dev/admin/v2/products/import"
_TAX_CAUSES = [
    "الأدوية والمعدات الطبية", "الخدمات المالية", "عقد تأمين على الحياة",
    "التوريدات العقارية المعفاة", "صادرات السلع من المملكة", "صادرات الخدمات من المملكة",
    "النقل الدولي للسلع", "النقل الدولي للركاب", "توريد وسائل النقل",
]


def _csv_bytes(df: pd.DataFrame) -> bytes:
    # When opened in Excel, never interpret store-originated strings as formula commands.
    safe = df.copy()
    for col in safe.select_dtypes(include=["object", "string"]).columns:
        safe[col] = safe[col].map(
            lambda v: ("'" + v) if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@")) else v
        )
    return safe.to_csv(index=False).encode("utf-8-sig")


def _report_section(title: str, frame: pd.DataFrame, file_name: str) -> None:
    st.caption(f"إجمالي النتائج: {len(frame):,} سجل. تعرض الواجهة أول 300 نتيجة فقط؛ التقرير قابل لتنزيله بالكامل.")
    if frame.empty:
        st.success("لا توجد اختلافات في هذا القسم.")
        return
    query = st.text_input("بحث برقم SKU أو اسم المنتج", key=f"find_{file_name}")
    filtered = frame
    if query:
        literal = re.escape(query.strip())
        cols = [c for c in frame.columns if c == "SKU" or "اسم" in c or "الاسم" in c]
        if cols:
            mask = pd.Series(False, index=frame.index)
            for col in cols:
                mask |= frame[col].astype(str).str.contains(literal, case=False, regex=True, na=False)
            filtered = frame.loc[mask]
    st.dataframe(filtered.head(300), use_container_width=True, hide_index=True)
    st.download_button(
        f"📥 تنزيل جميع نتائج {title} (CSV)",
        data=_csv_bytes(filtered), file_name=file_name + ".csv",
        mime="text/csv", use_container_width=True, key=f"download_{file_name}"
    )


def _render_new_products(frame: pd.DataFrame, headers: dict, report_id: str) -> None:
    merchant = str(st.session_state.get("merchant_id", ""))
    selection_key = f"matching_selected_{merchant}_{report_id}"
    revision_key = f"matching_revision_{merchant}_{report_id}"
    selected = st.session_state.setdefault(selection_key, set())
    st.session_state.setdefault(revision_key, 0)
    ready = frame.loc[frame["صلاحية الرفع"].eq("جاهز")].copy()
    invalid_count = len(frame) - len(ready)
    st.info(f"المنتجات الجديدة: {len(frame):,} | الصالحة للتحضير: {len(ready):,} | تحتاج مراجعة: {invalid_count:,}")
    if invalid_count:
        st.warning("بعض المنتجات الجديدة لديها اسم أو سعر أو قيمة ضريبة غير صالحة؛ لن تدخل في ملف الرفع.")
    if ready.empty:
        _report_section("المنتجات الجديدة", frame, "new_products_reconciliation")
        return
    query = st.text_input("🔎 البحث ضمن المنتجات الجديدة (SKU أو الاسم)", key=f"search_new_{report_id}")
    mask = ready["SKU"].astype(str).str.contains(re.escape(query), case=False, na=False) | ready["اسم المنتج"].astype(str).str.contains(re.escape(query), case=False, na=False)
    filtered = ready.loc[mask]
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button(f"☑️ تحديد كل نتائج البحث ({len(filtered):,})", key=f"all_{report_id}", use_container_width=True):
            selected.update(filtered["SKU"].tolist())
            st.session_state[revision_key] += 1
            st.rerun()
    with col2:
        if st.button("⬜ إلغاء التحديد", key=f"clear_{report_id}", use_container_width=True):
            selected.clear()
            st.session_state[revision_key] += 1
            st.rerun()
    with col3:
        st.metric("المحدد للرفع", len(selected))

    per_page = 80
    pages = max(1, math.ceil(len(filtered) / per_page))
    page = st.number_input("صفحة المنتجات", min_value=1, max_value=pages, value=1, step=1, key=f"new_page_{report_id}")
    portion = filtered.iloc[(page - 1) * per_page : page * per_page].copy()
    portion.insert(0, "اختيار", portion["SKU"].isin(selected))
    edited = st.data_editor(
        portion, hide_index=True, use_container_width=True,
        key=f"edit_new_{report_id}_{page}_{st.session_state[revision_key]}",
        disabled=[c for c in portion.columns if c != "اختيار"],
        column_config={"اختيار": st.column_config.CheckboxColumn("اختيار", default=False)},
    )
    for sku, checked in zip(edited["SKU"], edited["اختيار"]):
        if checked:
            selected.add(sku)
        else:
            selected.discard(sku)

    st.download_button(
        "📥 تنزيل تقرير جميع المنتجات الجديدة", data=_csv_bytes(frame),
        file_name="new_products_reconciliation.csv", mime="text/csv", use_container_width=True,
        key=f"dl_new_{report_id}"
    )
    chosen = ready.loc[ready["SKU"].isin(selected)].copy()
    if chosen.empty:
        st.caption("حدد المنتجات التي تريد رفعها أولاً. لن يُرفع شيء تلقائيًا.")
        return
    if len(chosen) > 1000:
        st.warning("يفضّل تقسيم الرفع إلى دفعات لا تتجاوز 1000 منتج؛ ألغِ تحديد بعض المنتجات.")
        return
    from matching_engine import parse_tax, parse_price
    non_taxable = chosen["خاضع للضريبة؟"].map(parse_tax).eq(False)
    reason = ""
    if non_taxable.any():
        st.warning("اختر سبب عدم الخضوع للضريبة الصحيح بعد التأكد من تصنيف المنتجات. لن يُفترض أن جميعها أدوية تلقائيًا.")
        reason = st.selectbox("سبب الإعفاء للمنتجات غير الخاضعة المختارة", ["— اختر بعد التحقق —"] + _TAX_CAUSES, key=f"tax_reason_{report_id}")
    products = []
    for row in chosen.to_dict("records"):
        is_tax = parse_tax(row["خاضع للضريبة؟"])
        price = parse_price(row["سعر المنتج"])
        products.append({
            "name": str(row["اسم المنتج"]), "sku": str(row["SKU"]),
            "price": float(price), "with_tax": is_tax,
            "tax_exemption_cause": reason if is_tax is False else "",
        })
    if not st.session_state.get("access_token") or not merchant:
        st.error("لا يوجد متجر مصادق عليه. أعد اختيار المتجر قبل تجهيز الرفع.")
        return
    if non_taxable.any() and reason.startswith("—"):
        st.info("حدد سببًا صحيحًا قبل تجهيز القالب أو الإرسال.")
        return
    template_bytes = generate_salla_new_products_file(products)
    if not template_bytes:
        st.error("تعذر إنشاء قالب سلة.")
        return
    st.download_button("📄 تنزيل قالب سلة للمنتجات المختارة (مراجعة قبل الرفع)",
                       template_bytes, file_name="Salla_Selected_New_Products.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       key=f"template_{report_id}", use_container_width=True)
    st.warning(
        "⚠️ قالب إضافة المنتجات الحالي في التطبيق يضع افتراضياً «يتطلب شحن = نعم»، "
        "«الوزن = 1 كجم»، «أقصى كمية = 50»، ويترك التصنيف فارغاً. "
        "راجع ملاءمة هذه القيم قبل الضغط على الرفع."
    )
    confirmation = st.checkbox(
        f"أؤكد مراجعة أسماء وأسعار وضريبة {len(products):,} منتج وأوافق على إرسالها إلى المتجر: {st.session_state.get('store_name', merchant)}",
        value=False, key=f"confirm_upload_{report_id}",
    )
    fingerprint = hashlib.sha256((merchant + report_id + repr(sorted(selected)) + reason).encode("utf-8")).hexdigest()
    already_submitted = st.session_state.get("matching_last_batch_fingerprint") == fingerprint
    if already_submitted:
        st.info("سبق إرسال هذه الدفعة للمعالجة. راجع نتيجة الاستيراد في سلة ثم أعد المطابقة قبل أي إرسال جديد.")
    if st.button(f"🚀 رفع المنتجات الجديدة المختارة ({len(products):,})", type="primary",
                 use_container_width=True, disabled=not confirmation or already_submitted,
                 key=f"send_new_{report_id}"):
        # No background API calls while previewing. A deliberate click is required.
        try:
            upload_headers = dict(headers)
            upload_headers.pop("Content-Type", None)
            response = requests.post(
                _IMPORT_URL, headers=upload_headers,
                files={"file": ("Salla_Selected_New_Products.xlsx", template_bytes,
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                data={"type": "products"}, timeout=(10, 90),
            )
            successful = response.status_code == 201
            if successful:
                st.session_state["matching_last_batch_fingerprint"] = fingerprint
                st.success("✅ قُبل الملف في سلة للمعالجة. تأكد من نتيجة الاستيراد لاحقًا؛ القبول لا يضمن اكتمال إضافة كل المنتجات.")
            else:
                st.error(f"لم يقبل سلة ملف الاستيراد (رمز HTTP {response.status_code}). راجع صلاحيات المنتجات والقالب وسجل الأخطاء.")
        except requests.RequestException:
            st.error("تعذر الاتصال بسلة أو انتهت مهلة الطلب. تحقق من سجل الاستيراد قبل محاولة إعادة الإرسال.")


def render_matching_panel(headers: dict) -> None:
    st.markdown("### 🔄 مطابقة منتجات سلة مع النظام الداخلي")
    st.caption("المطابقة حسب SKU؛ اختلاف السعر والقيمة الضريبية يُراجع للمقارنة بنفس الأساس المحاسبي. التحليل لا يغيّر أي منتج.")
    c1, c2 = st.columns([2, 1])
    with c1:
        excluded = st.text_input("🚫 استبعاد تصنيفات النظام (مفصولة بفاصلة)", placeholder="مثال: اكسسوارات", key="matching_exclude")
    with c2:
        tolerance = st.number_input("هامش اختلاف السعر (ر.س)", min_value=0.0, max_value=100.0, value=0.01, step=0.01, format="%.2f", key="matching_tolerance")
    uploaded = st.file_uploader("📂 رفع ملف Excel: ورقتا salla و system", type=["xlsx"], key="matching_uploaded")
    if uploaded is None:
        st.info("ارفع الملف ثم اضغط «بدء المطابقة وتحليل الاختلافات».")
        return
    data = uploaded.getvalue()
    if len(data) > 30 * 1024 * 1024:
        st.error("حجم ملف المطابقة يتجاوز 30 MB؛ يرجى تصغير الملف.")
        return
    file_id = hashlib.sha256(data + excluded.encode("utf-8") + str(tolerance).encode("utf-8")).hexdigest()[:24]
    merchant = str(st.session_state.get("merchant_id", "unselected"))
    report_id = f"{merchant}_{file_id}"
    if st.button("🔍 بدء المطابقة وتحليل اختلافات SKU والأسماء والأسعار والضريبة", type="primary", use_container_width=True, key="matching_start"):
        try:
            xl = pd.ExcelFile(io.BytesIO(data))
            if not {"salla", "system"}.issubset(set(xl.sheet_names)):
                st.error("الملف يجب أن يحتوي على ورقتين باسم salla و system.")
                return
            salla = pd.read_excel(xl, sheet_name="salla", dtype={"رقم المنتج": "string"})
            system = pd.read_excel(xl, sheet_name="system", dtype={"رقم المنتج": "string"})
            st.session_state["matching_report"] = compare_catalogs(salla, system, excluded, tolerance)
            st.session_state["matching_report_id"] = report_id
        except Exception as exc:
            st.error(f"تعذرت قراءة الملف أو التحليل: {type(exc).__name__}: {exc}")
            return
    if st.session_state.get("matching_report_id") != report_id:
        st.info("اضغط زر بدء المطابقة لعرض نتائج هذا الملف والإعدادات الحالية.")
        return
    results = st.session_state["matching_report"]
    stats = results["summary"]
    a,b,c,d = st.columns(4)
    a.metric("SKU مشتركة قابلة للمقارنة", f"{stats['comparable_common_skus']:,}")
    b.metric("منتجات جديدة", f"{stats['new_products']:,}")
    c.metric("اختلافات السعر", f"{stats['different_prices']:,}")
    d.metric("اختلافات الضريبة", f"{stats['different_taxes']:,}")
    st.caption(f"اختلاف الاسم: {stats['different_names']:,} | موجودة بسلة فقط: {stats['salla_only']:,} | سجلات تتطلب مراجعة: {stats['problems']:,} | تصنيفات مستبعدة: {stats['excluded_system_rows']:,}")
    tabs = st.tabs([
        f"🆕 منتجات جديدة ({stats['new_products']:,})",
        f"🏷️ أسماء مختلفة ({stats['different_names']:,})",
        f"💰 أسعار مختلفة ({stats['different_prices']:,})",
        f"🧾 ضريبة مختلفة ({stats['different_taxes']:,})",
        f"⚠️ تكرار / بيانات ناقصة ({stats['problems']:,})",
        f"📦 سلة فقط ({stats['salla_only']:,})",
    ])
    with tabs[0]: _render_new_products(results["new"], headers, report_id)
    with tabs[1]: _report_section("اختلاف الأسماء", results["names"], "mismatched_names")
    with tabs[2]:
        st.warning("تأكد أن سعر سلة وسعر النظام كلاهما شاملان للضريبة أو كلاهما غير شاملين، وأن السعر ليس سعر عرض ترويجي.")
        _report_section("اختلاف الأسعار", results["prices"], "mismatched_prices")
    with tabs[3]: _report_section("اختلاف الضريبة", results["taxes"], "mismatched_taxes")
    with tabs[4]: _report_section("المشاكل", results["problems"], "duplicate_or_invalid_skus")
    with tabs[5]: _report_section("موجودة في سلة فقط", results["salla_only"], "salla_only")
