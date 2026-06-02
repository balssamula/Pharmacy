import streamlit as st
import pandas as pd
import sqlite3
from io import BytesIO
from datetime import datetime
from utils.database import DB_PATH

def show():
    st.markdown(
        """
        <div class="hero">
            <h1>👥 مراقبة تعديلات الصيدليات</h1>
            <p>متابعة إنجازات الصيادلة وتعديلاتهم على الطلبات</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    # عرض الصيادلة المسجلين
    st.markdown('<div class="section-title">👤 الصيادلة المسجلون</div>', unsafe_allow_html=True)
    
    conn = sqlite3.connect(DB_PATH)
    try:
        pharmacists_df = pd.read_sql_query("""
            SELECT username, pharmacist_name, last_login
            FROM users
            WHERE role = 'pharmacy' AND pharmacist_name != ''
            ORDER BY last_login DESC
        """, conn)
        
        if not pharmacists_df.empty:
            st.dataframe(pharmacists_df.rename(columns={
                "username": "اسم المستخدم",
                "pharmacist_name": "اسم الصيدلي",
                "last_login": "آخر دخول"
            }), use_container_width=True)
        else:
            st.info("لا يوجد صيادلة مسجلون بعد")
        
        st.markdown("---")
        
        # عرض التعديلات
        st.markdown('<div class="section-title">📋 سجل التعديلات</div>', unsafe_allow_html=True)
        
        adjustments_df = pd.read_sql_query("""
            SELECT order_number, sku, product_name, pharmacy_name, case_type, 
                   status, performed_by, performed_at, pharmacist_note
            FROM reconciliation_items
            WHERE performed_by != '' AND status = 'تم'
            ORDER BY performed_at DESC
            LIMIT 100
        """, conn)
        
        if not adjustments_df.empty:
            adjustments_df = adjustments_df.rename(columns={
                "order_number": "رقم الطلب",
                "sku": "SKU",
                "product_name": "المنتج",
                "pharmacy_name": "الصيدلية",
                "case_type": "نوع الإجراء",
                "status": "الحالة",
                "performed_by": "تم بواسطة",
                "performed_at": "تاريخ التنفيذ",
                "pharmacist_note": "ملحوظة"
            })
            st.dataframe(adjustments_df, use_container_width=True)
            
            output = BytesIO()
            adjustments_df.to_excel(output, index=False)
            output.seek(0)
            st.download_button(
                "📥 تصدير سجل التعديلات إلى Excel",
                data=output,
                file_name=f"pharmacy_adjustments_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        else:
            st.info("لا توجد تعديلات مسجلة بعد")
    finally:
        conn.close()