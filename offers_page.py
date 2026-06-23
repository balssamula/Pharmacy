import streamlit as st
from datetime import datetime
import pandas as pd
import re
from utils import (
    get_headers, safe_api_request, SALLA_API_URL, generate_salla_excel_template,
    process_excel_import, export_offers_to_excel, safe_parse_date, parse_products_cleanly
)

def render_offers_page():
    st.markdown("<h2 style='color:#0f1c2e;'>📊 لوحة إدارة وتصفية العروض الحالية</h2>", unsafe_allow_html=True)
    
    headers = get_headers()
    if not headers: return

    # --- تنزيل وتصدير واستيراد العروض ---
    col_dl, col_ex = st.columns([1, 1])
    with col_dl:
        st.download_button(
            label="📥 تنزيل نموذج الاستيراد الـ Excel",
            data=generate_salla_excel_template(),
            file_name="Salla_Offers_Template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
    with st.spinner("جاري جلب العروض لإعداد التصدير..."):
        res_all = safe_api_request("GET", SALLA_API_URL, headers)
        raw_offers = res_all.get("data", []) if res_all else []
        
    with col_ex:
        if raw_offers:
            st.download_button(
                label="📥 تصدير العروض الحالية إلى Excel",
                data=export_offers_to_excel(raw_offers),
                file_name=f"offers_export_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

    uploaded_file = st.file_uploader("📂 تحميل ملف عروض جماعي جديد (XLSX):", type=["xlsx"])
    if uploaded_file:
        df_user = pd.read_excel(uploaded_file)
        st.dataframe(df_user, use_container_width=True)
        if st.button("🚀 تأكيد النشر الجماعي للعروض الحالية", use_container_width=True, type="primary"):
            res = process_excel_import(df_user)
            for m in res["success"]: st.success(m)
            for m in res["errors"]: st.error(m)
            st.rerun()

    st.divider()

    # --- نموذج إنشاء عرض جديد (الذي تم استرجاعه) ---
    with st.expander("➕ إنشاء عرض ترويجي جديد في سلة", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            new_name = st.text_input("اسم العرض الجديد:")
            new_type = st.selectbox("نوع العرض:", ["buy_x_get_y", "percentage", "fixed_amount"])
            new_buy_qty = st.number_input("كمية الشراء المطلوبة (X):", min_value=1, value=1)
            new_buy_p = st.text_input("معرفات منتجات الشراء (مفصولة بفاصلة):")
        with c2:
            new_msg = st.text_input("الرسالة الترويجية التسويقية:")
            new_coupon = st.selectbox("تطبيق مع كوبون؟", ["لا", "نعم"])
            new_get_qty = st.number_input("كمية الهدية / التخفيض (Y):", min_value=1, value=1)
            new_get_p = st.text_input("معرفات منتجات الهدية (مفصولة بفاصلة):")
            
        c_d1, c_d2 = st.columns(2)
        with c_d1: new_start = st.text_input("تاريخ البدء:", value=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        with c_d2: new_expiry = st.text_input("تاريخ الانتهاء:", value="2026-12-31 23:59:59")
        
        if st.button("🚀 نشر العرض الترويجي الآن للمتجر", type="primary", use_container_width=True):
            payload = {
                "name": new_name, "offer_type": new_type, "message": new_msg, "applied_with_coupon": new_coupon == "نعم",
                "start_date": new_start, "expiry_date": new_expiry, "status": "active",
                "buy": {"type": "product", "quantity": int(new_buy_qty), "products": [int(i.strip()) for i in new_buy_p.split(",") if i.strip().isdigit()]},
                "get": {"type": "product", "quantity": int(new_get_qty), "discount_type": "free-product", "products": [int(i.strip()) for i in new_get_p.split(",") if i.strip().isdigit()]}
            }
            if safe_api_request("POST", SALLA_API_URL, headers, json=payload):
                st.success("✅ تم إنشاء ونشر العرض بنجاح!")
                st.rerun()

    st.divider()

    # --- الفلترة والبحث المتقدم مع فلتر تاريخ الانتهاء المطلوب ---
    st.markdown("#### 🔍 أدوات التصفية المتقدمة")
    f1, f2, f3 = st.columns(3)
    with f1: search_offer = st.text_input("🔎 ابحث باسم العرض أو بالمعرف الرقمي:")
    with f2: status_filter = st.selectbox("📌 حالة النشاط بالمتجر:", ["الكل", "نشط", "غير نشط"])
    with f3: expiry_filter = st.selectbox("📅 تصفية حسب تاريخ الانتهاء الصلاحي:", ["الكل", "عروض سارية وغير منتهية", "عروض منتهية الصلاحية"])

    now = datetime.now()

    # حلقة العرض الجمالية الإبداعية
    for idx, offer in enumerate(raw_offers):
        offer_id = offer.get('id', 'N/A')
        offer_name = offer.get('name', 'عرض بدون اسم')
        status = offer.get('status', 'inactive')
        exp_date = safe_parse_date(offer.get('expiry_date'))
        
        # تطبيق منطق الفلاتر بالكامل
        if search_offer and (search_offer.lower() not in offer_name.lower() and search_offer not in str(offer_id)): continue
        if status_filter == "نشط" and status != "active": continue
        if status_filter == "غير نشط" and status == "active": continue
        
        is_expired = exp_date and exp_date < now
        if expiry_filter == "عروض سارية وغير منتهية" and is_expired: continue
        if expiry_filter == "عروض منتهية الصلاحية" and not is_expired: continue
        
        # ترويسة العرض الداكنة الفخمة
        badge = "🟢 نشط بالمتجر" if status == "active" else "🔴 متوقف حالياً"
        exp_badge = "⚠️ منتهي الصلاحية" if is_expired else "⏳ ساري الصلاحية"
        
        st.markdown(f"""
            <div style="background: linear-gradient(135deg, #0f1c2e 0%, #1a365d 100%); 
                        padding: 12px 20px; border-radius: 12px 12px 0px 0px; 
                        margin-top: 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 3px solid #00b4d8;">
                <span style="color: #ffffff; font-weight: bold; font-size: 16px;">🎯 {offer_name} (ID: {offer_id})</span>
                <div>
                    <span style="background: rgba(255,255,255,0.2); color: #fff; padding: 4px 10px; border-radius: 15px; font-size: 12px; margin-left:10px;">{badge}</span>
                    <span style="background: rgba(255,193,7,0.3); color: #fff; padding: 4px 10px; border-radius: 15px; font-size: 12px;">{exp_badge}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # جسم الحاوية
        with st.container():
            st.markdown("""
                <div style="background-color: #ffffff; padding: 20px; border-radius: 0px 0px 12px 12px; 
                            border: 1px solid #e8edf2; border-top: none; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 20px;">
            """, unsafe_allow_html=True)
            
            cx, cy = st.columns(2)
            with cx:
                st.markdown(f"**📅 تاريخ البدء:** `{offer.get('start_date', 'غير محدد')}`")
                st.markdown(f"**📅 تاريخ الانتهاء:** `{offer.get('expiry_date', 'غير محدد')}`")
            with cy:
                st.markdown(f"**🔖 متوافق مع كوبون:** `{'نعم' if offer.get('applied_with_coupon') else 'لا'}`")
                st.markdown(f"**📢 رسالة العرض التسويقية:** *{offer.get('message', 'لا توجد')}*")
                
            # أزرار تحكم سريعة
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2, b3 = st.columns(3)
            with b1:
                t_status = "inactive" if status == "active" else "active"
                lbl = "⏸️ إيقاف تشغيل العرض" if status == "active" else "▶️ إعادة تفعيل العرض"
                if st.button(lbl, key=f"t_st_{offer_id}_{idx}", use_container_width=True):
                    safe_api_request("PUT", f"{SALLA_API_URL}/{offer_id}/status", headers, json={"status": t_status})
                    st.rerun()
            with b2:
                if st.button("🔖 عكس حالة الكوبون", key=f"t_cp_{offer_id}_{idx}", use_container_width=True):
                    safe_api_request("PUT", f"{SALLA_API_URL}/{offer_id}", headers, json={"applied_with_coupon": not offer.get('applied_with_coupon', False)})
                    st.rerun()
            with b3:
                if st.button("🗑️ حذف العرض نهائياً", key=f"t_dl_{offer_id}_{idx}", type="primary", use_container_width=True):
                    safe_api_request("DELETE", f"{SALLA_API_URL}/{offer_id}", headers)
                    st.rerun()

            # نموذج التعديل المتقدم الخاص بكل عرض (الذي تم استرجاعه بالكامل)
            with st.expander("✏️ تعديل تفاصيل هذا العرض بشكل متقدم", expanded=False):
                ed_name = st.text_input("تعديل اسم العرض:", value=offer_name, key=f"ed_n_{offer_id}")
                ed_msg = st.text_input("تعديل رسالة العرض ترويجياً:", value=offer.get('message', ''), key=f"ed_m_{offer_id}")
                ed_start = st.text_input("تعديل تاريخ البدء:", value=offer.get('start_date', ''), key=f"ed_s_{offer_id}")
                ed_end = st.text_input("تعديل تاريخ الانتهاء:", value=offer.get('expiry_date', ''), key=f"ed_e_{offer_id}")
                
                if st.button("💾 حفظ التغييرات الحالية للعرض", key=f"sv_of_{offer_id}", type="primary", use_container_width=True):
                    update_payload = {
                        "name": ed_name, "message": ed_msg, "start_date": ed_start, "expiry_date": ed_end,
                        "status": status, "offer_type": offer.get('offer_type', 'buy_x_get_y'),
                        "applied_with_coupon": offer.get('applied_with_coupon', False),
                        "buy": offer.get('buy', {"type": "product", "quantity": 1}),
                        "get": offer.get('get', {"type": "product", "quantity": 1, "discount_type": "free-product"})
                    }
                    if safe_api_request("PUT", f"{SALLA_API_URL}/{offer_id}", headers, json=update_payload):
                        st.success("✅ تم حفظ وتحديث العرض الفردي بنجاح!")
                        st.rerun()
            
            st.markdown("</div>", unsafe_allow_html=True)
