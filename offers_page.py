import streamlit as st
from datetime import datetime
import pandas as pd
import re
from utils import (
    get_headers, safe_api_request, SALLA_API_URL, generate_salla_excel_template,
    process_excel_import, export_offers_to_excel, safe_parse_date, parse_products_cleanly
)

def render_offers_page():
    st.markdown("<h2 style='color:#0f1c2e;'>📊 لوحة إدارة العروض الاحترافية</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color:#555;'>إدارة شاملة للعروض مع التصفية الجمالية والتعديل الجماعي المتقدم.</p>", unsafe_allow_html=True)
    
    # --- استيراد وتصدير جماعي ---
    col_info, col_btn = st.columns([3, 1])
    with col_info:
        st.info("📥 قم بتنزيل النموذج وتعبئة البيانات بالصيغ المحددة ثم ارفع الملف أدناه.")
    with col_btn:
        st.download_button(
            label="📥 تحميل نموذج الـ Excel",
            data=generate_salla_excel_template(),
            file_name="Salla_Offers_Template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    
    uploaded_file = st.file_uploader("📂 اختر ملف العروض بصيغة XLSX:", type=["xlsx"])
    if uploaded_file:
        try:
            df_user = pd.read_excel(uploaded_file)
            st.dataframe(df_user, use_container_width=True)
            if st.button("🚀 تأكيد النشر الجماعي للملف", use_container_width=True, type="primary"):
                with st.spinner("جاري المعالجة..."):
                    res = process_excel_import(df_user)
                    for m in res["success"]: st.success(m)
                    for m in res["errors"]: st.error(m)
                st.rerun()
        except Exception as e:
            st.error(f"خطأ في قراءة الملف: {str(e)}")

    st.divider()

    # --- جلب وعرض البيانات الفعلي ---
    headers = get_headers()
    if not headers: return

    with st.spinner("🔄 جاري مزامنة العروض من سلة..."):
        res = safe_api_request("GET", SALLA_API_URL, headers)
    
    if res and res.get("data"):
        raw_offers = res["data"]
        
        # الفلترة المتقدمة
        col1, col2 = st.columns(2)
        with col1:
            search_offer = st.text_input("🔎 ابحث باسم العرض أو المعرف:")
        with col2:
            offer_status_filter = st.selectbox("📌 تصفية حسب الحالة:", ["الكل", "نشط", "غير نشط"])
        
        now = datetime.now()
        
        for idx, offer in enumerate(raw_offers):
            offer_id = offer.get('id', 'N/A')
            offer_name = offer.get('name', 'عرض بدون اسم')
            status = offer.get('status', 'inactive')
            
            # تطبيق الفلترة
            if search_offer and (search_offer.lower() not in offer_name.lower() and search_offer not in str(offer_id)):
                continue
            if offer_status_filter == "نشط" and status != "active": continue
            if offer_status_filter == "غير نشط" and status == "active": continue
            
            # --- تصميم الحاوية الإبداعية الفاخرة ---
            status_badge = "🟢 نشط ومفعل" if status == "active" else "🔴 متوقف حالياً"
            
            # 1. رأس الحاوية (Dark Header Container)
            st.markdown(f"""
                <div style="background: linear-gradient(135deg, #0f1c2e 0%, #1f3a60 100%); 
                            padding: 12px 20px; border-radius: 12px 12px 0px 0px; 
                            margin-top: 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 3px solid #00b4d8;">
                    <span style="color: #ffffff; font-weight: bold; font-size: 16px;">🎯 {offer_name} (ID: {offer_id})</span>
                    <span style="background: rgba(255,255,255,0.2); color: #fff; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600;">{status_badge}</span>
                </div>
            """, unsafe_allow_html=True)
            
            # 2. جسم الحاوية السفلي (Data Container)
            with st.container():
                st.markdown("""
                    <div style="background-color: #ffffff; padding: 20px; border-radius: 0px 0px 12px 12px; 
                                border: 1px solid #e8edf2; border-top: none; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 20px;">
                """, unsafe_allow_html=True)
                
                # تفاصيل العرض في أعمدة داخل الجسد
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown(f"**📅 تاريخ البدء:**\n`{offer.get('start_date', 'غير محدد')}`")
                    st.markdown(f"**📅 تاريخ الانتهاء:**\n`{offer.get('expiry_date', 'غير محدد')}`")
                with c2:
                    st.markdown(f"**🛒 نوع التطبيق:** `{offer.get('applied_to', 'product')}`")
                    st.markdown(f"**🔖 الكوبون:** {'نعم (مربوط بكوبون)' if offer.get('applied_with_coupon') else 'لا يحتاج كوبون'}")
                with c3:
                    st.markdown(f"**📢 الرسالة الترويجية:**\n*{offer.get('message', 'لا توجد رسالة')}*")
                
                st.markdown("<hr style='margin: 10px 0; border-top: 1px dashed #ddd;'>", unsafe_allow_html=True)
                
                # تفاصيل المنتجات المشمولة بالعرض (X و Y)
                cx, cy = st.columns(2)
                with cx:
                    st.markdown("<b style='color:#0f1c2e;'>🛒 منتجات الشراء المطلوبة (X):</b>", unsafe_allow_html=True)
                    st.text(parse_products_cleanly(offer.get('buy', {}).get('products', [])))
                    st.caption(f"الكمية المطلوبة: {offer.get('buy', {}).get('quantity', 1)}")
                with cy:
                    st.markdown("<b style='color:#0f1c2e;'>🎁 المنتجات الهدايا / المخصومة (Y):</b>", unsafe_allow_html=True)
                    st.text(parse_products_cleanly(offer.get('get', {}).get('products', [])))
                    st.caption(f"كمية الهدية: {offer.get('get', {}).get('quantity', 1)}")

                # أزرار الإجراءات السريعة في الأسفل تظهر بشكل نظيف
                st.markdown("<br>", unsafe_allow_html=True)
                btn_col1, btn_col2, btn_col3 = st.columns(3)
                with btn_col1:
                    target_status = "inactive" if status == "active" else "active"
                    lbl = "⏸️ إيقاف مؤقت" if status == "active" else "▶️ تفعيل العرض"
                    if st.button(lbl, key=f"tgl_{offer_id}_{idx}", use_container_width=True):
                        safe_api_request("PUT", f"{SALLA_API_URL}/{offer_id}/status", headers, json={"status": target_status})
                        st.rerun()
                with btn_col2:
                    if st.button("🔖 تبديل حالة الكوبون", key=f"cpn_{offer_id}_{idx}", use_container_width=True):
                        safe_api_request("PUT", f"{SALLA_API_URL}/{offer_id}", headers, json={"applied_with_coupon": not offer.get('applied_with_coupon', False)})
                        st.rerun()
                with btn_col3:
                    if st.button("🗑️ حذف العرض نهائياً", key=f"del_{offer_id}_{idx}", type="primary", use_container_width=True):
                        safe_api_request("DELETE", f"{SALLA_API_URL}/{offer_id}", headers)
                        st.rerun()
                        
                st.markdown("</div>", unsafe_allow_html=True)
