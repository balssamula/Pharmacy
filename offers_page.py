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

    col_dl, col_ex = st.columns([1, 1])
    with col_dl:
        st.download_button(
            label="📥 تنزيل نموذج الاستيراد الـ Excel",
            data=generate_salla_excel_template(),
            file_name="Salla_Offers_Template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
    with st.spinner("جاري جلب العروض الحالية..."):
        res_all = safe_api_request("GET", SALLA_API_URL, headers)
        raw_offers = res_all.get("data", []) if res_all else []
        
    with col_ex:
        if raw_offers:
            st.download_button(
                label="📥 تصدير قائمة العروض الحالية إلى Excel",
                data=export_offers_to_excel(raw_offers),
                file_name=f"offers_export_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

    uploaded_file = st.file_uploader("📂 تحميل واستيراد ملف عروض جماعي (XLSX):", type=["xlsx"])
    if uploaded_file:
        try:
            df_user = pd.read_excel(uploaded_file)
            st.dataframe(df_user, use_container_width=True)
            if st.button("🚀 تأكيد معالجة ونشر الملف الجماعي", use_container_width=True):
                res = process_excel_import(df_user)
                for m in res["success"]: st.success(m)
                for m in res["errors"]: st.error(m)
                st.rerun()
        except Exception as e:
            st.error(f"خطأ في قراءة الملف: {str(e)}")

    st.divider()

    # --- استعادة الحقول الكاملة لإنشاء عرض ترويجي جديد ---
    with st.expander("➕ إنشاء عرض ترويجي جديد متكامل", expanded=False):
        st.markdown("### 📝 تفاصيل العرض الجديد الأساسية")
        c1, c2 = st.columns(2)
        with c1:
            new_offer_name = st.text_input("اسم العرض:", placeholder="أدخل اسم العرض الترويجي")
            new_offer_type = st.selectbox("نوع وهيكل العرض:", ["buy_x_get_y", "percentage", "fixed_amount", "discounts_table", "tiered_offer", "cart_offer", "special_price"])
            new_applied_to = st.selectbox("تطبيق نطاق العرض على:", ["product", "category", "order", "paymentMethod"])
            new_with_coupon = st.selectbox("هل يتطلب استخدام كوبون؟", ["لا", "نعم"])
        with c2:
            new_message = st.text_input("الرسالة التسويقية للسلة:", placeholder="أدخل رسالة ترويجية تظهر للعميل")
            new_offer_status = st.selectbox("حالة تشغيل العرض الفورية:", ["active", "inactive"], format_func=lambda x: "مفعل فوراً" if x == "active" else "مسودة غير نشط")
            new_start_date = st.text_input("توقيت بدء العرض:", value=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            new_expiry_date = st.text_input("توقيت انتهاء العرض:", value="2026-12-31 23:59:59")
            
        st.markdown("#### 🛒 شروط ومجموعات الكميات المشمولة بالمنح")
        col_b1, col_b2, col_b3 = st.columns(3)
        with col_b1:
            new_buy_type = st.selectbox("نوع شرط الشراء:", ["product", "category"])
            new_buy_qty = st.number_input("الكمية المطلوب شراؤها (X):", min_value=1, value=1)
        with col_b2:
            new_get_type = st.selectbox("نوع مادة المنح الهدية:", ["product", "category"])
            new_get_qty = st.number_input("كمية المواد الممنوحة (Y):", min_value=1, value=1)
        with col_b3:
            new_discount_type = st.selectbox("نوع تخفيض Y:", ["free-product", "percentage"])
            new_discount_amount = st.number_input("قيمة الخصم المالي المطبق:", min_value=0.0, value=0.0)
            
        new_buy_products = st.text_input("قائمة الـ IDs لمنتجات الشراء (مفصولة بفاصلة):", placeholder="مثال: 1298176905, 1444615766")
        new_get_products = st.text_input("قائمة الـ IDs لمنتجات الهدية (مفصولة بفاصلة):", placeholder="مثال: 1298176905, 1444615766")
        
        if st.button("🚀 نشر العرض الترويجي الآن للمتجر", type="primary", use_container_width=True, key="create_offer_btn"):
            try:
                b_ids = [int(i.strip()) for i in new_buy_products.split(",") if i.strip().isdigit()]
                g_ids = [int(i.strip()) for i in new_get_products.split(",") if i.strip().isdigit()]
                
                payload = {
                    "name": new_offer_name, "offer_type": new_offer_type, "message": new_message,
                    "applied_channel": "browser_and_application", "applied_to": new_applied_to,
                    "start_date": new_start_date, "expiry_date": new_expiry_date, "status": new_offer_status,
                    "applied_with_coupon": new_with_coupon == "نعم",
                    "buy": {"type": new_buy_type, "quantity": int(new_buy_qty)},
                    "get": {"type": new_get_type, "quantity": int(new_get_qty), "discount_type": new_discount_type}
                }
                if b_ids: payload["buy"]["products"] = b_ids
                if g_ids: payload["get"]["products"] = g_ids
                if new_discount_amount > 0 and new_discount_type == "percentage":
                    payload["get"]["discount_amount"] = float(new_discount_amount)
                    
                if safe_api_request("POST", SALLA_API_URL, headers, json=payload):
                    st.success("✅ تم إنشاء العرض الترويجي الجديد بنجاح!")
                    st.rerun()
            except Exception as e:
                st.error(f"فشل إنشاء العرض: {str(e)}")

    st.divider()

    # --- أدوات التصفية وتعديل فلتر تاريخ الانتهاء ليطابق التاريخ المدخل بدقة ---
    st.markdown("#### 🔍 أدوات التصفية والبحث عن العروض")
    f1, f2, f3 = st.columns(3)
    with f1: search_offer = st.text_input("🔎 ابحث باسم العرض أو بالمعرف الرقمي:")
    with f2: status_filter = st.selectbox("📌 حالة نشاط وظهور العرض:", ["الكل", "نشط فقط", "غير inactive فقط"])
    with f3: filter_date_str = st.text_input("📅 البحث عن تاريخ انتهاء مطابق تماماً (YYYY-MM-DD):", placeholder="مثال: 2026-06-24")

    now = datetime.now()

    for idx, offer in enumerate(raw_offers):
        offer_id = offer.get('id', 'N/A')
        offer_name = offer.get('name', 'عرض بدون اسم')
        status = offer.get('status', 'inactive')
        exp_date = safe_parse_date(offer.get('expiry_date'))
        
        if search_offer and (search_offer.lower() not in offer_name.lower() and search_offer not in str(offer_id)): continue
        if status_filter == "نشط فقط" and status != "active": continue
        if status_filter == "غير inactive فقط" and status == "active": continue
        
        # تصفية مطابقة لليوم المدخل تماماً (وليس قبله أو بعده)
        if filter_date_str.strip():
            try:
                target_date = datetime.strptime(filter_date_str.strip(), "%Y-%m-%d").date()
                if not exp_date or exp_date.date() != target_date:
                    continue
            except ValueError:
                st.warning("⚠️ يرجى كتابة صيغة تاريخ البحث بشكل سليم YYYY-MM-DD")
                st.stop()
        
        is_expired = exp_date and exp_date < now
        badge = "🟢 نشط بالمتجر" if status == "active" else "🔴 متوقف حالياً"
        exp_badge = "⚠️ منتهي الصلاحية" if is_expired else "⏳ ساري الصلاحية"
        
        st.markdown(f"""
            <div style="background: linear-gradient(135deg, #0f1c2e 0%, #1a365d 100%); 
                        padding: 14px 20px; border-radius: 12px 12px 0px 0px; 
                        margin-top: 25px; display: flex; justify-content: space-between; align-items: center; 
                        flex-wrap: wrap; gap: 10px; border-bottom: 3px solid #00b4d8;">
                <span style="color: #ffffff; font-weight: bold; font-size: 16px;">🎯 {offer_name} (ID: {offer_id})</span>
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                    <span style="background: rgba(255,255,255,0.2); color: #fff; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;">{badge}</span>
                    <span style="background: rgba(255,193,7,0.25); color: #ffca28; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;">{exp_badge}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        with st.container():
            st.markdown("""
                <div style="background-color: #ffffff; padding: 20px; border-radius: 0px 0px 12px 12px; 
                            border: 1px solid #e8edf2; border-top: none; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 25px;">
            """, unsafe_allow_html=True)
            
            cx, cy = st.columns(2)
            with cx:
                st.markdown(f"**📅 توقيت بدء النشر المعتمد:** `{offer.get('start_date', 'غير محدد')}`")
                st.markdown(f"**📅 توقيت انتهاء الصلاحية:** `{offer.get('expiry_date', 'بدون تاريخ (مستمر)')}`")
            with cy:
                st.markdown(f"**🔖 متوافق ومربوط مع كوبونات؟** `{'نعم بالتأكيد' if offer.get('applied_with_coupon') else 'لا (تلقائي المفعول)'}`")
                st.markdown(f"**📢 نص الرسالة الترويجية للزبائن:** *{offer.get('message', 'لا توجد رسالة مرفقة')}*")
                
            st.markdown("<hr style='margin: 15px 0; border-top: 1px dashed #e2e8f0;'>", unsafe_allow_html=True)
            
            # عرض تفاصيل محتويات العروض الحالية
            col_x, col_y = st.columns(2)
            with col_x:
                st.markdown("<b style='color:#0f1c2e;'>🛒 مجموعة الشراء (X):</b>", unsafe_allow_html=True)
                st.text(parse_products_cleanly(offer.get('buy', {})))
                st.caption(f"الكمية المطلوبة: {offer.get('buy', {}).get('quantity', 1)} قطعة")
            with col_y:
                st.markdown("<b style='color:#0f1c2e;'>🎁 مجموعة المنح والهدية (Y):</b>", unsafe_allow_html=True)
                st.text(parse_products_cleanly(offer.get('get', {})))
                st.caption(f"كمية المنح/الخصم: {offer.get('get', {}).get('quantity', 1)} قطعة")

            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2, b3 = st.columns(3)
            with b1:
                t_status = "inactive" if status == "active" else "active"
                lbl = "⏸️ إيقاف مفعول العرض" if status == "active" else "▶️ إعادة تفعيل وبث العرض"
                if st.button(lbl, key=f"t_st_{offer_id}_{idx}", use_container_width=True):
                    safe_api_request("PUT", f"{SALLA_API_URL}/{offer_id}/status", headers, json={"status": t_status})
                    st.rerun()
            with b2:
                if st.button("🔖 عكس التوافق مع الكوبون", key=f"t_cp_{offer_id}_{idx}", use_container_width=True):
                    safe_api_request("PUT", f"{SALLA_API_URL}/{offer_id}", headers, json={"applied_with_coupon": not offer.get('applied_with_coupon', False)})
                    st.rerun()
            with b3:
                if st.button("🗑️ حذف هذا العرض بالكامل", key=f"t_dl_{offer_id}_{idx}", use_container_width=True):
                    safe_api_request("DELETE", f"{SALLA_API_URL}/{offer_id}", headers)
                    st.rerun()

            # --- الحقول المكتملة والشاملة لتعديل العرض الترويجي الحالي بالكامل ---
            with st.expander("✏️ تعديل ومراجعة كافة حقول هذا العرض الترويجي", expanded=False):
                st.markdown("##### ✏️ تعديل البيانات الأساسية والشروط")
                ed_name = st.text_input("تحديث مسمى العرض الحصري:", value=offer_name, key=f"ed_n_{offer_id}_{idx}")
                ed_msg = st.text_input("تحديث الرسالة المعروضة في السلة للزبائن:", value=offer.get('message', ''), key=f"ed_m_{offer_id}_{idx}")
                
                ec1, ec2 = st.columns(2)
                with ec1:
                    ed_type = st.selectbox("تعديل هيكل ونوع العرض:", ["buy_x_get_y", "percentage", "fixed_amount"], index=["buy_x_get_y", "percentage", "fixed_amount"].index(offer.get('offer_type', 'buy_x_get_y')) if offer.get('offer_type', 'buy_x_get_y') in ["buy_x_get_y", "percentage", "fixed_amount"] else 0, key=f"ed_t_{offer_id}_{idx}")
                    ed_applied_to = st.selectbox("تعديل نطاق التطبيق على:", ["product", "category", "order"], index=["product", "category", "order"].index(offer.get('applied_to', 'product')) if offer.get('applied_to', 'product') in ["product", "category", "order"] else 0, key=f"ed_a_{offer_id}_{idx}")
                with ec2:
                    ed_coupon = st.selectbox("تعديل اشتراط الكوبون؟", ["لا", "نعم"], index=1 if offer.get('applied_with_coupon') else 0, key=f"ed_c_{offer_id}_{idx}")
                    ed_status = st.selectbox("تعديل حالة بث العرض:", ["active", "inactive"], index=0 if status == "active" else 1, key=f"ed_st_sel_{offer_id}_{idx}")

                st.markdown("##### 🛒 تعديل كميات ومنتجات العرض التكتيكي")
                buy_obj = offer.get('buy', {})
                get_obj = offer.get('get', {})
                
                eq1, eq2, eq3 = st.columns(3)
                with eq1:
                    ed_buy_type = st.selectbox("تعديل نوع شراء X:", ["product", "category"], index=0 if buy_obj.get('type') == 'product' else 1, key=f"ed_bt_{offer_id}_{idx}")
                    ed_buy_qty = st.number_input("تعديل كمية الشراء (X):", min_value=1, value=int(buy_obj.get('quantity', 1)), key=f"ed_bq_{offer_id}_{idx}")
                with eq2:
                    ed_get_type = st.selectbox("تعديل نوع هدية Y:", ["product", "category"], index=0 if get_obj.get('type') == 'product' else 1, key=f"ed_gt_{offer_id}_{idx}")
                    ed_get_qty = st.number_input("تعديل كمية الهدية (Y):", min_value=1, value=int(get_obj.get('quantity', 1)), key=f"ed_gq_{offer_id}_{idx}")
                with eq3:
                    ed_disc_type = st.selectbox("تعديل نوع تخفيض Y:", ["free-product", "percentage"], index=1 if get_obj.get('discount_type') == 'percentage' else 0, key=f"ed_dt_{offer_id}_{idx}")
                    ed_disc_amt = st.number_input("تعديل قيمة الخصم المالي المطبق على Y:", min_value=0.0, value=float(get_obj.get('discount_amount', 0.0)), key=f"ed_da_{offer_id}_{idx}")

                buy_p_ids = ",".join([str(p.get('id', p)) if isinstance(p, dict) else str(p) for p in buy_obj.get('products', [])])
                get_p_ids = ",".join([str(p.get('id', p)) if isinstance(p, dict) else str(p) for p in get_obj.get('products', [])])
                
                ed_buy_products = st.text_input("تعديل مصفوفة الـ IDs لمنتجات الشراء المشمولة:", value=buy_p_ids, key=f"ed_bp_ids_{offer_id}_{idx}")
                ed_get_products = st.text_input("تعديل مصفوفة الـ IDs لمنتجات الهدية المشمولة:", value=get_p_ids, key=f"ed_gp_ids_{offer_id}_{idx}")
                
                et1, et2 = st.columns(2)
                with et1: ed_start = st.text_input("تحديث تاريخ بدء العرض:", value=offer.get('start_date', ''), key=f"ed_s_dt_{offer_id}_{idx}")
                with et2: ed_end = st.text_input("تحديث تاريخ انتهاء الصلاحية:", value=offer.get('expiry_date', ''), key=f"ed_e_dt_{offer_id}_{idx}")
                
                if st.button("💾 اعتماد وحفظ تعديلات هذا العرض الفردي", key=f"sv_of_{offer_id}_{idx}", type="primary", use_container_width=True):
                    try:
                        b_p_list = [int(i.strip()) for i in ed_buy_products.split(",") if i.strip().isdigit()]
                        g_p_list = [int(i.strip()) for i in ed_get_products.split(",") if i.strip().isdigit()]
                        
                        update_payload = {
                            "name": ed_name, "message": ed_msg, "start_date": ed_start, "expiry_date": ed_end,
                            "status": ed_status, "offer_type": ed_type, "applied_with_coupon": ed_coupon == "نعم",
                            "buy": {"type": ed_buy_type, "quantity": int(ed_buy_qty), "products": b_p_list},
                            "get": {"type": ed_get_type, "quantity": int(ed_get_qty), "discount_type": ed_disc_type, "products": g_p_list}
                        }
                        if ed_disc_amt > 0 and ed_disc_type == "percentage":
                            update_payload["get"]["discount_amount"] = float(ed_disc_amt)
                            
                        if safe_api_request("PUT", f"{SALLA_API_URL}/{offer_id}", headers, json=update_payload):
                            st.success("✅ تم تحديث بيانات العرض بنجاح تام!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"خطأ أثناء حفظ التحديثات: {str(e)}")
            
            st.markdown("</div>", unsafe_allow_html=True)
