import streamlit as st
import pandas as pd
from utils.helpers import status_pill, case_pill, numeric_value

def render_metrics(df: pd.DataFrame):
    if df.empty:
        return
    cols = st.columns(6)
    metrics = [
        ("إجمالي الحالات", len(df)),
        ("إضافات", int((df["case_type"] == "addition").sum())),
        ("إرجاعات", int((df["case_type"] == "return").sum())),
        ("طلبات بدون فاتورة", int((df["case_type"] == "orphan_salla").sum())),
        ("فواتير بدون طلب", int((df["case_type"] == "orphan_abc").sum())),
        ("تم إنجازها", int((df["status"] == "تم").sum())),
    ]
    for col, (label, value) in zip(cols, metrics):
        with col:
            st.markdown(f"""
            <div class="metric-box">
                <div style="font-size:0.88rem;color:#5a7380;">{label}</div>
                <div style="font-size:2rem;font-weight:800;color:#16425b;">{value}</div>
            </div>
            """, unsafe_allow_html=True)

def render_completed_table(df: pd.DataFrame, is_admin: bool = False):
    if df.empty:
        st.info("لا توجد طلبات مكتملة بعد.")
        return
    display_df = df.rename(columns={
        "order_number": "رقم الطلب", "invoice_number": "رقم الفاتورة", "sku": "SKU",
        "product_name": "المنتج", "case_label": "نوع الإجراء", "performed_by": "تم بواسطة",
        "performed_at": "تاريخ الإكمال", "pharmacy_name": "الصيدلية", "abc_pharmacist_name": "الصيدلي"
    })
    cols = ["رقم الطلب", "رقم الفاتورة", "SKU", "المنتج", "نوع الإجراء", "تم بواسطة", "تاريخ الإكمال"]
    if is_admin:
        cols.insert(1, "الصيدلية")
        cols.insert(2, "الصيدلي")
    st.dataframe(display_df[cols], use_container_width=True)