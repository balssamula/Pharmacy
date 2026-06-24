import streamlit as st
from datetime import datetime
import pandas as pd
from utils import (
    get_headers, safe_api_request, SALLA_API_URL, generate_salla_excel_template,
    process_excel_import, export_offers_to_excel, safe_parse_date, parse_products_cleanly,
    OFFER_TYPES_MAP, CHANNELS_MAP, APPLIED_TO_MAP
)

def render_offers_page():
    st.markdown("<h2 style='color:#0f1c2e;'>📊 لوحة إدارة العروض الخاصة والمنتجات</h2>", unsafe_allow_html=True)
    
    headers = get_headers()
    if not headers: return

    col_dl, col_ex = st.columns([1, 1])
    with col_dl:
        st.download_button(
            label="📥 تنزيل نموذج استيراد العروض الترويجية",
            data=generate_salla_excel_template(),
            file_name="Salla_Offers_Template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
    with st.spinner("جاري مزامنة العروض..."):
        res_all = safe_api_request("GET", SALLA_API_URL, headers)
        raw_offers = res_all.get("data", []) if res_all else []
        
    with col_ex:
        if raw_offers:
            st.download_button(
                label="📥 تصدير العروض الخاصة الحالية",
                data=export_offers_to_excel(raw_offers),
                file_name=f"offers_export_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary"
            )

    uploaded_file = st.file_uploader("📂 تحميل واستيراد ملف عروض جماعي (XLSX):", type=["xlsx"])
    if uploaded_file:
        try:
            df_user = pd.read_excel(uploaded_file)
            st.dataframe(df_user, use_container_width=True)
            if st.button("🚀 تأكيد معالجة ونشر العروض المرفوعة", use_container_width=True, type="primary"):
                res = process_excel_import(df_user)
                for m in res["success"]: st.success(m)
                for m in res["errors"]: st.error(m)
                st.rerun()
        except Exception as e:
            st.error(f"خطأ في قراءة ملف الإكسيل: {str(e)}")

    st.divider()

    # --- حاوية إنشاء عرض جديد متكامل ومحمي بظهور ديناميكي مشروط ---
    with st.expander("➕ إنشاء عرض ترويجي جديد", expanded=False):
        st.markdown("### 📝 تفاصيل العرض الأساسية")
        c1, c2 = st.columns(2)
        with c1:
            new_offer_name = st.text_input("اسم العرض الجديد:")
            new_offer_type_ar = st.selectbox("نوع العرض:", list(OFFER_TYPES_MAP.values()), key="creation_type_box_ar")
            new_applied_to_ar = st.selectbox("يتم تطبيق العرض على:", list(APPLIED_TO_MAP.values()), key="creation_applied_to_box_ar")
            new_with_coupon = st.selectbox("تطبيق العرض مع كوبون التخفيض؟", ["لا", "نعم"], key="new_coupon_creation")
        with c2:
            new_message = st.text_input("نص رسالة العرض:")
            new_channel_ar = st.selectbox("منصة نشر العرض:", list(CHANNELS_MAP.values()), key="new_channel_creation")
            new_offer_status = st.selectbox("حالة العرض:", ["active", "inactive"], format_func=lambda x: "مفعل ةنشط بالمتجر" if x == "active" else "متوقف حالياً", key="new_status_creation")
            new_start_date = st.text_input("توقيت بدء العرض:", value=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            new_expiry_date = st.text_input("توقيت انتهاء العرض:", value="2026-12-31 23:59:59")
            
        st.markdown("#### ⚙️ خيارات العرض")
        cc1, cc2, cc3 = st.columns(3)
        with cc1:
            new_max_discount = st.number_input("الحد الأقصى للخصم (SAR) [0 لتعطيله]:", min_value=0.0, value=0.0)
        with cc2:
            min_apply_option = st.selectbox("الحد الأدنى لتطبيق العرض:", ["الحد الأدنى لمبلغ الشراء", "الحد الأدنى لكمية المنتجات"])
            new_min_purchase = st.number_input("قيمة الحد الأدنى لمبلغ الشراء (SAR):", min_value=0.0, value=0.0) if min_apply_option == "الحد الأدنى لمبلغ الشراء" else 0.0
        with cc3:
            new_min_items = st.number_input("الحد الأدنى لكمية المنتجات المطلوبة (حبة):", min_value=0, value=0) if min_apply_option == "الحد الأدنى لكمية المنتجات" else 0

        selected_type_key = [k for k, v in OFFER_TYPES_MAP.items() if v == new_offer_type_ar][0]
        selected_channel_key = [k for k, v in CHANNELS_MAP.items() if v == new_channel_ar][0]
        selected_applied_key = [k for k, v in APPLIED_TO_MAP.items() if v == new_applied_to_ar][0]

        st.markdown("#### 🛒 شروط ومجموعات الكميات المشمولة")
        # التغيير الشرطي الكامل لحقول الإنشاء بناءً على نوع العرض
        if selected_type_key == "buy_x_get_y":
            col_bx, col_by = st.columns(2)
            with col_bx:
                new_buy_type = st.selectbox("نوع شرط الشراء X:", ["product", "category"], key="nb_t")
                new_buy_qty = st.number_input("الكمية المطلوب شراؤها (X):", min_value=1, value=1, key="nb_q")
                new_buy_products = st.text_input("معرفات (IDs) لمنتجات الشراء (إذا اشترى العميل):", key="nb_p")
            with col_by:
                new_get_type = st.selectbox("نوع العرض Y:", ["product", "category"], key="ng_t")
                new_get_qty = st.number_input("الكمية المجانية (Y):", min_value=1, value=1, key="ng_q")
                new_get_products = st.text_input("معرفات (IDs) لمنتجات العرض (يحصل على):", key="ng_p")
            
            new_discount_type_ar = st.selectbox("نوع التخفيض المطبق على Y:", ["منتج مجاني", "خصم بنسبة"], key="nd_t_ar")
            if new_discount_type_ar == "خصم بنسبة":
                new_discount_amount = st.number_input("نسبة الخصم المئوية المطبقة على Y (%):", min_value=1.0, max_value=100.0, value=10.0, key="nd_a")
                new_discount_type = "percentage"
            else:
                new_discount_amount = 0.0
                new_discount_type = "free-product"
        else:
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                new_discount_amount = st.number_input("قيمة أو نسبة التخفيض:", min_value=0.5, value=10.0, key="nd_a_dir")
                new_buy_products = st.text_input("معرفات الـ IDs للمنتجات الخاضعة للتخفيض (بفاصلة):", key="nb_p_dir")
            with col_p2:
                st.caption("ملاحظة: هذا العرض مالي مباشر وموحد ويطبق على السلة أو الأصناف المحددة.")
            new_buy_type = "product"
            new_buy_qty = 1
            new_get_type = "product"
            new_get_qty = 1
            new_get_products = ""
            new_discount_type = "percentage" if selected_type_key == "percentage" else "fixed_amount"
        
        if st.button("🚀 إنشاء العرض ونشره بالمتجر الآن", type="primary", use_container_width=True, key="save_new_offer_green"):
            try:
                b_ids = [int(i.strip()) for i in new_buy_products.split(",") if i.strip().isdigit()]
                payload = {
                    "name": new_offer_name, "offer_type": selected_type_key, "message": new_message,
                    "applied_channel": selected_channel_key, "applied_to": selected_applied_key,
                    "start_date": new_start_date, "expiry_date": new_expiry_date, "status": new_offer_status,
                    "applied_with_coupon": new_with_coupon == "نعم",
                    "max_discount_amount": float(new_max_discount), "min_purchase_amount": float(new_purchase) if 'new_purchase' in locals() else float(new_min_purchase), "min_items_count": int(new_min_items),
                    "buy": {"type": new_buy_type, "quantity": int(new_buy_qty), "products": b_ids},
                    "get": {"type": new_get_type, "quantity": int(new_get_qty), "discount_type": new_discount_type}
                }
                if selected_type_key == "buy_x_get_y":
                    g_ids = [int(i.strip()) for i in new_get_products.split(",") if i.strip().isdigit()]
                    payload["get"]["products"] = g_ids
                if new_discount_amount > 0:
                    payload["get"]["discount_amount"] = float(new_discount_amount)
                    
                if safe_api_request("POST", SALLA_API_URL, headers, json=payload):
                    st.success("✅ تم إنشاء العرض الترويجي بنجاح!")
                    st.rerun()
            except Exception as e:
                st.error(f"خطأ أثناء إنشاء العرض: {str(e)}")

    st.divider()

    # --- أدوات التصفية والبحث المتقدمة عن العروض ---
    st.markdown("#### 🔍 أدوات التصفية والبحث المتقدمة عن العروض")
    f1, f2, f3 = st.columns(3)
    with f1: search_offer = st.text_input("🔎 ابحث باسم العرض أو بالمعرف الرقمي:")
    with f2: status_filter = st.selectbox("📌 حالة ظهور العرض بالمتجر:", ["الكل", "نشط", "غير نشط"])
    with f3: filter_date_str = st.text_input("📅 ابحث عن تاريخ انتهاء مطابق تماماً وحصراً (YYYY-MM-DD):", placeholder="مثال: 2026-06-24")

    now = datetime.now()

    for idx, offer in enumerate(raw_offers):
        offer_id = offer.get('id', 'N/A')
        offer_name = offer.get('name', 'عرض بدون اسم')
        status = offer.get('status', 'inactive')
        o_type_raw = offer.get('offer_type', '')
        o_channel_raw = offer.get('applied_channel', 'browser_and_application')
        o_applied_raw = offer.get('applied_to', 'product')
        
        start_date = safe_parse_date(offer.get('start_date'))
        exp_date = safe_parse_date(offer.get('expiry_date'))
        
        if search_offer and (search_offer.lower() not in offer_name.lower() and search_offer not in str(offer_id)): continue
        if status_filter == "نشط" and status != "active": continue
        if status_filter == "غير نشط" and status == "active": continue
        
        if filter_date_str.strip():
            try:
                target_date = datetime.strptime(filter_date_str.strip(), "%d-%m-%Y").date()
                if not exp_date or exp_date.date() != target_date: continue
            except ValueError:
                st.warning("⚠️ صيغة تاريخ التصفية المطابق الصحيح هي YYYY-MM-DD")
                st.stop()
        
        badge = "🟢 نشط بالمتجر" if status == "active" else "🔴 متوقف حالياً"
        
        # ضبط شارات التواريخ الاحترافية الثلاثية المطلوبة بدقة كاملة
        if start_date and start_date > now:
            exp_badge = "⏳ لم يبدأ بعد"
        elif exp_date and exp_date < now:
            exp_badge = "⚠️ منتهي الصلاحية"
        else:
            exp_badge = "⏳ ساري الصلاحية"
        
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
                st.markdown(f"⚙️ **نوع العرض:** `{OFFER_TYPES_MAP.get(o_type_raw, o_type_raw)}`")
                st.markdown(f"📺 **قناة العرض الفعالة:** `{CHANNELS_MAP.get(o_channel_raw, o_channel_raw)}`")
                st.markdown(f"🎯 **يتم تطبيق العرض على:** `{APPLIED_TO_MAP.get(o_applied_raw, o_applied_raw)}`")
                st.markdown(f"📅 **توقيت بدء العرض:** `{offer.get('start_date', 'غير محدد')}`")
            with cy:
                st.markdown(f"📅 **توقيت انتهاء العرض:** `{offer.get('expiry_date', 'بدون تاريخ (مستمر)')}`")
                st.markdown(f"🛡️ **الحد الأقصى للخصم:** `{offer.get('max_discount_amount', 0)} SAR` | 💵 **الحد الأدنى للشراء:** `{offer.get('min_purchase_amount', 0)} SAR`")
                st.markdown(f"**🔖 تطبيق العرض مع كوبون التخفيض؟** `{'نعم' if offer.get('applied_with_coupon') else 'لا يطبق'}`")
                st.markdown(f"**📢 نص رسالة العرض:** *{offer.get('message', 'لا توجد رسالة مرفقة')}*")
                
            st.markdown("<hr style='margin: 15px 0; border-top: 1px dashed #e2e8f0;'>", unsafe_allow_html=True)
            
            col_x, col_y = st.columns(2)
            with col_x:
                st.markdown("<b style='color:#0f1c2e;'>🛒 مجموعة الشراء (X) - [إذا اشترى العميل]:</b>", unsafe_allow_html=True)
                st.text(parse_products_cleanly(offer.get('buy', {})))
                st.caption(f"الكمية المطلوبة: {offer.get('buy', {}).get('quantity', 1)} قطعة")
            with col_y:
                st.markdown("<b style='color:#0f1c2e;'>🎁 المنتجات المجانية والخصم (Y) - [يحصل على]:</b>", unsafe_allow_html=True)
                st.text(parse_products_cleanly(offer.get('get', {})))
                st.caption(f"الكمية المجانية/الخصم: {offer.get('get', {}).get('quantity', 1)} قطعة")
                if offer.get('get', {}).get('discount_amount'):
                    st.markdown(f"🔥 **قيمة/نسبة الخصم:** `{offer.get('get', {}).get('discount_amount')}`")

            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2, b3 = st.columns(3)
            with b1:
                t_status = "inactive" if status == "active" else "active"
                lbl = "⏸️ إيقاف العرض" if status == "active" else "▶️ إعادة تفعيل وبث العرض"
                if st.button(lbl, key=f"t_st_{offer_id}_{idx}", use_container_width=True):
                    safe_api_request("PUT", f"{SALLA_API_URL}/{offer_id}/status", headers, json={"status": t_status})
                    st.rerun()
            with b2:
                if st.button("🔖 عكس تطبيق العرض مع الكوبون", key=f"t_cp_{offer_id}_{idx}", use_container_width=True):
                    safe_api_request("PUT", f"{SALLA_API_URL}/{offer_id}", headers, json={"applied_with_coupon": not offer.get('applied_with_coupon', False)})
                    st.rerun()
            with b3:
                if st.button("🗑️ حذف العرض بالكامل", key=f"t_dl_{offer_id}_{idx}", use_container_width=True, type="primary"):
                    safe_api_request("DELETE", f"{SALLA_API_URL}/{offer_id}", headers)
                    st.rerun()

            # --- حاوية تعديل مشروطة متكاملة ومسترجعة بالكامل لمنع الأخطاء البصرية والبرمجية ---
            with st.expander("✏️ تعديل ومراجعة الترويجي", expanded=False):
                st.markdown("##### ✏️ تعديل البيانات والخيارات الأساسية")
                ed_name = st.text_input("تحديث إسم العرض:", value=offer_name, key=f"ed_n_{offer_id}_{idx}")
                ed_msg = st.text_input("تحديث نص رسالة العرض:", value=offer.get('message', ''), key=f"ed_m_{offer_id}_{idx}")
                
                ec1, ec2, ec3 = st.columns(3)
                with ec1:
                    current_type_idx = list(OFFER_TYPES_MAP.keys()).index(o_type_raw) if o_type_raw in OFFER_TYPES_MAP else 0
                    ed_type_ar = st.selectbox("تعديل نوع العرض:", list(OFFER_TYPES_MAP.values()), index=current_type_idx, key=f"ed_t_ar_{offer_id}_{idx}")
                    ed_applied_ar = st.selectbox("تعديل نطاق تطبيق العرض على:", list(APPLIED_TO_MAP.values()), index=list(APPLIED_TO_MAP.keys()).index(o_applied_raw) if o_applied_raw in APPLIED_TO_MAP else 0, key=f"ed_app_ar_{offer_id}_{idx}")
                with ec2:
                    current_chan_idx = list(CHANNELS_MAP.keys()).index(o_channel_raw) if o_channel_raw in CHANNELS_MAP else 0
                    ed_chan_ar = st.selectbox("تعديل منصة نشر العرض:", list(CHANNELS_MAP.values()), index=current_chan_idx, key=f"ed_ch_ar_{offer_id}_{idx}")
                    ed_status = st.selectbox("تعديل حالة العرض:", ["active", "inactive"], index=0 if status == "active" else 1, format_func=lambda x: "مفعل ونشط بالمتجر" if x == "active" else "متوقف حاليا", key=f"ed_status_field_{offer_id}_{idx}")
                with ec3:
                    ed_coupon = st.selectbox("تطبيق العرض مع كوبون التخفيض؟", ["لا", "نعم"], index=1 if offer.get('applied_with_coupon') else 0, key=f"ed_c_{offer_id}_{idx}")

                selected_ed_type_key = [k for k, v in OFFER_TYPES_MAP.items() if v == ed_type_ar][0]
                selected_ed_chan_key = [k for k, v in CHANNELS_MAP.items() if v == ed_chan_ar][0]
                selected_ed_app_key = [k for k, v in APPLIED_TO_MAP.items() if v == ed_applied_ar][0]

                st.markdown("##### ⚙️ تعديل خيارات العرض المتغيرة")
                ecc1, ecc2, ecc3 = st.columns(3)
                with ecc1:
                    ed_max_discount = st.number_input("تعديل الحد الأقصى للخصم (SAR):", min_value=0.0, value=float(offer.get('max_discount_amount', 0.0)), key=f"ed_max_d_{offer_id}_{idx}")
                with ecc2:
                    ed_min_purchase = st.number_input("تعديل الحد الأدنى لمبلغ الشراء (SAR):", min_value=0.0, value=float(offer.get('min_purchase_amount', 0.0)), key=f"ed_min_p_{offer_id}_{idx}")
                with ecc3:
                    ed_min_items = st.number_input("تعديل الحد الأدنى لكمية المنتجات (حبة):", min_value=0, value=int(offer.get('min_items_count', 0)), key=f"ed_min_i_{offer_id}_{idx}")

                st.markdown("##### 🛒 تعديل متغيرات العروض")
                buy_obj = offer.get('buy', {})
                get_obj = offer.get('get', {})
                
                # استخراج نقي وآمن للمعرفات من مصفوفة سلة لعدم إظهار تداخل الأسماء
                buy_p_ids = ",".join([str(p.get('id', p)) if isinstance(p, dict) else str(p) for p in buy_obj.get('products', [])]) if buy_obj else ""
                get_p_ids = ",".join([str(p.get('id', p)) if isinstance(p, dict) else str(p) for p in get_obj.get('products', [])]) if get_obj else ""
                
                # تطبيق الظهور والفرز الديناميكي المشروط في حقول التعديل بالكامل
                if selected_ed_type_key == "buy_x_get_y":
                    eq1, eq2 = st.columns(2)
                    with eq1:
                        ed_buy_type = st.selectbox("تعديل نوع شراء X:", ["product", "category"], index=0 if buy_obj.get('type', 'product') == 'product' else 1, key=f"ed_bt_{offer_id}_{idx}")
                        ed_buy_qty = st.number_input("تعديل كمية الشراء (X):", min_value=1, value=int(buy_obj.get('quantity', 1)), key=f"ed_bq_{offer_id}_{idx}")
                        ed_buy_products = st.text_input("تعديل (IDs) إذا اشترى العميل:", value=buy_p_ids, key=f"ed_bp_ids_{offer_id}_{idx}")
                    with eq2:
                        ed_get_type = st.selectbox("تعديل نوع العرض Y:", ["product", "category"], index=0 if get_obj.get('type', 'product') == 'product' else 1, key=f"ed_gt_{offer_id}_{idx}")
                        ed_get_qty = st.number_input("تعديل كمية العرض (Y):", min_value=1, value=int(get_obj.get('quantity', 1)), key=f"ed_gq_{offer_id}_{idx}")
                        ed_get_products = st.text_input("تعديل (IDs) يحصل العميل على:", value=get_p_ids, key=f"ed_gp_ids_{offer_id}_{idx}")
                    
                    current_disc_type_raw = "خصم بنسبة" if get_obj.get('discount_type', 'free-product') == 'percentage' else "منتج مجاني"
                    ed_discount_type_ar = st.selectbox("تعديل نوع الخصم Y:", ["منتج مجاني", "خصم بنسبة"], index=1 if current_disc_type_raw == "خصم بنسبة" else 0, key=f"ed_dt_ar_{offer_id}_{idx}")
                    
                    if ed_discount_type_ar == "خصم بنسبة":
                        ed_disc_amt = st.number_input("تعديل نسبة الخصم المطبقة على Y (%):", min_value=1.0, max_value=100.0, value=float(get_obj.get('discount_amount', 10.0)), key=f"ed_da_{offer_id}_{idx}")
                        ed_disc_type = "percentage"
                    else:
                        ed_disc_amt = 0.0
                        ed_disc_type = "free-product"
                else:
                    eq1, eq2 = st.columns(2)
                    with eq1:
                        ed_disc_amt = st.number_input("تعديل قيمة أو نسبة الخصم:", min_value=0.5, value=float(get_obj.get('discount_amount', 10.0)), key=f"ed_da_direct_{offer_id}_{idx}")
                        ed_buy_products = st.text_input("تعديل الـ IDs لمنتجات التخفيض:", value=buy_p_ids, key=f"ed_bp_direct_{offer_id}_{idx}")
                    with eq2:
                        st.caption("ملاحظة: هذا النوع من العروض الترويجية يطبق بشكل فوري ومباشر على السلة أو الأصناف المحددة.")
                    ed_buy_type = "product"
                    ed_buy_qty = 1
                    ed_get_type = "product"
                    ed_get_qty = 1
                    ed_get_products = ""
                    ed_disc_type = "percentage" if selected_ed_type_key == "percentage" else "fixed_amount"

                et1, et2 = st.columns(2)
                with et1: ed_start = st.text_input("تحديث تاريخ بدء العرض:", value=offer.get('start_date', ''), key=f"ed_s_dt_{offer_id}_{idx}")
                with et2: ed_end = st.text_input("تحديث تاريخ انتهاء صلاحية العرض:", value=offer.get('expiry_date', ''), key=f"ed_e_dt_{offer_id}_{idx}")
                
                if st.button("💾 اعتماد وحفظ العرض المحدث", key=f"sv_of_{offer_id}_{idx}", type="primary", use_container_width=True):
                    try:
                        b_p_list = [int(i.strip()) for i in ed_buy_products.split(",") if i.strip().isdigit()] if ed_buy_products.strip() else []
                        update_payload = {
                            "name": ed_name, "message": ed_msg, "start_date": ed_start, "expiry_date": ed_end,
                            "status": ed_status, "offer_type": selected_ed_type_key, "applied_channel": selected_ed_chan_key, "applied_to": selected_ed_app_key,
                            "applied_with_coupon": ed_coupon == "نعم", "max_discount_amount": float(ed_max_discount), "min_purchase_amount": float(ed_min_purchase), "min_items_count": int(ed_min_items),
                            "buy": {"type": ed_buy_type, "quantity": int(ed_buy_qty), "products": b_p_list},
                            "get": {"type": ed_get_type, "quantity": int(ed_get_qty), "discount_type": ed_disc_type}
                        }
                        if selected_ed_type_key == "buy_x_get_y":
                            g_p_list = [int(i.strip()) for i in ed_get_products.split(",") if i.strip().isdigit()] if ed_get_products.strip() else []
                            update_payload["get"]["products"] = g_p_list
                        if ed_disc_amt > 0:
                            update_payload["get"]["discount_amount"] = float(ed_disc_amt)
                            
                        if safe_api_request("PUT", f"{SALLA_API_URL}/{offer_id}", headers, json=update_payload):
                            st.success("✅ تم تحديث ونشر بيانات العرض بنجاح!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"خطأ أثناء حفظ التحديثات: {str(e)}")
            
            st.markdown("</div>", unsafe_allow_html=True)
