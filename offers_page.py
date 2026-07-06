import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
from utils import (
    get_headers, safe_api_request, SALLA_API_URL, generate_salla_excel_template,
    process_excel_import, export_offers_to_excel, safe_parse_date, parse_products_cleanly,
    OFFER_TYPES_MAP, CHANNELS_MAP, APPLIED_TO_MAP, safe_float
)

def render_offers_page():
    st.markdown("""
    <div style="background: linear-gradient(135deg, #0F1C2E 0%, #00EBCF 100%); padding: 15px 25px; border-radius: 12px; color: white; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        <h2 style="color: white; margin: 0;">📊 مركز إدارة العروض الخاصة المتقدم</h2>
    </div>
    """, unsafe_allow_html=True)
    
    headers = get_headers()
    if not headers: return

    # ✅ دالة جلب شاملة لتفادي أخطاء per_page <= 60
    def fetch_all_pages(url_base):
        all_data = []
        page = 1
        while True:
            url = f"{url_base}?per_page=60&page={page}" if "?" not in url_base else f"{url_base}&per_page=60&page={page}"
            res = safe_api_request("GET", url, headers)
            if not res or not res.get("data"): break
            all_data.extend(res["data"])
            if page >= res.get("pagination", {}).get("totalPages", 1): break
            page += 1
        return all_data
    
    # ==========================================
    # ⚙️ تهيئة وجلب البيانات المساعدة تلقائياً
    # ==========================================
    if "all_products" not in st.session_state: st.session_state["all_products"] = []
    if "all_categories" not in st.session_state: st.session_state["all_categories"] = []
    if "all_brands" not in st.session_state: st.session_state["all_brands"] = []
    
    with st.spinner("🔄 جاري تهيئة البيانات المساعدة (المنتجات، التصنيفات، والماركات) للعروض..."):
        if not st.session_state["all_categories"]:
            st.session_state["all_categories"] = fetch_all_pages("https://api.salla.dev/admin/v2/categories")
        if not st.session_state["all_brands"]:
            st.session_state["all_brands"] = fetch_all_pages("https://api.salla.dev/admin/v2/brands")
        if not st.session_state["all_products"]:
            st.session_state["all_products"] = fetch_all_pages("https://api.salla.dev/admin/v2/products")

    def render_dynamic_selection(label, selection_type, existing_ids, key_prefix):
        options = {}
        if selection_type == "product":
            for p in st.session_state.get("all_products", []):
                options[f"🆔 {p.get('id')} - SKU:{p.get('sku','')} - {p.get('name','')}"] = p.get('id')
        elif selection_type == "category":
            for c in st.session_state.get("all_categories", []):
                options[f"📁 {c.get('name','')} - (ID:{c.get('id')})"] = c.get('id')
        elif selection_type == "brand":
            for b in st.session_state.get("all_brands", []):
                options[f"🏢 {b.get('name','')} - (ID:{b.get('id')})"] = b.get('id')
                
        selected_labels = []
        options_inv = {v: k for k, v in options.items()}
        for eid in existing_ids:
            if eid in options_inv: selected_labels.append(options_inv[eid])
            else:
                fallback = f"ID: {eid} (غير متوفر)"
                options[fallback] = eid
                selected_labels.append(fallback)
                
        selected = st.multiselect(label, options=list(options.keys()), default=selected_labels, key=key_prefix)
        return [options[s] for s in selected]

    def rebuild_offer_payload(full_offer: dict, overrides: dict) -> dict:
        def get_id(field_name):
            val = full_offer.get(field_name)
            return val.get("id") if isinstance(val, dict) else val

        payload = {
            "name": full_offer.get("name", "عرض خاص"), "status": get_id("status") or "active",
            "offer_type": get_id("offer_type") or "buy_x_get_y", "applied_channel": get_id("applied_channel") or "browser",
            "applied_to": get_id("applied_to") or "all", "applied_with_coupon": full_offer.get("applied_with_coupon", False)
        }
        
        if full_offer.get("start_date"): payload["start_date"] = full_offer["start_date"]
        if full_offer.get("expiry_date"): payload["expiry_date"] = full_offer["expiry_date"]
        elif full_offer.get("end_date"): payload["expiry_date"] = full_offer["end_date"]
            
        for key in ["max_discount_amount", "min_purchase_amount", "min_items_count"]:
            if full_offer.get(key) is not None: payload[key] = safe_float(full_offer[key]) if "amount" in key else int(safe_float(full_offer[key]))
                
        if full_offer.get("customer_groups"): payload["customer_groups"] = [g.get("id", g) if isinstance(g, dict) else g for g in full_offer["customer_groups"]]
            
        if full_offer.get("buy"):
            buy = full_offer["buy"]
            b_type = buy.get("type", {}).get("id") if isinstance(buy.get("type"), dict) else buy.get("type")
            payload["buy"] = {"type": b_type or "quantity", "quantity": int(buy.get("quantity", 1))}
            b_prods = [p.get("id", p) if isinstance(p, dict) else p for p in buy.get("products", [])]
            if b_prods: payload["buy"]["products"] = b_prods
            b_cats = [c.get("id", c) if isinstance(c, dict) else c for c in buy.get("categories", [])]
            if b_cats: payload["buy"]["categories"] = b_cats
            b_brands = [b.get("id", b) if isinstance(b, dict) else b for b in buy.get("brands", [])]
            if b_brands: payload["buy"]["brands"] = b_brands
                
        if full_offer.get("get"):
            get_obj = full_offer["get"]
            g_type = get_obj.get("type", {}).get("id") if isinstance(get_obj.get("type"), dict) else get_obj.get("type")
            g_disc_type = get_obj.get("discount_type", {}).get("id") if isinstance(get_obj.get("discount_type"), dict) else get_obj.get("discount_type")
            payload["get"] = {"type": g_type or "quantity", "quantity": int(get_obj.get("quantity", 1)), "discount_type": g_disc_type or "percentage"}
            if get_obj.get("discount_amount") is not None: payload["get"]["discount_amount"] = safe_float(get_obj["discount_amount"])
                
            g_prods = [p.get("id", p) if isinstance(p, dict) else p for p in get_obj.get("products", [])]
            if g_prods: payload["get"]["products"] = g_prods
            g_cats = [c.get("id", c) if isinstance(c, dict) else c for c in get_obj.get("categories", [])]
            if g_cats: payload["get"]["categories"] = g_cats
            g_brands = [b.get("id", b) if isinstance(b, dict) else b for b in get_obj.get("brands", [])]
            if g_brands: payload["get"]["brands"] = g_brands

        for k, v in overrides.items(): payload[k] = v
        return payload

    col_dl, col_ex = st.columns([1, 1])
    with col_dl:
        st.download_button("📥 تنزيل نموذج استيراد العروض الترويجية", data=generate_salla_excel_template(), file_name="Salla_Offers_Template.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        
    with st.spinner("🔄 جاري جلب كافة العروض (نشطة وغير نشطة) من سلة..."):
        raw_offers = fetch_all_pages(SALLA_API_URL)
        
    with col_ex:
        if raw_offers:
            st.download_button("📥 تصدير قائمة العروض الحالية", data=export_offers_to_excel(raw_offers), file_name=f"Offers_Export_{datetime.now().strftime('%Y%m%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, type="primary")

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
    # ✅ أزرار الإجراءات الجماعية المتقدمة
    # ==========================================
    st.markdown("### ⚡ إجراءات جماعية سريعة على العروض")
    col_bulk1, col_bulk2, col_bulk3 = st.columns(3)
    
    with col_bulk1:
        if st.button("⏹️ إيقاف جميع العروض المفعلة", use_container_width=True, type="primary"):
            active_offers = [o for o in raw_offers if o.get('status') == 'active']
            if not active_offers: st.warning("⚠️ لا توجد عروض مفعلة حالياً لإيقافها")
            else:
                with st.spinner(f"🔄 جاري إيقاف {len(active_offers)} عرض مفعل..."):
                    success_count = 0
                    for offer in active_offers:
                        offer_id = offer.get('id')
                        if offer_id and safe_api_request("PUT", f"{SALLA_API_URL}/{offer_id}/status", headers, json={"status": "inactive"}): success_count += 1
                    st.success(f"✅ تم إيقاف {success_count} عرض بنجاح من أصل {len(active_offers)}")
                    if success_count > 0: st.rerun()
    
    with col_bulk2:
        with st.popover("📅 تمديد وإدارة تواريخ الانتهاء"):
            target_scope_end = st.radio("استهداف العروض:", ["تنتهي في تاريخ محدد", "جميع العروض المتاحة"], key="b_end_scope")
            if target_scope_end == "تنتهي في تاريخ محدد":
                col_date1, col_time1 = st.columns(2)
                with col_date1: target_date = st.date_input("تاريخ الانتهاء الحالي للفحص:", value=datetime.now().date(), key="be_t_date")
                with col_time1: target_time = st.time_input("الوقت:", value=datetime.now().time().replace(minute=59, second=59), key="be_t_time")
                target_str = datetime.combine(target_date, target_time).strftime('%Y-%m-%d')
                matching_offers_end = [o for o in raw_offers if o.get('expiry_date', '') and o.get('expiry_date', '').startswith(target_str)]
                st.info(f"📊 عدد العروض المطابقة: **{len(matching_offers_end)}** عرض")
            else:
                matching_offers_end = raw_offers
                st.info(f"📊 سيتم تطبيق الإجراء على جميع العروض ({len(matching_offers_end)} عرض)")

            action_type = st.radio("الإجراء المطلوب تنفيذه:", ["تاريخ جديد للتمديد", "إلغاء التفعيل (إيقاف)"], key="be_action")
            if action_type == "تاريخ جديد للتمديد":
                col_date2, col_time2 = st.columns(2)
                with col_date2: new_date = st.date_input("التاريخ الجديد:", value=datetime.now().date() + timedelta(days=30), key="be_n_date")
                with col_time2: new_time = st.time_input("الوقت الجديد:", value=datetime.now().time().replace(minute=59, second=59), key="be_n_time")
                new_expiry_str = datetime.combine(new_date, new_time).strftime('%Y-%m-%d %H:%M:%S')
                st.info(f"📅 سيتم تمديد العروض المطابقة إلى **{new_expiry_str}**")
                btn_lbl = "🔄 تطبيق التمديد"
            else:
                st.info("🔴 سيتم إيقاف العروض المطابقة ونقلها للمسودات")
                btn_lbl = "🛑 تطبيق الإيقاف"
            
            if st.button(btn_lbl, use_container_width=True, type="primary"):
                if not matching_offers_end: st.warning("⚠️ لا توجد عروض مطابقة")
                else:
                    with st.spinner("🔄 جاري المعالجة والمزامنة..."):
                        success_count = 0
                        for offer in matching_offers_end:
                            offer_id = offer.get('id')
                            if action_type == "إلغاء التفعيل (إيقاف)":
                                if safe_api_request("PUT", f"{SALLA_API_URL}/{offer_id}/status", headers, json={"status": "inactive"}): success_count += 1
                            else:
                                full_res = safe_api_request("GET", f"{SALLA_API_URL}/{offer_id}", headers)
                                if full_res and full_res.get('data'):
                                    payload = rebuild_offer_payload(full_res['data'], {"expiry_date": new_expiry_str})
                                    if safe_api_request("PUT", f"{SALLA_API_URL}/{offer_id}", headers, json=payload): success_count += 1
                        st.success(f"✅ تم تنفيذ الإجراء لـ {success_count} عرض بنجاح!")
                        if success_count > 0: st.rerun()

    with col_bulk3:
        with st.popover("📅 إدارة تواريخ البداية"):
            target_scope_start = st.radio("استهداف العروض:", ["تبدأ في تاريخ محدد", "جميع العروض المتاحة"], key="bs_scope")
            if target_scope_start == "تبدأ في تاريخ محدد":
                col_sd1, col_st1 = st.columns(2)
                with col_sd1: target_s_date = st.date_input("تاريخ البداية الحالي للفحص:", value=datetime.now().date(), key="bs_t_date")
                with col_st1: target_s_time = st.time_input("الوقت:", value=datetime.now().time().replace(minute=0, second=0), key="bs_t_time")
                target_s_str = datetime.combine(target_s_date, target_s_time).strftime('%Y-%m-%d')
                matching_offers_start = [o for o in raw_offers if o.get('start_date', '') and o.get('start_date', '').startswith(target_s_str)]
                st.info(f"📊 عدد العروض المطابقة: **{len(matching_offers_start)}** عرض")
            else:
                matching_offers_start = raw_offers
                st.info(f"📊 سيتم تطبيق الإجراء على جميع العروض ({len(matching_offers_start)} عرض)")
            
            st.markdown("**📅 تاريخ البداية الجديد:**")
            if st.button("🕒 تعيين الوقت الحالي", key="btn_now_start_bulk"):
                st.session_state["bs_n_date"] = (datetime.now() + timedelta(hours=3)).date()
                st.session_state["bs_n_time"] = (datetime.now() + timedelta(hours=3)).time()
            col_nsd, col_nst = st.columns(2)
            with col_nsd: new_s_date = st.date_input("التاريخ الجديد لبداية العرض:", value=st.session_state.get("bs_n_date", datetime.now().date()), key="bs_n_date")
            with col_nst: new_s_time = st.time_input("الوقت الجديد:", value=st.session_state.get("bs_n_time", datetime.now().time().replace(minute=0, second=0)), key="bs_n_time")
            new_start_str = datetime.combine(new_s_date, new_s_time).strftime('%Y-%m-%d %H:%M:%S')
            
            if st.button("🚀 تطبيق تاريخ البداية المحدث", use_container_width=True, type="primary"):
                if not matching_offers_start: st.warning("⚠️ لا توجد عروض مطابقة")
                else:
                    with st.spinner("🔄 جاري التعديل..."):
                        success_count = 0
                        for offer in matching_offers_start:
                            offer_id = offer.get('id')
                            full_res = safe_api_request("GET", f"{SALLA_API_URL}/{offer_id}", headers)
                            if full_res and full_res.get('data'):
                                payload = rebuild_offer_payload(full_res['data'], {"start_date": new_start_str})
                                if safe_api_request("PUT", f"{SALLA_API_URL}/{offer_id}", headers, json=payload): success_count += 1
                        st.success(f"✅ تم تعديل تاريخ البداية لـ {success_count} عرض بنجاح!")
                        if success_count > 0: st.rerun()

    col_bulk4, col_bulk5 = st.columns([2, 1])
    with col_bulk4:
        if st.button("🚀 تطبيق وتفعيل دمج العرض مع كوبون التخفيض (لجميع العروض)", type="primary", use_container_width=True):
            with st.spinner("🔄 جاري تحديث كافة العروض..."):
                active_offers = [o for o in raw_offers if o.get("status") == "active"]
                success_count = 0
                for offer_summary in active_offers:
                    offer_id = offer_summary.get("id")
                    full_offer_res = safe_api_request("GET", f"{SALLA_API_URL}/{offer_id}", headers)
                    if not full_offer_res or not full_offer_res.get("data"): continue
                    payload = rebuild_offer_payload(full_offer_res["data"], {"applied_with_coupon": True})
                    if safe_api_request("PUT", f"{SALLA_API_URL}/{offer_id}", headers, json=payload): success_count += 1
                st.success(f"✅ تم تفعيل دمج الكوبونات لـ {success_count} عرض بنجاح!")
                
    with col_bulk5:
        if "filtered_offers" in st.session_state and st.session_state["filtered_offers"] and len(st.session_state["filtered_offers"]) < len(raw_offers):
            st.download_button("📥 تصدير العروض المفلترة", data=export_offers_to_excel(st.session_state["filtered_offers"]), file_name=f"filtered_offers_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="bulk_export_filtered_top_active", use_container_width=True, type="secondary")
        else:
            if st.button("📥 تصدير العروض المفلترة", use_container_width=True, type="secondary", key="bulk_export_filtered_top_disabled"):
                st.info("💡 يرجى استخدام فلاتر البحث في الأسفل أولاً، ليتم تصدير العروض الناتجة.")

    # ==========================================
    # --- حاوية إنشاء عرض جديد (ديناميكي) ---
    # ==========================================
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
            if st.button("🕒 تعيين الوقت الحالي", key="btn_now_start_cre"):
                st.session_state["new_start_date"] = (datetime.now() + timedelta(hours=3)).date()
                st.session_state["new_start_time"] = (datetime.now() + timedelta(hours=3)).time()
            col_start_date, col_start_time = st.columns(2)
            with col_start_date: new_start_date_val = st.date_input("اختر التاريخ:", value=st.session_state.get("new_start_date", datetime.now().date()), key="new_start_date")
            with col_start_time: new_start_time_val = st.time_input("اختر الوقت:", value=st.session_state.get("new_start_time", datetime.now().time().replace(minute=0, second=0)), key="new_start_time", step=60)
            new_start_date = datetime.combine(new_start_date_val, new_start_time_val).strftime('%Y-%m-%d %H:%M:%S')
            
            st.markdown("**📅 تاريخ انتهاء العرض:**")
            col_end_date, col_end_time = st.columns(2)
            with col_end_date: new_expiry_date_val = st.date_input("اختر التاريخ:", value=datetime.now().date() + timedelta(days=30), key="new_expiry_date")
            with col_end_time: new_expiry_time_val = st.time_input("اختر الوقت:", value=datetime.now().time().replace(hour=23, minute=59, second=59), key="new_expiry_time", step=60)
            new_expiry_date = datetime.combine(new_expiry_date_val, new_expiry_time_val).strftime('%Y-%m-%d %H:%M:%S')
            
        new_cust_groups_input = st.text_input("معرفات مجموعة العملاء المشمولة (مفصولة بفاصلة ,) - اتركها فارغة للكل:", placeholder="مثال: 10294, 33451", key="new_cust_groups_creation")

        selected_type_key = [k for k, v in OFFER_TYPES_MAP.items() if v == new_offer_type_ar][0]
        selected_channel_key = [k for k, v in CHANNELS_MAP.items() if v == new_channel_ar][0]
        selected_applied_to_key = [k for k, v in APPLIED_TO_MAP.items() if v == new_applied_to_ar][0]

        st.markdown("⚙️ تفاصيل العرض المتقدمة")
        ca1, ca2, ca3 = st.columns(3)
        with ca1: new_max_discount = st.number_input("الحد الأقصى للخصم (SAR) - 0 لعدم التقييد:", min_value=0.0, value=0.0, key="cre_max_d")
        with ca2: new_min_purchase = st.number_input("الحد الأدنى لمبلغ الشراء (SAR) - 0 لعدم التقييد:", min_value=0.0, value=0.0, key="cre_min_p")
        with ca3: new_min_items = st.number_input("الحد الأدنى لكمية المنتجات:", min_value=0, value=0, step=1, key="cre_min_i")
            
        st.markdown("🛒 شروط وخيارات العرض")
        type_options_ar = ["منتجات", "تصنيفات", "ماركات"]
        type_map = {"منتجات": "product", "تصنيفات": "category", "ماركات": "brand"}
        
        if selected_type_key == "buy_x_get_y":
            col_bx, col_by = st.columns(2)
            with col_bx:
                new_buy_type_ar = st.selectbox("نوع شرط الشراء X:", type_options_ar, key="cre_buy_type_select")
                new_buy_type = type_map[new_buy_type_ar]
                new_buy_qty = st.number_input("[إذا اشترى] - كمية الشراء (X):", min_value=1, value=1, key="cre_buy_qty_input")
                buy_selected_ids = render_dynamic_selection(f"اختر {new_buy_type_ar} (X):", new_buy_type, [], "cre_buy_X")
            with col_by:
                new_get_type_ar = st.selectbox("نوع صنف الهدية الممنوحة Y:", type_options_ar, key="cre_get_type_select")
                new_get_type = type_map[new_get_type_ar]
                new_get_qty = st.number_input("[يحصل على] - كمية/نسبة القطع الممنوحة (Y):", min_value=1, value=1, key="cre_get_qty_input")
                get_selected_ids = render_dynamic_selection(f"اختر {new_get_type_ar} الممنوحة (Y):", new_get_type, [], "cre_get_Y")
            
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
                new_buy_type_ar = st.selectbox("نوع التخفيض المطبق على:", type_options_ar, key="cre_buy_type_direct")
                new_buy_type = type_map[new_buy_type_ar]
                buy_selected_ids = render_dynamic_selection(f"اختر {new_buy_type_ar} التخفيض:", new_buy_type, [], "cre_buy_direct")
            with col_p2:
                st.caption("عروض النسبة والمبالغ المقطوعة والسعر الثابت تطبق بشكل فوري ومباشر على الخيارات المحددة دون اشتراط هدايا معها.")
            new_buy_qty = 1
            new_get_type = "product"
            new_get_qty = 1
            get_selected_ids = []
            new_discount_type = "percentage" if selected_type_key == "percentage" else "fixed_amount"
        
        if st.button("🚀 إنشاء العرض ونشره بالمتجر الآن", type="primary", use_container_width=True, key="save_new_offer_green"):
            try:
                cg_ids = [int(g.strip()) for g in new_cust_groups_input.split(",") if g.strip().isdigit()] if new_cust_groups_input.strip() else []
                payload = {
                    "name": new_offer_name, "offer_type": selected_type_key, "message": new_message,
                    "applied_channel": selected_channel_key, "applied_to": selected_applied_to_key,
                    "start_date": new_start_date, "expiry_date": new_expiry_date, "status": "active",
                    "applied_with_coupon": new_with_coupon == "نعم", "customer_groups": cg_ids,
                    "max_discount_amount": float(new_max_discount), "min_purchase_amount": float(new_min_purchase),
                    "min_items_count": int(new_min_items),
                    "buy": {"type": new_buy_type, "quantity": int(new_buy_qty)},
                    "get": {"type": new_get_type, "quantity": int(new_get_qty), "discount_type": new_discount_type}
                }
                
                if new_buy_type == "product" and buy_selected_ids: payload["buy"]["products"] = buy_selected_ids
                elif new_buy_type == "category" and buy_selected_ids: payload["buy"]["categories"] = buy_selected_ids
                elif new_buy_type == "brand" and buy_selected_ids: payload["buy"]["brands"] = buy_selected_ids
                
                if selected_type_key == "buy_x_get_y":
                    if new_get_type == "product" and get_selected_ids: payload["get"]["products"] = get_selected_ids
                    elif new_get_type == "category" and get_selected_ids: payload["get"]["categories"] = get_selected_ids
                    elif new_get_type == "brand" and get_selected_ids: payload["get"]["brands"] = get_selected_ids
                    
                if new_discount_amount > 0: payload["get"]["discount_amount"] = float(new_discount_amount)
                    
                if safe_api_request("POST", SALLA_API_URL, headers, json=payload):
                    st.success("✅ تم إنشاء العرض الترويجي بنجاح!")
                    st.rerun()
            except Exception as e: st.error(f"خطأ أثناء إنشاء العرض: {str(e)}")

    st.divider()

    # ==========================================
    # --- أدوات التصفية والبحث ---
    # ==========================================
    st.markdown(" 🔍 أدوات التصفية والبحث المتقدمة عن العروض")
    f1, f2, f3, f4 = st.columns(4)
    with f1: search_offer = st.text_input("🔎 ابحث باسم العرض أو بالمعرف:", key="filter_search_input")
    with f2: status_filter = st.selectbox("📌 حالة نشاط العرض:", ["الكل", "نشط", "غير نشط"], key="filter_status_select", help="ملاحظة: عند استخدام مربع البحث سيتم تجاهل هذا الفلتر للبحث في كافة العروض")
    with f3: filter_date = st.date_input("📅 ابحث عن تاريخ الانتهاء:", value=None, key="filter_date_input")
    with f4: filter_overlap = st.checkbox("🔄 فحص التداخل (منتجات مكررة)", key="f_overlap")

    # 🕒 ضبط التوقيت ليتوافق مع توقيت السعودية KSA (لتصحيح شارة "لم تبدأ بعد")
    now_ksa = datetime.now() + timedelta(hours=3)
    
    overlapping_offer_ids = set()
    if filter_overlap:
        with st.spinner("🔄 جاري تحليل تفاصيل جميع العروض للبحث عن تداخل المنتجات..."):
            product_offer_map = {}
            for o in raw_offers:
                o_id = o.get('id')
                if o.get('status') != 'active': continue
                full_res = safe_api_request("GET", f"{SALLA_API_URL}/{o_id}", headers)
                if full_res and full_res.get('data'):
                    p_ids = set()
                    for p in full_res['data'].get('buy', {}).get('products', []): p_ids.add(str(p.get('id', p) if isinstance(p, dict) else p))
                    for p in full_res['data'].get('get', {}).get('products', []): p_ids.add(str(p.get('id', p) if isinstance(p, dict) else p))
                    for pid in p_ids:
                        if pid not in product_offer_map: product_offer_map[pid] = []
                        product_offer_map[pid].append(o_id)
            for pid, o_ids in product_offer_map.items():
                if len(o_ids) > 1: overlapping_offer_ids.update(o_ids)
            if not overlapping_offer_ids: st.success("✅ ممتاز! لا يوجد أي تداخل في منتجات العروض النشطة.")
            else: st.warning(f"⚠️ انتبه: تم العثور على منتجات مكررة مشتركة بين {len(overlapping_offer_ids)} عروض نشطة.")

    filtered_offers = []
    for offer in raw_offers:
        offer_id = offer.get('id', 'N/A')
        offer_name = offer.get('name', 'عرض بدون اسم')
        status = offer.get('status', 'inactive')
        
        start_date = safe_parse_date(offer.get('start_date'))
        exp_date = safe_parse_date(offer.get('expiry_date'))
        
        # ✅ تجاهل فلتر النشاط إذا قام المستخدم بالبحث عن اسم معين
        if search_offer:
            if search_offer.lower() not in offer_name.lower() and search_offer not in str(offer_id): continue
        else:
            if status_filter == "نشط" and status != "active": continue
            if status_filter == "غير نشط" and status == "active": continue
            
        if filter_date and (not exp_date or exp_date.date() != filter_date): continue
        if filter_overlap and offer_id not in overlapping_offer_ids: continue
        filtered_offers.append(offer)
    
    st.session_state["filtered_offers"] = filtered_offers
    
    if filtered_offers and len(filtered_offers) < len(raw_offers):
        st.download_button("📥 اضغط هنا لتحميل ملف العروض المفلترة الحالية مباشرة", data=export_offers_to_excel(filtered_offers), file_name=f"filtered_offers_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="direct_download_filtered_offers_bottom_final", type="primary", use_container_width=True)
    
    st.markdown(f"""
        <div style="background: #f0f4f8; padding: 8px 16px; border-radius: 8px; margin-bottom: 14px; border-right: 4px solid #00b4d8;">
            <strong>📊 عدد العروض المطابقة للبحث: {len(filtered_offers)} عرض</strong>
            {f' (تم تصفيتها من أصل {len(raw_offers)})' if len(filtered_offers) < len(raw_offers) else ''}
        </div>
    """, unsafe_allow_html=True)

    # ==========================================
    # --- عرض بطاقات العروض ---
    # ==========================================
    inv_type_map = {"product": "منتجات", "category": "تصنيفات", "brand": "ماركات"}
    type_options_ar = ["منتجات", "تصنيفات", "ماركات"]
    type_map = {"منتجات": "product", "تصنيفات": "category", "ماركات": "brand"}
    
    for idx, offer in enumerate(filtered_offers):
        offer_id = offer.get('id', 'N/A')
        offer_name = offer.get('name', 'عرض بدون اسم')
        status = offer.get('status', 'inactive')
        
        with st.spinner(f"جاري جلب تفاصيل العرض: {offer_name}..."):
            detailed_res = safe_api_request("GET", f"{SALLA_API_URL}/{offer_id}", headers)
            offer_data = detailed_res.get("data", offer) if detailed_res else offer

        o_type_raw = offer_data.get('offer_type', '')
        o_channel_raw = offer_data.get('applied_channel', 'browser_and_application')
        o_applied_raw = offer_data.get('applied_to', 'product')
        
        start_date = safe_parse_date(offer_data.get('start_date'))
        exp_date = safe_parse_date(offer_data.get('expiry_date'))
        
        badge = "🟢 نشط بالمتجر" if status == "active" else "🔴 متوقف حالياً"
        
        # ✅ تطبيق تصحيح الوقت (now_ksa) على شارات الانتهاء والبدء
        if start_date and start_date > now_ksa: exp_badge = "⏳ لم يبدأ بعد"
        elif exp_date and exp_date < now_ksa: exp_badge = "⚠️ منتهي الصلاحية"
        else: exp_badge = "⏳ ساري الصلاحية"
        
        st.markdown(f"""
            <div style="background: linear-gradient(135deg, #0f1c2e 0%, #1a365d 100%); padding: 14px 20px; border-radius: 12px 12px 0px 0px; margin-top: 25px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; border-bottom: 3px solid #00b4d8;">
                <span style="color: #ffffff; font-weight: bold; font-size: 16px;">🎯 {offer_name} (ID: {offer_id})</span>
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                    <span style="background: rgba(255,255,255,0.2); color: #fff; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;">{badge}</span>
                    <span style="background: rgba(255,193,7,0.25); color: #ffca28; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;">{exp_badge}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        with st.container(border=True):
            st.markdown("""<div style="background-color: #ffffff; padding: 20px; border-radius: 0px 0px 12px 12px; border: 1px solid #e8edf2; border-top: none; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 25px;">""", unsafe_allow_html=True)
            
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
                b_type_raw = buy_obj.get("type", "product")
                if isinstance(b_type_raw, dict): b_type_raw = b_type_raw.get("id", "product")
                st.text(f"مطبق على: {inv_type_map.get(b_type_raw, 'منتجات')}")
                st.caption(f"الكمية المطلوبة: {buy_obj.get('quantity', 1)} قطعة")
            with col_y:
                st.markdown("<b style='color:#0f1c2e;'>🎁 مجموعة المنح والهدية (Y) - [يحصل على]:</b>", unsafe_allow_html=True)
                get_obj = offer_data.get('get', {})
                g_type_raw = get_obj.get("type", "product")
                if isinstance(g_type_raw, dict): g_type_raw = g_type_raw.get("id", "product")
                st.text(f"مطبق على: {inv_type_map.get(g_type_raw, 'منتجات')}")
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

            # --- حاوية التعديل المتقدمة (ديناميكية) ---
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
                with ecc1: ed_max_discount = st.number_input("تعديل الحد الأقصى للخصم (SAR):", min_value=0.0, value=safe_float(offer_data.get('max_discount_amount', 0.0)), key=f"ed_max_d_{offer_id}_{idx}")
                with ecc2: ed_min_purchase = st.number_input("تعديل الحد الأدنى لمبلغ الشراء (SAR):", min_value=0.0, value=safe_float(offer_data.get('min_purchase_amount', 0.0)), key=f"ed_min_p_{offer_id}_{idx}")
                with ecc3: ed_min_items = st.number_input("تعديل الحد الأدنى لكمية المنتجات (حبة):", min_value=0, value=int(safe_float(offer_data.get('min_items_count', 0.0))), key=f"ed_min_i_{offer_id}_{idx}")

                st.markdown("🛒 تعديل مجموعات الصنف والكميات للعرض")
                
                if selected_ed_type_key == "buy_x_get_y":
                    eq1, eq2 = st.columns(2)
                    with eq1:
                        ed_buy_type_ar = st.selectbox("تعديل نوع شراء X:", type_options_ar, index=type_options_ar.index(inv_type_map.get(b_type_raw, "منتجات")), key=f"ed_bt_{offer_id}_{idx}")
                        ed_buy_type = type_map[ed_buy_type_ar]
                        ed_buy_qty = st.number_input("تعديل كمية الشراء - [إذا اشترى] (X):", min_value=1, value=int(buy_obj.get('quantity', 1)), key=f"ed_bq_{offer_id}_{idx}")
                        
                        existing_buy_ids = []
                        if ed_buy_type == "product": existing_buy_ids = [p.get('id', p) if isinstance(p, dict) else p for p in buy_obj.get('products', [])]
                        elif ed_buy_type == "category": existing_buy_ids = [c.get('id', c) if isinstance(c, dict) else c for c in buy_obj.get('categories', [])]
                        elif ed_buy_type == "brand": existing_buy_ids = [b.get('id', b) if isinstance(b, dict) else b for b in buy_obj.get('brands', [])]
                        ed_buy_selected_ids = render_dynamic_selection(f"تعديل {ed_buy_type_ar} الشراء (X):", ed_buy_type, existing_buy_ids, f"ed_buy_X_{offer_id}_{idx}")
                    
                    with eq2:
                        ed_get_type_ar = st.selectbox("تعديل نوع عرض Y:", type_options_ar, index=type_options_ar.index(inv_type_map.get(g_type_raw, "منتجات")), key=f"ed_gt_{offer_id}_{idx}")
                        ed_get_type = type_map[ed_get_type_ar]
                        ed_get_qty = st.number_input("تعديل كمية العرض - [يحصل على] (Y):", min_value=1, value=int(get_obj.get('quantity', 1)), key=f"ed_gq_{offer_id}_{idx}")
                        
                        existing_get_ids = []
                        if ed_get_type == "product": existing_get_ids = [p.get('id', p) if isinstance(p, dict) else p for p in get_obj.get('products', [])]
                        elif ed_get_type == "category": existing_get_ids = [c.get('id', c) if isinstance(c, dict) else c for c in get_obj.get('categories', [])]
                        elif ed_get_type == "brand": existing_get_ids = [b.get('id', b) if isinstance(b, dict) else b for b in get_obj.get('brands', [])]
                        ed_get_selected_ids = render_dynamic_selection(f"تعديل {ed_get_type_ar} الممنوحة (Y):", ed_get_type, existing_get_ids, f"ed_get_Y_{offer_id}_{idx}")
                    
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
                        ed_buy_type_ar = st.selectbox("تعديل نوع التخفيض المطبق على:", type_options_ar, index=type_options_ar.index(inv_type_map.get(b_type_raw, "منتجات")), key=f"ed_bt_direct_{offer_id}_{idx}")
                        ed_buy_type = type_map[ed_buy_type_ar]
                        
                        existing_buy_ids = []
                        if ed_buy_type == "product": existing_buy_ids = [p.get('id', p) if isinstance(p, dict) else p for p in buy_obj.get('products', [])]
                        elif ed_buy_type == "category": existing_buy_ids = [c.get('id', c) if isinstance(c, dict) else c for c in buy_obj.get('categories', [])]
                        elif ed_buy_type == "brand": existing_buy_ids = [b.get('id', b) if isinstance(b, dict) else b for b in buy_obj.get('brands', [])]
                        
                        ed_buy_selected_ids = render_dynamic_selection(f"تعديل {ed_buy_type_ar} التخفيض:", ed_buy_type, existing_buy_ids, f"ed_buy_direct_{offer_id}_{idx}")
                    with eq2:
                        st.caption("هذا النوع يطبق مباشر على الخيارات المحددة دون اشتراط هدايا معها.")
                    ed_buy_qty = 1
                    ed_get_type = "product"
                    ed_get_qty = 1
                    ed_get_selected_ids = []
                    ed_disc_type = "percentage" if selected_ed_type_key == "percentage" else "fixed_amount"

                st.markdown("**📅 تعديل تاريخ بدء العرض:**")
                if st.button("🕒 تعيين الوقت الحالي", key=f"btn_now_start_{offer_id}_{idx}"):
                    st.session_state[f"ed_s_date_{offer_id}_{idx}"] = (datetime.now() + timedelta(hours=3)).date()
                    st.session_state[f"ed_start_time_{offer_id}_{idx}"] = (datetime.now() + timedelta(hours=3)).time()
                col_ed_start_date, col_ed_start_time = st.columns(2)
                with col_ed_start_date: ed_start_date_val = st.date_input("اختر التاريخ:", value=st.session_state.get(f"ed_s_date_{offer_id}_{idx}", safe_parse_date(offer_data.get('start_date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))).date() if safe_parse_date(offer_data.get('start_date')) else datetime.now().date()), key=f"ed_s_date_{offer_id}_{idx}")
                with col_ed_start_time: ed_start_time_val = st.time_input("اختر الوقت:", value=st.session_state.get(f"ed_start_time_{offer_id}_{idx}", safe_parse_date(offer_data.get('start_date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))).time() if safe_parse_date(offer_data.get('start_date')) else datetime.now().time()), key=f"ed_start_time_{offer_id}_{idx}", step=60)
                ed_start = datetime.combine(ed_start_date_val, ed_start_time_val).strftime('%Y-%m-%d %H:%M:%S')
                
                st.markdown("**📅 تعديل تاريخ انتهاء العرض:**")
                col_ed_end_date, col_ed_end_time = st.columns(2)
                with col_ed_end_date: ed_end_date_val = st.date_input("اختر التاريخ:", value=safe_parse_date(offer_data.get('expiry_date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))).date() if safe_parse_date(offer_data.get('expiry_date')) else (datetime.now() + timedelta(days=30)).date(), key=f"ed_e_date_{offer_id}_{idx}")
                with col_ed_end_time: ed_end_time_val = st.time_input("اختر الوقت:", value=safe_parse_date(offer_data.get('expiry_date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))).time() if safe_parse_date(offer_data.get('expiry_date')) else datetime.now().time().replace(hour=23, minute=59, second=59), key=f"ed_end_time_{offer_id}_{idx}", step=60)
                ed_end = datetime.combine(ed_end_date_val, ed_end_time_val).strftime('%Y-%m-%d %H:%M:%S')
                
                if st.button("💾 اعتماد وحفظ العرض المحدث", key=f"sv_of_{offer_id}_{idx}", type="primary", use_container_width=True):
                    try:
                        cg_p_list = [int(g.strip()) for g in ed_cust_groups.split(",") if g.strip().isdigit()] if ed_cust_groups.strip() else []
                        update_payload = {
                            "name": ed_name, "message": ed_msg, "start_date": ed_start, "expiry_date": ed_end,
                            "status": ed_status, "offer_type": selected_ed_type_key, "applied_channel": selected_ed_chan_key, "applied_to": selected_ed_app_key,
                            "applied_with_coupon": ed_coupon == "نعم", "max_discount_amount": float(ed_max_discount), "min_purchase_amount": float(ed_min_purchase), "min_items_count": int(ed_min_items),
                            "customer_groups": cg_p_list,
                            "buy": {"type": ed_buy_type, "quantity": int(ed_buy_qty)},
                            "get": {"type": ed_get_type, "quantity": int(ed_get_qty), "discount_type": ed_disc_type}
                        }
                        
                        if ed_buy_type == "product" and ed_buy_selected_ids: update_payload["buy"]["products"] = ed_buy_selected_ids
                        elif ed_buy_type == "category" and ed_buy_selected_ids: update_payload["buy"]["categories"] = ed_buy_selected_ids
                        elif ed_buy_type == "brand" and ed_buy_selected_ids: update_payload["buy"]["brands"] = ed_buy_selected_ids
                        
                        if selected_ed_type_key == "buy_x_get_y":
                            if ed_get_type == "product" and ed_get_selected_ids: update_payload["get"]["products"] = ed_get_selected_ids
                            elif ed_get_type == "category" and ed_get_selected_ids: update_payload["get"]["categories"] = ed_get_selected_ids
                            elif ed_get_type == "brand" and ed_get_selected_ids: update_payload["get"]["brands"] = ed_get_selected_ids
                            
                        if ed_disc_amt > 0: update_payload["get"]["discount_amount"] = float(ed_disc_amt)
                            
                        if safe_api_request("PUT", f"{SALLA_API_URL}/{offer_id}", headers, json=update_payload):
                            st.success("✅ تم تحديث ونشر بيانات العرض بنجاح!")
                            st.rerun()
                    except Exception as e: st.error(f"خطأ أثناء حفظ التحديثات: {str(e)}")
            st.markdown("</div>", unsafe_allow_html=True)
