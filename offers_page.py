import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
from utils import (
    get_headers, safe_api_request, SALLA_API_URL, generate_salla_excel_template,
    process_excel_import, export_offers_to_excel, safe_parse_date, parse_products_cleanly,
    OFFER_TYPES_MAP, CHANNELS_MAP, APPLIED_TO_MAP, safe_float
)

def render_offers_page():
    st.markdown("<h2 style='color:#0f1c2e;'>📊 لوحة إدارة العروض الخاصة والمنتجات الحالية</h2>", unsafe_allow_html=True)
    
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
        
    with st.spinner("جاري جلب العروض الترويجية الحالية من سلة..."):
        res_all = safe_api_request("GET", SALLA_API_URL, headers)
        raw_offers = res_all.get("data", []) if res_all else []
        
    with col_ex:
        if raw_offers:
            st.download_button(
                label="📥 تصدير قائمة العروض الحالية",
                data=export_offers_to_excel(raw_offers),
                file_name=f"Offers_Export_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary"
            )

    uploaded_file = st.file_uploader("📂 تحميل واستيراد ملف العروض الترويجية (XLSX):", type=["xlsx"])
    if uploaded_file:
        try:
            df_user = pd.read_excel(uploaded_file)
            st.dataframe(df_user, use_container_width=True)
            if st.button("🚀 تأكيد معالجة ونشر ملف العروض المرفوعة", use_container_width=True):
                res = process_excel_import(df_user)
                for m in res["success"]: st.success(m)
                for m in res["errors"]: st.error(m)
                st.rerun()
        except Exception as e:
            st.error(f"خطأ في قراءة ملف الإكسيل: {str(e)}")

    st.divider()

    # ==========================================
    # ✅ أزرار الإجراءات الجماعية
    # ==========================================
    st.markdown("### ⚡ إجراءات جماعية سريعة على العروض")
    
    col_bulk1, col_bulk2, col_bulk3, col_bulk4 = st.columns(4)
    
    with col_bulk1:
        if st.button("⏹️ إيقاف جميع العروض المفعلة", use_container_width=True, type="primary"):
            active_offers = [o for o in raw_offers if o.get('status') == 'active']
            if not active_offers:
                st.warning("⚠️ لا توجد عروض مفعلة حالياً لإيقافها")
            else:
                with st.spinner(f"🔄 جاري إيقاف {len(active_offers)} عرض مفعل..."):
                    success_count = 0
                    for offer in active_offers:
                        offer_id = offer.get('id')
                        if offer_id:
                            res = safe_api_request(
                                "PUT", 
                                f"{SALLA_API_URL}/{offer_id}/status", 
                                headers, 
                                json={"status": "inactive"}
                            )
                            if res: success_count += 1
                    st.success(f"✅ تم إيقاف {success_count} عرض بنجاح من أصل {len(active_offers)}")
                    if success_count > 0: st.rerun()
    
    with col_bulk2:
        with st.popover("📅 تمديد العروض المنتهية"):
            st.markdown("تمديد العروض التي تنتهي في تاريخ محدد")
            st.markdown("**📅 تاريخ انتهاء العرض الحالي:**")
            col_date1, col_time1 = st.columns(2)
            with col_date1:
                target_date = st.date_input("اختر التاريخ:", value=datetime.now().date(), key="bulk_extend_target_date")
            with col_time1:
                target_time = st.time_input("اختر الوقت:", value=datetime.now().time().replace(minute=59, second=59), key="bulk_extend_target_time", step=60)
            target_datetime = datetime.combine(target_date, target_time)
            
            st.markdown("**📅 التاريخ الجديد للتمديد:**")
            col_date2, col_time2 = st.columns(2)
            with col_date2:
                new_date = st.date_input("اختر التاريخ الجديد:", value=datetime.now().date() + timedelta(days=30), key="bulk_extend_new_date")
            with col_time2:
                new_time = st.time_input("اختر الوقت الجديد:", value=datetime.now().time().replace(minute=59, second=59), key="bulk_extend_new_time", step=60)
            new_datetime = datetime.combine(new_date, new_time)
            
            target_str = target_datetime.strftime('%Y-%m-%d')
            matching_offers = [o for o in raw_offers if o.get('expiry_date', '') and o.get('expiry_date', '').startswith(target_str)]
            
            st.info(f"📊 عدد العروض التي تنتهي في {target_str}: **{len(matching_offers)}** عرض")
            st.info(f"📅 سيتم تمديدها إلى **{new_datetime.strftime('%Y-%m-%d %H:%M:%S')}**")
            
            if st.button("🔄 تطبيق التمديد على جميع العروض", use_container_width=True, type="primary"):
                if not matching_offers:
                    st.warning(f"⚠️ لا توجد عروض تنتهي في تاريخ {target_str}")
                else:
                    new_datetime_str = new_datetime.strftime('%Y-%m-%d %H:%M:%S')
                    with st.spinner(f"🔄 جاري تمديد {len(matching_offers)} عرض..."):
                        success_count = 0
                        for offer in matching_offers:
                            offer_id = offer.get('id')
                            if offer_id:
                                current = safe_api_request("GET", f"{SALLA_API_URL}/{offer_id}", headers)
                                if current and current.get('data'):
                                    offer_data = current['data']
                                    offer_data['expiry_date'] = new_datetime_str
                                    
                                    if 'buy' in offer_data and isinstance(offer_data['buy'], dict):
                                        if 'products' in offer_data['buy'] and isinstance(offer_data['buy']['products'], list):
                                            offer_data['buy']['products'] = [p.get('id') if isinstance(p, dict) else p for p in offer_data['buy']['products']]
                                        if 'categories' in offer_data['buy'] and isinstance(offer_data['buy']['categories'], list):
                                            offer_data['buy']['categories'] = [c.get('id') if isinstance(c, dict) else c for c in offer_data['buy']['categories']]
                                            
                                    if 'get' in offer_data and isinstance(offer_data['get'], dict):
                                        if 'products' in offer_data['get'] and isinstance(offer_data['get']['products'], list):
                                            offer_data['get']['products'] = [p.get('id') if isinstance(p, dict) else p for p in offer_data['get']['products']]
                                        if 'categories' in offer_data['get'] and isinstance(offer_data['get']['categories'], list):
                                            offer_data['get']['categories'] = [c.get('id') if isinstance(c, dict) else c for c in offer_data['get']['categories']]
                                            
                                    if 'customer_groups' in offer_data and isinstance(offer_data['customer_groups'], list):
                                        offer_data['customer_groups'] = [g.get('id') if isinstance(g, dict) else g for g in offer_data['customer_groups']]
                                    
                                    for key in ['id', 'created_at', 'updated_at', 'show_price_after_discount', 'show_discounts_table_message']:
                                        offer_data.pop(key, None)
                                    
                                    res = safe_api_request("PUT", f"{SALLA_API_URL}/{offer_id}", headers, json=offer_data)
                                    if res: success_count += 1
                        st.success(f"✅ تم تمديد {success_count} عرض بنجاح من أصل {len(matching_offers)}")
                        if success_count > 0: st.rerun()
    
    with col_bulk3:
        # الاستفادة من العروض المفلترة المخزنة في الجلسة من التحديث السابق لزر التصدير العلوي
        if "filtered_offers" in st.session_state and st.session_state["filtered_offers"] and len(st.session_state["filtered_offers"]) < len(raw_offers):
            st.download_button(
                label="📥 تصدير العروض المفلترة",
                data=export_offers_to_excel(st.session_state["filtered_offers"]),
                file_name=f"filtered_offers_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="bulk_export_filtered_top_active",
                use_container_width=True,
                type="secondary"
            )
        else:
            if st.button("📥 تصدير العروض المفلترة", use_container_width=True, type="secondary", key="bulk_export_filtered_top_disabled"):
                st.info("💡 يرجى كتابة أو اختيار فلاتر البحث في الأسفل أولاً، ليقوم الزر بحصرها وتصديرها فوراً!")

    with col_bulk4:
        if st.button("🚀 تفعيل تطبيق العرض مع كوبون التخفيض على جميع العروض", type="primary", use_container_width=True):
            headers = get_headers()
            with st.spinner("🔄 جاري قراءة وتحديث كافة العروض النشطة..."):
                offers_res = safe_api_request("GET", "https://api.salla.dev/admin/v2/specialoffers", headers)
                active_offers = [o for o in offers_res.get("data", []) if o.get("status") == "active"]
            
                success_count = 0
                for offer in active_offers:
                    offer_id = offer.get("id")
                
                    def get_id(field_name):
                        val = offer.get(field_name)
                        return val.get("id") if isinstance(val, dict) else val

                    payload = {
                        "name": offer.get("name", "عرض خاص"),
                        "status": get_id("status") or "active",
                        "offer_type": get_id("offer_type") or "buy_x_get_y",
                        "applied_channel": get_id("applied_channel") or "browser",
                        "applied_to": get_id("applied_to") or "all",
                        "applied_with_coupon": True 
                    }
                
                    if offer.get("start_date"): payload["start_date"] = offer["start_date"]
                    if offer.get("end_date"): payload["end_date"] = offer["end_date"]
                
                    for key in ["max_discount_amount", "min_purchase_amount", "min_items_count"]:
                        if offer.get(key) is not None:
                            payload[key] = float(offer[key]) if "amount" in key else int(offer[key])
                        
                    if offer.get("customer_groups"):
                        payload["customer_groups"] = [g.get("id", g) if isinstance(g, dict) else g for g in offer["customer_groups"]]
                    
                    # ✅ الحل الجذري لخطأ 422: ضمان وجود products كـ مصفوفة دائماً
                    if offer.get("buy"):
                        buy = offer["buy"]
                        b_type = buy.get("type", {}).get("id") if isinstance(buy.get("type"), dict) else buy.get("type")
                        payload["buy"] = {
                            "type": b_type or "quantity", 
                            "quantity": int(buy.get("quantity", 1)),
                            "products": [p.get("id", p) if isinstance(p, dict) else p for p in buy.get("products", [])]
                        }
                        
                    if offer.get("get"):
                        get_obj = offer["get"]
                        g_type = get_obj.get("type", {}).get("id") if isinstance(get_obj.get("type"), dict) else get_obj.get("type")
                        g_disc_type = get_obj.get("discount_type", {}).get("id") if isinstance(get_obj.get("discount_type"), dict) else get_obj.get("discount_type")
                        payload["get"] = {
                            "type": g_type or "quantity",
                            "quantity": int(get_obj.get("quantity", 1)),
                            "discount_type": g_disc_type or "percentage",
                            "products": [p.get("id", p) if isinstance(p, dict) else p for p in get_obj.get("products", [])]
                        }
                        if get_obj.get("discount_amount") is not None: 
                            payload["get"]["discount_amount"] = float(get_obj["discount_amount"])

                    res = safe_api_request("PUT", f"https://api.salla.dev/admin/v2/specialoffers/{offer_id}", headers, json=payload)
                    if res:
                        success_count += 1
                    
                st.success(f"✅ تم تفعيل دمج الكوبونات لـ {success_count} عرض بنجاح!")
                
    # --- حاوية إنشاء عرض جديد ---
    with st.expander("➕ إنشاء عرض ترويجي جديد", expanded=False):
        st.markdown("### 📝 تفاصيل العرض الأساسية")
        c1, c2 = st.columns(2)
        with c1:
            new_offer_name = st.text_input("اسم العرض الجديد:", key="cre_offer_name_input")
            new_offer_type_ar = st.selectbox("نوع العرض:", list(OFFER_TYPES_MAP.values()), key="creation_type_box_ar")
            new_applied_to_ar = st.selectbox("يتم تطبيق العرض على:", list(APPLIED_TO_MAP.values()), key="creation_applied_to_ar")
            new_with_coupon = st.selectbox("تطبيق العرض مع كوبون التخفيض؟", ["لا", "نعم"], key="new_coupon_creation")
        with c2:
            new_message = st.text_input("نص رسالة العرض:", key="cre_offer_msg_input")
            new_channel_ar = st.selectbox("منصة نشر العرض:", list(CHANNELS_MAP.values()), key="new_channel_creation")
            
            st.markdown("**📅 تاريخ بدء العرض:**")
            col_start_date, col_start_time = st.columns(2)
            with col_start_date:
                new_start_date_val = st.date_input("اختر التاريخ:", value=datetime.now().date(), key="new_start_date")
            with col_start_time:
                new_start_time_val = st.time_input("اختر الوقت:", value=datetime.now().time().replace(minute=0, second=0), key="new_start_time", step=60)
            new_start_date = datetime.combine(new_start_date_val, new_start_time_val).strftime('%Y-%m-%d %H:%M:%S')
            
            st.markdown("**📅 تاريخ انتهاء العرض:**")
            col_end_date, col_end_time = st.columns(2)
            with col_end_date:
                new_expiry_date_val = st.date_input("اختر التاريخ:", value=datetime.now().date() + timedelta(days=30), key="new_expiry_date")
            with col_end_time:
                new_expiry_time_val = st.time_input("اختر الوقت:", value=datetime.now().time().replace(hour=23, minute=59, second=59), key="new_expiry_time", step=60)
            new_expiry_date = datetime.combine(new_expiry_date_val, new_expiry_time_val).strftime('%Y-%m-%d %H:%M:%S')
            
        new_cust_groups_input = st.text_input("معرفات مجموعة العملاء المشمولة (مفصولة بفاصلة ,) - اتركها فارغة للكل:", placeholder="مثال: 10294, 33451", key="new_cust_groups_creation")

        selected_type_key = [k for k, v in OFFER_TYPES_MAP.items() if v == new_offer_type_ar][0]
        selected_channel_key = [k for k, v in CHANNELS_MAP.items() if v == new_channel_ar][0]
        selected_applied_to_key = [k for k, v in APPLIED_TO_MAP.items() if v == new_applied_to_ar][0]

        st.markdown("⚙️ تفاصيل العرض المتقدمة")
        ca1, ca2, ca3 = st.columns(3)
        with ca1:
            new_max_discount = st.number_input("الحد الأقصى للخصم (SAR) - 0 لعدم التقييد:", min_value=0.0, value=0.0, key="cre_max_d")
        with ca2:
            new_min_purchase = st.number_input("الحد الأدنى لمبلغ الشراء (SAR) - 0 لعدم التقييد:", min_value=0.0, value=0.0, key="cre_min_p")
        with ca3:
            new_min_items = st.number_input("الحد الأدنى لكمية المنتجات:", min_value=0, value=0, step=1, key="cre_min_i")
            
        st.markdown("🛒 شروط وخيارات العرض")
        
        if selected_type_key == "buy_x_get_y":
            col_bx, col_by = st.columns(2)
            with col_bx:
                new_buy_type = st.selectbox("نوع شرط الشراء X:", ["product", "category"], key="cre_buy_type_select")
                new_buy_qty = st.number_input("[إذا اشترى] - كمية الشراء (X):", min_value=1, value=1, key="cre_buy_qty_input")
                new_buy_products = st.text_input("(IDs) - منتجات الشراء (إذا اشترى العميل):", key="cre_buy_products_input")
            with col_by:
                new_get_type = st.selectbox("نوع صنف الهدية الممنوحة Y:", ["product", "category"], key="cre_get_type_select")
                new_get_qty = st.number_input("[يحصل على] - كمية/نسبة خصم القطع الممنوحة (Y):", min_value=1, value=1, key="cre_get_qty_input")
                new_get_products = st.text_input("(IDs) - منتجات العرض الممنوح (يحصل على):", key="cre_get_products_input")
            
            new_discount_type_ar = st.selectbox("نوع التخفيض المطبق على Y:", ["منتج مجاني", "خصم بنسبة"], key="cre_dtype_ar")
            if new_discount_type_ar == "خصم بنسبة":
                new_discount_amount = st.number_input("نسبة الخصم المطبقة على Y (%):", min_value=1.0, max_value=100.0, value=50.0, key="cre_discount_amt_buyx")
                new_discount_type = "percentage"
            else:
                new_discount_amount = 0.0
                new_discount_type = "free-product"
        else:
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                new_discount_amount = st.number_input("قيمة أو نسبة التخفيض:", min_value=0.0, value=10.0, key="cre_discount_amt_direct")
                new_buy_products = st.text_input("(IDs) منتجات التخفيض (مفصولة بفاصلة ,):", key="cre_buy_products_direct")
            with col_p2:
                st.caption("عروض النسبة والمبالغ المقطوعة والسعر الثابت تطبق بشكل فوري ومباشر على أصناف المستودع المحددة دون اشتراط هدايا معها.")
            new_buy_type = "product"
            new_buy_qty = 1
            new_get_type = "product"
            new_get_qty = 1
            new_get_products = ""
            new_discount_type = "percentage" if selected_type_key == "percentage" else "fixed_amount"
        
        if st.button("🚀 إنشاء العرض ونشره بالمتجر الآن", type="primary", use_container_width=True, key="save_new_offer_green"):
            try:
                b_ids = [int(i.strip()) for i in new_buy_products.split(",") if i.strip().isdigit()]
                cg_ids = [int(g.strip()) for g in new_cust_groups_input.split(",") if g.strip().isdigit()] if new_cust_groups_input.strip() else []
                
                payload = {
                    "name": new_offer_name, "offer_type": selected_type_key, "message": new_message,
                    "applied_channel": selected_channel_key, "applied_to": selected_applied_to_key,
                    "start_date": new_start_date, "expiry_date": new_expiry_date, "status": "active",
                    "applied_with_coupon": new_with_coupon == "نعم",
                    "customer_groups": cg_ids,
                    "max_discount_amount": float(new_max_discount),
                    "min_purchase_amount": float(new_min_purchase),
                    "min_items_count": int(new_min_items),
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

    # --- أدوات التصفية والبحث ---
    st.markdown(" 🔍 أدوات التصفية والبحث المتقدمة عن العروض")
    f1, f2, f3 = st.columns(3)
    with f1: search_offer = st.text_input("🔎 ابحث باسم العرض أو بالمعرف الرقمي:", key="filter_search_input")
    with f2: status_filter = st.selectbox("📌 حالة نشاط وظهور العرض بالمتجر:", ["الكل", "نشط", "غير نشط"], key="filter_status_select")
    with f3: filter_date = st.date_input("📅 ابحث عن تاريخ انتهاء العرض:", value=None, key="filter_date_input")

    now = datetime.now()
    
    filtered_offers = []
    for offer in raw_offers:
        offer_id = offer.get('id', 'N/A')
        offer_name = offer.get('name', 'عرض بدون اسم')
        status = offer.get('status', 'inactive')
        
        start_date = safe_parse_date(offer.get('start_date'))
        exp_date = safe_parse_date(offer.get('expiry_date'))
        
        if search_offer and (search_offer.lower() not in offer_name.lower() and search_offer not in str(offer_id)): continue
        if status_filter == "نشط" and status != "active": continue
        if status_filter == "غير نشط" and status == "active": continue
        if filter_date and (not exp_date or exp_date.date() != filter_date): continue
        
        filtered_offers.append(offer)
    
    st.session_state["filtered_offers"] = filtered_offers
    
    if filtered_offers and len(filtered_offers) < len(raw_offers):
        # تحويله إلى زر تحميل مباشر دون وضعه داخل st.button لمنع اختفائه أثناء الـ Rerun
        st.download_button(
            label="📥 اضغط هنا لتحميل ملف العروض المفلترة الحالية مباشرة",
            data=export_offers_to_excel(filtered_offers),
            file_name=f"filtered_offers_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="direct_download_filtered_offers_bottom_final",
            type="primary",
            use_container_width=True
        )
    
    st.markdown(f"""
        <div style="background: #f0f4f8; padding: 8px 16px; border-radius: 8px; margin-bottom: 14px; border-right: 4px solid #00b4d8;">
            <strong>📊 عدد العروض: {len(filtered_offers)} عرض</strong>
            {f' (تم تصفيتها من أصل {len(raw_offers)})' if len(filtered_offers) < len(raw_offers) else ''}
        </div>
    """, unsafe_allow_html=True)

    # عرض العروض
    for idx, offer in enumerate(filtered_offers):
        offer_id = offer.get('id', 'N/A')
        offer_name = offer.get('name', 'عرض بدون اسم')
        status = offer.get('status', 'inactive')
        
        # ✅ الاستدعاء التفصيلي الحي لكل عرض لحل مشكلة اختفاء مسميات الأصناف ومجموعات العملاء
        with st.spinner(f"جاري جلب تفاصيل العرض: {offer_name}..."):
            detailed_res = safe_api_request("GET", f"{SALLA_API_URL}/{offer_id}", headers)
            offer_data = detailed_res.get("data", offer) if detailed_res else offer

        o_type_raw = offer_data.get('offer_type', '')
        o_channel_raw = offer_data.get('applied_channel', 'browser_and_application')
        o_applied_raw = offer_data.get('applied_to', 'product')
        
        start_date = safe_parse_date(offer_data.get('start_date'))
        exp_date = safe_parse_date(offer_data.get('expiry_date'))
        
        badge = "🟢 نشط بالمتجر" if status == "active" else "🔴 متوقف حالياً"
        
        # الشارات الصارمة الثلاثية المحدثة
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
        
        with st.container(border=True):
            st.markdown("""
                <div style="background-color: #ffffff; padding: 20px; border-radius: 0px 0px 12px 12px; 
                            border: 1px solid #e8edf2; border-top: none; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 25px;">
            """, unsafe_allow_html=True)
            
            cx, cy = st.columns(2)
            with cx:
                st.markdown(f"⚙️ **نوع العرض:** `{OFFER_TYPES_MAP.get(o_type_raw, o_type_raw)}`")
                st.markdown(f"📺 **قناة نشر العرض:** `{CHANNELS_MAP.get(o_channel_raw, o_channel_raw)}`")
                st.markdown(f"🎯 **يتم تطبيق العرض على:** `{APPLIED_TO_MAP.get(o_applied_raw, o_applied_raw)}`")
                st.markdown(f"📅 **توقيت بدء العرض:** `{offer_data.get('start_date', 'غير محدد')}`")
            with cy:
                st.markdown(f"📅 **توقيت انتهاء العرض:** `{offer_data.get('expiry_date', 'بدون تاريخ (مستمر)')}`")
                st.markdown(f"🛡️ **الحد الأقصى للخصم:** `{offer_data.get('max_discount_amount', 0)} SAR` | 💵 **الحد الأدنى للشراء:** `{offer_data.get('min_purchase_amount', 0)} SAR`")
                
                c_groups_raw = offer_data.get('customer_groups', [])
                c_groups_rendered = ", ".join([str(g.get('name', g.get('id', g))) if isinstance(g, dict) else str(g) for g in c_groups_raw]) if c_groups_raw else "كل المجموعات"
                st.markdown(f"👥 **مجموعة العملاء المستهدفة:** `{c_groups_rendered}`")
                
                st.markdown(f"**🔖 تطبيق العرض مع كوبون التخفيض؟** `{'نعم' if offer_data.get('applied_with_coupon') else 'لا يطبق'}`")
                st.markdown(f"**📢 نص رسالة العرض:** *{offer_data.get('message', 'لا توجد رسالة مرفقة')}*")
                
            st.markdown("<hr style='margin: 15px 0; border-top: 1px dashed #e2e8f0;'>", unsafe_allow_html=True)
            
            col_x, col_y = st.columns(2)
            with col_x:
                st.markdown("<b style='color:#0f1c2e;'>🛒 مجموعة الشراء (X) - [إذا اشترى العميل]:</b>", unsafe_allow_html=True)
                buy_obj = offer_data.get('buy', {})
                buy_products = buy_obj.get('products', [])
                buy_categories = buy_obj.get('categories', [])
                if buy_products or buy_categories:
                    buy_text = parse_products_cleanly({'products': buy_products, 'categories': buy_categories})
                else:
                    buy_text = "جميع الأصناف المشمولة"
                st.text(buy_text)
                st.caption(f"الكمية المطلوبة: {buy_obj.get('quantity', 1)} قطعة")
            with col_y:
                st.markdown("<b style='color:#0f1c2e;'>🎁 مجموعة المنح والهدية (Y) - [يحصل على]:</b>", unsafe_allow_html=True)
                get_obj = offer_data.get('get', {})
                get_products = get_obj.get('products', [])
                get_categories = get_obj.get('categories', [])
                if get_products or get_categories:
                    get_text = parse_products_cleanly({'products': get_products, 'categories': get_categories})
                else:
                    get_text = "جميع الأصناف المشمولة"
                st.text(get_text)
                st.caption(f"كمية المنح/الخصم: {get_obj.get('quantity', 1)} قطعة")
                if get_obj.get('discount_amount'):
                    st.markdown(f"🔥 **قيمة/نسبة الخصم :** `{get_obj.get('discount_amount')}`")

            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2, b3 = st.columns(3)
            with b1:
                t_status = "inactive" if status == "active" else "active"
                lbl = "🛑 إيقاف العرض" if status == "active" else "▶️ إعادة تفعيل العرض"
                if st.button(lbl, key=f"t_st_{offer_id}_{idx}", use_container_width=True):
                    safe_api_request("PUT", f"{SALLA_API_URL}/{offer_id}/status", headers, json={"status": t_status})
                    st.rerun()
            with b2:
                if st.button("🔖 عكس تطبيق العرض مع الكوبون ⏯", key=f"t_cp_{offer_id}_{idx}", use_container_width=True):
                    safe_api_request("PUT", f"{SALLA_API_URL}/{offer_id}", headers, json={"applied_with_coupon": not offer_data.get('applied_with_coupon', False)})
                    st.rerun()
            with b3:
                if st.button("🗑️ حذف العرض بالكامل", key=f"t_dl_{offer_id}_{idx}", use_container_width=True, type="primary"):
                    safe_api_request("DELETE", f"{SALLA_API_URL}/{offer_id}", headers)
                    st.rerun()

            # --- حاوية التعديل المتقدمة ---
            with st.expander("✏️ تعديل ومراجعة العرض الترويجي", expanded=False):
                st.markdown("✏️ تعديل البيانات والخيارات الأساسية")
                ed_name = st.text_input("تحديث إسم العرض:", value=offer_name, key=f"ed_n_{offer_id}_{idx}")
                ed_msg = st.text_input("تحديث نص رسالة العرض:", value=offer_data.get('message', ''), key=f"ed_m_{offer_id}_{idx}")
                
                ec1, ec2, ec3 = st.columns(3)
                with ec1:
                    current_type_idx = list(OFFER_TYPES_MAP.keys()).index(o_type_raw) if o_type_raw in OFFER_TYPES_MAP else 0
                    ed_type_ar = st.selectbox("تعديل نوع العرض:", list(OFFER_TYPES_MAP.values()), index=current_type_idx, key=f"ed_t_ar_{offer_id}_{idx}")
                    ed_applied_ar = st.selectbox("تعديل تطبيق العرض على:", list(APPLIED_TO_MAP.values()), index=list(APPLIED_TO_MAP.keys()).index(o_applied_raw) if o_applied_raw in APPLIED_TO_MAP else 0, key=f"ed_app_ar_{offer_id}_{idx}")
                with ec2:
                    current_chan_idx = list(CHANNELS_MAP.keys()).index(o_channel_raw) if o_channel_raw in CHANNELS_MAP else 0
                    ed_chan_ar = st.selectbox("تعديل منصة نشر العرض:", list(CHANNELS_MAP.values()), index=current_chan_idx, key=f"ed_ch_ar_{offer_id}_{idx}")
                    ed_status = st.selectbox("تعديل حالة العرض:", ["active", "inactive"], index=0 if status == "active" else 1, format_func=lambda x: "مفعل ومباشر" if x == "active" else "مسودة معطلة", key=f"ed_status_field_{offer_id}_{idx}")
                with ec3:
                    ed_coupon = st.selectbox("تطبيق العرض مع كوبون التخفيض؟", ["لا", "نعم"], index=1 if offer_data.get('applied_with_coupon') else 0, key=f"ed_c_{offer_id}_{idx}")

                selected_ed_type_key = [k for k, v in OFFER_TYPES_MAP.items() if v == ed_type_ar][0]
                selected_ed_chan_key = [k for k, v in CHANNELS_MAP.items() if v == ed_chan_ar][0]
                selected_ed_app_key = [k for k, v in APPLIED_TO_MAP.items() if v == ed_applied_ar][0]

                existing_cg_str = ", ".join([str(g.get('id', g)) if isinstance(g, dict) else str(g) for g in offer_data.get('customer_groups', [])])
                ed_cust_groups = st.text_input("تعديل مجموعة العملاء المشمولة (ضع بينهم فاصلة):", value=existing_cg_str, key=f"ed_cg_{offer_id}_{idx}")

                st.markdown("⚙️ تعديل خيارات العرض")
                ecc1, ecc2, ecc3 = st.columns(3)
                with ecc1:
                    ed_max_discount = st.number_input("تعديل الحد الأقصى للخصم (SAR):", min_value=0.0, value=safe_float(offer_data.get('max_discount_amount', 0.0)), key=f"ed_max_d_{offer_id}_{idx}")
                with ecc2:
                    ed_min_purchase = st.number_input("تعديل الحد الأدنى لمبلغ الشراء (SAR):", min_value=0.0, value=safe_float(offer_data.get('min_purchase_amount', 0.0)), key=f"ed_min_p_{offer_id}_{idx}")
                with ecc3:
                    ed_min_items = st.number_input("تعديل الحد الأدنى لكمية المنتجات (حبة):", min_value=0, value=int(safe_float(offer_data.get('min_items_count', 0.0))), key=f"ed_min_i_{offer_id}_{idx}")

                st.markdown("🛒 تعديل مجموعات الصنف والكميات للعرض")
                
                buy_p_ids_list = [str(p.get('id', '')) if isinstance(p, dict) else str(p) for p in buy_obj.get('products', [])]
                buy_p_ids = ",".join(buy_p_ids_list) if buy_p_ids_list else ""
                
                get_p_ids_list = [str(p.get('id', '')) if isinstance(p, dict) else str(p) for p in get_obj.get('products', [])]
                get_p_ids = ",".join(get_p_ids_list) if get_p_ids_list else ""
                
                if selected_ed_type_key == "buy_x_get_y":
                    eq1, eq2 = st.columns(2)
                    with eq1:
                        ed_buy_type = st.selectbox("تعديل نوع شراء X:", ["product", "category"], index=0 if buy_obj.get('type', 'product') == 'product' else 1, key=f"ed_bt_{offer_id}_{idx}")
                        ed_buy_qty = st.number_input("تعديل كمية الشراء - [إذا اشترى] (X):", min_value=1, value=int(buy_obj.get('quantity', 1)), key=f"ed_bq_{offer_id}_{idx}")
                        ed_buy_products = st.text_input("تعديل (IDs) إذا اشترى العميل:", value=buy_p_ids, key=f"ed_bp_ids_{offer_id}_{idx}")
                    with eq2:
                        ed_get_type = st.selectbox("تعديل نوع عرض Y:", ["product", "category"], index=0 if get_obj.get('type', 'product') == 'product' else 1, key=f"ed_gt_{offer_id}_{idx}")
                        ed_get_qty = st.number_input("تعديل كمية العرض - [يحصل على] (Y):", min_value=1, value=int(get_obj.get('quantity', 1)), key=f"ed_gq_{offer_id}_{idx}")
                        ed_get_products = st.text_input("تعديل (IDs) يحصل العميل على:", value=get_p_ids, key=f"ed_gp_ids_{offer_id}_{idx}")
                    
                    current_disc_type_raw = "خصم بنسبة" if get_obj.get('discount_type', 'free-product') == 'percentage' else "منتج مجاني"
                    ed_discount_type_ar = st.selectbox("تعديل نوع الخصم Y:", ["منتج مجاني", "خصم بنسبة"], index=1 if current_disc_type_raw == "خصم بنسبة" else 0, key=f"ed_dt_ar_{offer_id}_{idx}")
                    
                    if ed_discount_type_ar == "خصم بنسبة":
                        ed_disc_amt = st.number_input("تعديل نسبة الخصم المطبقة على Y (%):", min_value=1.0, max_value=100.0, value=safe_float(get_obj.get('discount_amount', 50.0)), key=f"ed_da_{offer_id}_{idx}")
                        ed_disc_type = "percentage"
                    else:
                        ed_disc_amt = 0.0
                        ed_disc_type = "free-product"
                else:
                    eq1, eq2 = st.columns(2)
                    with eq1:
                        ed_disc_amt = st.number_input("تعديل قيمة أو نسبة الخصم:", min_value=0.0, value=safe_float(get_obj.get('discount_amount', 10.0)), key=f"ed_da_direct_{offer_id}_{idx}")
                        ed_buy_products = st.text_input("تعديل (IDs) لمنتجات التخفيض:", value=buy_p_ids, key=f"ed_bp_direct_{offer_id}_{idx}")
                    with eq2:
                        st.caption("ملاحظة: هذا النوع من العروض يطبق بشكل مباشر وتلقائي على مستودع الأصناف المحددة.")
                    ed_buy_type = "product"
                    ed_buy_qty = 1
                    ed_get_type = "product"
                    ed_get_qty = 1
                    ed_get_products = ""
                    ed_disc_type = "percentage" if selected_ed_type_key == "percentage" else "fixed_amount"

                st.markdown("**📅 تعديل تاريخ بدء العرض:**")
                col_ed_start_date, col_ed_start_time = st.columns(2)
                with col_ed_start_date:
                    ed_start_date_val = st.date_input("اختر التاريخ:", value=safe_parse_date(offer_data.get('start_date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))).date() if safe_parse_date(offer_data.get('start_date')) else datetime.now().date(), key=f"ed_s_date_{offer_id}_{idx}")
                with col_ed_start_time:
                    ed_start_time_val = st.time_input("اختر الوقت:", value=safe_parse_date(offer_data.get('start_date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))).time() if safe_parse_date(offer_data.get('start_date')) else datetime.now().time(), key=f"ed_start_time_{offer_id}_{idx}", step=60)
                ed_start = datetime.combine(ed_start_date_val, ed_start_time_val).strftime('%Y-%m-%d %H:%M:%S')
                
                st.markdown("**📅 تعديل تاريخ انتهاء العرض:**")
                col_ed_end_date, col_ed_end_time = st.columns(2)
                with col_ed_end_date:
                    ed_end_date_val = st.date_input("اختر التاريخ:", value=safe_parse_date(offer_data.get('expiry_date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))).date() if safe_parse_date(offer_data.get('expiry_date')) else (datetime.now() + timedelta(days=30)).date(), key=f"ed_e_date_{offer_id}_{idx}")
                with col_ed_end_time:
                    ed_end_time_val = st.time_input("اختر الوقت:", value=safe_parse_date(offer_data.get('expiry_date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))).time() if safe_parse_date(offer_data.get('expiry_date')) else datetime.now().time().replace(hour=23, minute=59, second=59), key=f"ed_end_time_{offer_id}_{idx}", step=60)
                ed_end = datetime.combine(ed_end_date_val, ed_end_time_val).strftime('%Y-%m-%d %H:%M:%S')
                
                if st.button("💾Box اعتماد وحفظ العرض المحدث", key=f"sv_of_{offer_id}_{idx}", type="primary", use_container_width=True):
                    try:
                        b_p_list = [int(i.strip()) for i in ed_buy_products.split(",") if i.strip().isdigit()] if ed_buy_products.strip() else []
                        cg_p_list = [int(g.strip()) for g in ed_cust_groups.split(",") if g.strip().isdigit()] if ed_cust_groups.strip() else []
                        
                        update_payload = {
                            "name": ed_name, "message": ed_msg, "start_date": ed_start, "expiry_date": ed_end,
                            "status": ed_status, "offer_type": selected_ed_type_key, "applied_channel": selected_ed_chan_key, "applied_to": selected_ed_app_key,
                            "applied_with_coupon": ed_coupon == "نعم", "max_discount_amount": float(ed_max_discount), "min_purchase_amount": float(ed_min_purchase), "min_items_count": int(ed_min_items),
                            "customer_groups": cg_p_list,
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
