import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
import io
import re
from utils import (
    get_headers, safe_api_request, SALLA_API_URL, generate_salla_excel_template,
    process_excel_import, export_offers_to_excel, safe_parse_date,
    OFFER_TYPES_MAP, CHANNELS_MAP, APPLIED_TO_MAP, safe_float,
    update_product_promotions_secure
)

def render_offers_page():
    st.markdown("""
    <div style="background: linear-gradient(135deg, #0F1C2E 0%, #00EBCF 100%); padding: 15px 25px; border-radius: 12px; color: white; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        <h2 style="color: white; margin: 0;">📊 مركز إدارة العروض الخاصة المتقدم</h2>
    </div>
    """, unsafe_allow_html=True)
    
    headers = get_headers()
    if not headers: return

    # ==========================================
    # 🌟 CSS الأزرار الجانبية
    # ==========================================
    st.markdown("""
    <style>
        div[data-testid="stElementContainer"]:has(span[id^="qa-marker-"]) {
            display: none !important;
            margin: 0 !important;
            padding: 0 !important;
        }
        div[data-testid="stElementContainer"]:has(span[id^="qa-marker-"]) + div[data-testid="stElementContainer"] {
            position: fixed !important;
            right: -240px !important;
            width: 280px !important;
            background: linear-gradient(135deg, #1E293B 0%, #0F1C2E 100%) !important;
            padding: 5px 10px !important;
            border-radius: 20px 0 0 20px !important;
            border: 2px solid #00EBCF !important;
            border-right: none !important;
            z-index: 999999 !important;
            transition: right 0.4s cubic-bezier(0.4, 0, 0.2, 1) !important;
            box-shadow: -4px 4px 12px rgba(0,0,0,0.3) !important;
        }
        div[data-testid="stElementContainer"]:has(span[id^="qa-marker-"]) + div[data-testid="stElementContainer"]:hover {
            right: 0px !important;
        }
        div[data-testid="stElementContainer"]:has(span[id="qa-marker-1"]) + div[data-testid="stElementContainer"] { top: 120px; }
        div[data-testid="stElementContainer"]:has(span[id="qa-marker-2"]) + div[data-testid="stElementContainer"] { top: 185px; }
        div[data-testid="stElementContainer"]:has(span[id="qa-marker-3"]) + div[data-testid="stElementContainer"] { top: 250px; }
        div[data-testid="stElementContainer"]:has(span[id="qa-marker-4"]) + div[data-testid="stElementContainer"] { top: 315px; }
        div[data-testid="stElementContainer"]:has(span[id="qa-marker-5"]) + div[data-testid="stElementContainer"] { top: 380px; }
        div[data-testid="stElementContainer"]:has(span[id^="qa-marker-"]) + div[data-testid="stElementContainer"] button {
            width: 100% !important;
            text-align: right !important;
            padding-right: 35px !important; 
            font-size: 14px !important;
            font-weight: bold !important;
            background: transparent !important;
            border: none !important;
            color: white !important;
            box-shadow: none !important;
        }
        div[data-testid="stElementContainer"]:has(span[id^="qa-marker-"]) + div[data-testid="stElementContainer"]::before {
            content: "👈";
            position: absolute;
            left: 10px;
            top: 50%;
            transform: translateY(-50%);
            font-size: 18px;
            pointer-events: none;
        }
        
        /* ✅ تنسيق حاويات الفلاتر */
        .filter-container {
            background: linear-gradient(135deg, #1a2332 0%, #0f1c2e 100%);
            padding: 15px 20px;
            border-radius: 12px;
            border: 1px solid #2d3a4a;
            margin-bottom: 15px;
        }
        .filter-title {
            color: #00EBCF;
            font-weight: bold;
            font-size: 13px;
            text-align: center;
            margin-bottom: 8px;
            display: block;
        }
        .filter-container .stRadio > div {
            justify-content: center !important;
        }
        .filter-container .stRadio label {
            color: #cbd5e1 !important;
        }
        .filter-container .stRadio label div[data-testid="stMarkdownContainer"] p {
            color: #cbd5e1 !important;
        }
        .filter-container .stRadio [data-testid="stBaseButton-selected"] {
            background-color: #00EBCF !important;
            color: #0f1c2e !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # ==========================================
    # 🌟 دالة السحب الذكية مع شريط التقدم
    # ==========================================
    def fetch_all_pages(url_base, loading_text="جاري التحميل..."):
        all_data = []
        page = 1
        total_pages = 1
        status_text = st.empty()
        progress_bar = st.progress(0)
        
        while True:
            status_text.info(f"📥 {loading_text} (صفحة {page} من {total_pages if page > 1 else '...'}) | تم تحميل {len(all_data)} عنصر")
            
            if "?" not in url_base:
                url = f"{url_base}?per_page=60&page={page}"
            else:
                url = f"{url_base}&per_page=60&page={page}"
            
            res = safe_api_request("GET", url, headers)
            if not res or not res.get("data"):
                break
            
            if page == 1:
                total_pages = res.get("pagination", {}).get("totalPages", 1)
            
            all_data.extend(res["data"])
            progress_bar.progress(min(page / total_pages, 1.0))
            
            if page >= total_pages:
                break
            page += 1
        
        progress_bar.empty()
        status_text.empty()
        return all_data
    
    # ✅ تعريف render_dynamic_selection قبل استخدامها
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
            if eid in options_inv: 
                selected_labels.append(options_inv[eid])
            else:
                fallback = f"ID: {eid} (غير متوفر)"
                options[fallback] = eid
                selected_labels.append(fallback)
                
        selected = st.multiselect(label, options=list(options.keys()), default=selected_labels, key=key_prefix)
        return [options[s] for s in selected]
    
    # ⚙️ تهيئة وجلب البيانات المساعدة
    if "all_products" not in st.session_state: 
        st.session_state["all_products"] = []
    if "all_categories" not in st.session_state: 
        st.session_state["all_categories"] = []
    if "all_brands" not in st.session_state: 
        st.session_state["all_brands"] = []
    
    if not st.session_state["all_products"] or not st.session_state["all_categories"] or not st.session_state["all_brands"]:
        with st.spinner("🔄 جاري تهيئة البيانات المساعدة للعروض..."):
            if not st.session_state["all_categories"]: 
                st.session_state["all_categories"] = fetch_all_pages(
                    "https://api.salla.dev/admin/v2/categories", 
                    "جاري سحب التصنيفات"
                )
            if not st.session_state["all_brands"]: 
                st.session_state["all_brands"] = fetch_all_pages(
                    "https://api.salla.dev/admin/v2/brands", 
                    "جاري سحب الماركات التجارية"
                )
            if not st.session_state["all_products"]: 
                st.session_state["all_products"] = fetch_all_pages(
                    "https://api.salla.dev/admin/v2/products", 
                    "جاري سحب قائمة المنتجات"
                )

    # ✅ جلب العروض
    with st.spinner("🔄 جاري جلب كافة العروض الحالية من المتجر..."):
        raw_offers = fetch_all_pages(SALLA_API_URL, "جاري سحب العروض من متجرك")

    # ==========================================
    # ⚡ الأزرار الجانبية (كما هي)
    # ==========================================
    if "qa_action" not in st.session_state: 
        st.session_state.qa_action = None

    # ... (الأزرار الجانبية كما هي في الكود الأصلي) ...

    # ==========================================
    # 🔍 الفلاتر الخاصة بالعروض (بدون فلاتر المنتجات)
    # ==========================================
    st.markdown("### 🔍 أدوات التصفية والبحث المتقدمة")
    
    col_search, col_status = st.columns([2, 1])
    with col_search:
        search_offer = st.text_input("🔎 ابحث باسم العرض أو بالمعرف:", key="filter_search_input")
    with col_status:
        status_filter = st.selectbox("📌 حالة العرض:", ["الكل", "نشط", "غير نشط"], key="filter_status_select")
    
    col_date1, col_date2 = st.columns(2)
    with col_date1:
        filter_date = st.date_input("📅 تاريخ الانتهاء:", value=None, key="filter_date_input")
    with col_date2:
        filter_overlap = st.checkbox("🔄 فحص التداخل (منتجات مكررة)", key="f_overlap")

    now_ksa = datetime.now() + timedelta(hours=3)
    
    # تحليل التداخل
    overlapping_offer_ids = set()
    if filter_overlap:
        with st.spinner("🔄 جاري تحليل تداخل المنتجات..."):
            product_offer_map = {}
            for o in raw_offers:
                o_id = o.get('id')
                if o.get('status') != 'active': 
                    continue
                full_res = safe_api_request("GET", f"{SALLA_API_URL}/{o_id}", headers)
                if full_res and full_res.get('data'):
                    p_ids = set()
                    for p in full_res['data'].get('buy', {}).get('products', []): 
                        p_ids.add(str(p.get('id', p) if isinstance(p, dict) else p))
                    for p in full_res['data'].get('get', {}).get('products', []): 
                        p_ids.add(str(p.get('id', p) if isinstance(p, dict) else p))
                    for pid in p_ids:
                        if pid not in product_offer_map: 
                            product_offer_map[pid] = []
                        product_offer_map[pid].append(o_id)
            for pid, o_ids in product_offer_map.items():
                if len(o_ids) > 1: 
                    overlapping_offer_ids.update(o_ids)
            if not overlapping_offer_ids: 
                st.success("✅ لا يوجد تداخل في منتجات العروض النشطة.")
            else: 
                st.warning(f"⚠️ تم العثور على {len(overlapping_offer_ids)} عرض متداخل.")

    # تصفية العروض
    filtered_offers = []
    for offer in raw_offers:
        offer_id = offer.get('id', 'N/A')
        offer_name = offer.get('name', 'عرض بدون اسم')
        status = offer.get('status', 'inactive')
        start_date = safe_parse_date(offer.get('start_date'))
        exp_date = safe_parse_date(offer.get('expiry_date'))
        
        # بحث بالاسم
        if search_offer:
            if search_offer.lower() not in offer_name.lower() and search_offer not in str(offer_id): 
                continue
        
        # فلتر الحالة
        if status_filter == "نشط" and status != "active": 
            continue
        if status_filter == "غير نشط" and status == "active": 
            continue
        
        # فلتر التاريخ
        if filter_date and (not exp_date or exp_date.date() != filter_date): 
            continue
        
        # فلتر التداخل
        if filter_overlap and offer_id not in overlapping_offer_ids: 
            continue
        
        filtered_offers.append(offer)
    
    st.session_state["filtered_offers"] = filtered_offers
    
    # زر تحميل الملفات المفلترة
    if filtered_offers and len(filtered_offers) < len(raw_offers):
        st.download_button(
            "📥 تحميل العروض المفلترة", 
            data=export_offers_to_excel(filtered_offers), 
            file_name=f"filtered_offers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", 
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
            key="download_filtered_offers", 
            type="primary", 
            use_container_width=True
        )
    
    st.markdown(f"<div style='background: #f0f4f8; padding: 8px 16px; border-radius: 8px; margin-bottom: 14px; border-right: 4px solid #00b4d8;'><strong>📊 عدد العروض المطابقة للبحث: {len(filtered_offers)} عرض</strong></div>", unsafe_allow_html=True)

    # ==========================================
    # 📄 عرض بطاقات العروض مع ترقيم الصفحات
    # ==========================================
    
    # ✅ ترقيم الصفحات
    items_per_page = 10
    total_pages = max(1, (len(filtered_offers) + items_per_page - 1) // items_per_page)
    
    if "offers_page" not in st.session_state:
        st.session_state["offers_page"] = 1
    
    if st.session_state["offers_page"] > total_pages:
        st.session_state["offers_page"] = total_pages
    
    start_idx = (st.session_state["offers_page"] - 1) * items_per_page
    end_idx = start_idx + items_per_page
    displayed_offers = filtered_offers[start_idx:end_idx]
    
    # ✅ أزرار التنقل (في الأعلى والأسفل)
    def render_pagination():
        col_prev, col_page, col_next = st.columns([1, 2, 1])
        with col_prev:
            if st.button("⬅️ السابق", disabled=st.session_state["offers_page"] == 1, use_container_width=True):
                st.session_state["offers_page"] -= 1
                st.rerun()
        with col_page:
            st.markdown(f"<h4 style='text-align:center;'>📄 صفحة {st.session_state['offers_page']} من {total_pages}</h4>", unsafe_allow_html=True)
        with col_next:
            if st.button("التالي ➡️", disabled=st.session_state["offers_page"] == total_pages, use_container_width=True):
                st.session_state["offers_page"] += 1
                st.rerun()
    
    st.markdown("---")
    render_pagination()
    st.markdown("---")
    
    # ✅ عرض العروض
    inv_type_map = {"product": "منتجات", "category": "تصنيفات", "brand": "ماركات"}
    type_options_ar = ["منتجات", "تصنيفات", "ماركات"]
    type_map = {"منتجات": "product", "تصنيفات": "category", "ماركات": "brand"}
    
    def get_promo_badge(pid):
        for pr in st.session_state.get("all_products", []):
            if str(pr.get('id')) == str(pid):
                promo_obj = pr.get('promotion')
                promo_title = pr.get('promotion_title', "")
                if isinstance(promo_obj, dict):
                    promo_title = promo_obj.get('title', promo_title)
                if promo_title:
                    return f"<span style='color:#b45309; font-size:11px; background:#fef3c7; padding:2px 6px; border-radius:4px; margin-right:4px;'>🔖 {promo_title}</span>"
        return ""
    
    for idx, offer in enumerate(displayed_offers):
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
        if start_date and start_date > now_ksa: exp_badge = "⏳ لم يبدأ بعد"
        elif exp_date and exp_date < now_ksa: exp_badge = "⚠️ منتهي الصلاحية"
        else: exp_badge = "⏳ ساري الصلاحية"
        
        st.markdown(f"""
            <div style="background: linear-gradient(135deg, #0f1c2e 0%, #1a365d 100%); padding: 14px 20px; border-radius: 12px 12px 0px 0px; margin-top: 25px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; border-bottom: 3px solid #00b4d8;">
                <span style="color: #ffffff; font-weight: bold; font-size: 16px;">🎯 {offer_name} (ID: {offer_id})</span>
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                    <span style="background: rgba(255,255,255,0.2); color: #fff; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;">{badge}</span>
                    <span style="background: rgba(255,193,7,0.25); color: #ffca28; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;">{exp_badge}</span>
                    <span style="background: rgba(0,235,207,0.2); color: #00EBCF; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600; cursor: pointer;" onclick="window.location.reload();">🔄 تحديث</span>
                </div>
            </div>
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
                b_type_raw = buy_obj.get("type", "product")
                if isinstance(b_type_raw, dict): b_type_raw = b_type_raw.get("id", "product")
                st.markdown(f"<div style='margin-bottom:8px; font-size:13px; color:#64748b;'>مطبق على: <b>{inv_type_map.get(b_type_raw, 'منتجات')}</b></div>", unsafe_allow_html=True)
                
                buy_html = "<div style='background:#f8fafc; padding:12px; border-radius:8px; border:1px solid #e2e8f0; max-height: 180px; overflow-y: auto;'><ul style='margin:0; padding-right:15px; font-size:13px; line-height:1.6;'>"
                has_items = False
                for p in buy_obj.get('products', []):
                    p_id = p.get('id', p) if isinstance(p, dict) else p
                    p_name = p.get('name', 'بدون اسم') if isinstance(p, dict) else 'منتج'
                    p_sku = p.get('sku', 'لا يوجد') if isinstance(p, dict) else 'لا يوجد'
                    promo_badge = get_promo_badge(p_id) # جلب الشارة
                    buy_html += f"<li style='margin-bottom:8px;'>📦 <b>{p_name}</b><br><span style='color:#64748b; font-size:11px; background:#e2e8f0; padding:2px 6px; border-radius:4px;'>SKU: {p_sku}</span> <span style='color:#64748b; font-size:11px; background:#e2e8f0; padding:2px 6px; border-radius:4px;'>ID: {p_id}</span> {promo_badge}</li>"
                    has_items = True
                for c in buy_obj.get('categories', []):
                    c_id = c.get('id', c) if isinstance(c, dict) else c
                    c_name = c.get('name', 'بدون اسم') if isinstance(c, dict) else 'تصنيف'
                    buy_html += f"<li style='margin-bottom:8px;'>📁 <b>{c_name}</b><br><span style='color:#64748b; font-size:11px; background:#e2e8f0; padding:2px 6px; border-radius:4px;'>ID: {c_id}</span></li>"
                    has_items = True
                for b in buy_obj.get('brands', []):
                    b_id = b.get('id', b) if isinstance(b, dict) else b
                    b_name = b.get('name', 'بدون اسم') if isinstance(b, dict) else 'ماركة'
                    buy_html += f"<li style='margin-bottom:8px;'>🏢 <b>{b_name}</b><br><span style='color:#64748b; font-size:11px; background:#e2e8f0; padding:2px 6px; border-radius:4px;'>ID: {b_id}</span></li>"
                    has_items = True
                buy_html += "</ul></div>"
                if has_items: st.markdown(buy_html, unsafe_allow_html=True)
                else: st.info("جميع الأصناف المشمولة")
                st.caption(f"الكمية المطلوبة: {buy_obj.get('quantity', 1)} قطعة")
                
            with col_y:
                st.markdown("<b style='color:#0f1c2e;'>🎁 مجموعة المنح والهدية (Y) - [يحصل على]:</b>", unsafe_allow_html=True)
                get_obj = offer_data.get('get', {})               
                g_type_raw = get_obj.get("type", "product")
                if isinstance(g_type_raw, dict): g_type_raw = g_type_raw.get("id", "product")
                st.markdown(f"<div style='margin-bottom:8px; font-size:13px; color:#64748b;'>مطبق على: <b>{inv_type_map.get(g_type_raw, 'منتجات')}</b></div>", unsafe_allow_html=True)
                
                get_html = "<div style='background:#f0fdf4; padding:12px; border-radius:8px; border:1px solid #bbf7d0; max-height: 180px; overflow-y: auto;'><ul style='margin:0; padding-right:15px; font-size:13px; line-height:1.6;'>"
                has_items_y = False
                for p in get_obj.get('products', []):
                    p_id = p.get('id', p) if isinstance(p, dict) else p
                    p_name = p.get('name', 'بدون اسم') if isinstance(p, dict) else 'منتج'
                    p_sku = p.get('sku', 'لا يوجد') if isinstance(p, dict) else 'لا يوجد'
                    promo_badge = get_promo_badge(p_id) # جلب الشارة
                    get_html += f"<li style='margin-bottom:8px;'>📦 <b>{p_name}</b><br><span style='color:#166534; font-size:11px; background:#dcfce7; padding:2px 6px; border-radius:4px;'>SKU: {p_sku}</span> <span style='color:#166534; font-size:11px; background:#dcfce7; padding:2px 6px; border-radius:4px;'>ID: {p_id}</span> {promo_badge}</li>"
                    has_items_y = True
                for c in get_obj.get('categories', []):
                    c_id = c.get('id', c) if isinstance(c, dict) else c
                    c_name = c.get('name', 'بدون اسم') if isinstance(c, dict) else 'تصنيف'
                    get_html += f"<li style='margin-bottom:8px;'>📁 <b>{c_name}</b><br><span style='color:#166534; font-size:11px; background:#dcfce7; padding:2px 6px; border-radius:4px;'>ID: {c_id}</span></li>"
                    has_items_y = True
                for b in get_obj.get('brands', []):
                    b_id = b.get('id', b) if isinstance(b, dict) else b
                    b_name = b.get('name', 'بدون اسم') if isinstance(b, dict) else 'ماركة'
                    get_html += f"<li style='margin-bottom:8px;'>🏢 <b>{b_name}</b><br><span style='color:#166534; font-size:11px; background:#dcfce7; padding:2px 6px; border-radius:4px;'>ID: {b_id}</span></li>"
                    has_items_y = True
                get_html += "</ul></div>"
                if has_items_y: st.markdown(get_html, unsafe_allow_html=True)
                else: st.success("جميع الأصناف المشمولة")
                st.caption(f"كمية المنح/الخصم: {get_obj.get('quantity', 1)} قطعة")
                if get_obj.get('discount_amount'): st.markdown(f"🔥 **قيمة/نسبة الخصم :** `{get_obj.get('discount_amount')}`")

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
                ed_name = st.text_input("إسم العرض:", value=offer_name, key=f"ed_n_{offer_id}_{idx}")
                ed_msg = st.text_input("رسالة العرض:", value=offer_data.get('message', ''), key=f"ed_m_{offer_id}_{idx}")
                
                ec1, ec2, ec3 = st.columns(3)
                with ec1:
                    current_type_idx = list(OFFER_TYPES_MAP.keys()).index(o_type_raw) if o_type_raw in OFFER_TYPES_MAP else 0
                    ed_type_ar = st.selectbox("نوع العرض:", list(OFFER_TYPES_MAP.values()), index=current_type_idx, key=f"ed_t_ar_{offer_id}_{idx}")
                    ed_applied_ar = st.selectbox("تطبيق العرض على:", list(APPLIED_TO_MAP.values()), index=list(APPLIED_TO_MAP.keys()).index(o_applied_raw) if o_applied_raw in APPLIED_TO_MAP else 0, key=f"ed_app_ar_{offer_id}_{idx}")
                with ec2:
                    current_chan_idx = list(CHANNELS_MAP.keys()).index(o_channel_raw) if o_channel_raw in CHANNELS_MAP else 0
                    ed_chan_ar = st.selectbox("منصة النشر:", list(CHANNELS_MAP.values()), index=current_chan_idx, key=f"ed_ch_ar_{offer_id}_{idx}")
                    ed_status = st.selectbox("حالة العرض:", ["active", "inactive"], index=0 if status == "active" else 1, format_func=lambda x: "مفعل" if x == "active" else "مسودة", key=f"ed_status_field_{offer_id}_{idx}")
                with ec3:
                    ed_coupon = st.selectbox("تطبيق مع كوبون؟", ["لا", "نعم"], index=1 if offer_data.get('applied_with_coupon') else 0, key=f"ed_c_{offer_id}_{idx}")

                selected_ed_type_key = [k for k, v in OFFER_TYPES_MAP.items() if v == ed_type_ar][0]
                selected_ed_chan_key = [k for k, v in CHANNELS_MAP.items() if v == ed_chan_ar][0]
                selected_ed_app_key = [k for k, v in APPLIED_TO_MAP.items() if v == ed_applied_ar][0]
                ed_cust_groups = st.text_input("مجموعة العملاء (IDs):", value=",".join([str(g.get('id', g)) if isinstance(g, dict) else str(g) for g in offer_data.get('customer_groups', [])]), key=f"ed_cg_{offer_id}_{idx}")

                ecc1, ecc2, ecc3 = st.columns(3)
                with ecc1: ed_max_discount = st.number_input("أقصى خصم (SAR):", min_value=0.0, value=safe_float(offer_data.get('max_discount_amount', 0.0)), key=f"ed_max_d_{offer_id}_{idx}")
                with ecc2: ed_min_purchase = st.number_input("أدنى شراء (SAR):", min_value=0.0, value=safe_float(offer_data.get('min_purchase_amount', 0.0)), key=f"ed_min_p_{offer_id}_{idx}")
                with ecc3: ed_min_items = st.number_input("أدنى كمية:", min_value=0, value=int(safe_float(offer_data.get('min_items_count', 0.0))), key=f"ed_min_i_{offer_id}_{idx}")

                if selected_ed_type_key == "buy_x_get_y":
                    eq1, eq2 = st.columns(2)
                    with eq1:
                        ed_buy_type_ar = st.selectbox("نوع شراء X:", type_options_ar, index=type_options_ar.index(inv_type_map.get(b_type_raw, "منتجات")), key=f"ed_bt_{offer_id}_{idx}")
                        ed_buy_type = type_map[ed_buy_type_ar]
                        ed_buy_qty = st.number_input("كمية الشراء (X):", min_value=1, value=int(buy_obj.get('quantity', 1)), key=f"ed_bq_{offer_id}_{idx}")
                        existing_buy_ids = [i.get('id', i) if isinstance(i, dict) else i for i in buy_obj.get({'product':'products','category':'categories','brand':'brands'}.get(ed_buy_type), [])]
                        ed_buy_selected_ids = render_dynamic_selection(f"تعديل {ed_buy_type_ar} الشراء (X):", ed_buy_type, existing_buy_ids, f"ed_buy_X_{offer_id}_{idx}")
                    
                    with eq2:
                        ed_get_type_ar = st.selectbox("نوع عرض Y:", type_options_ar, index=type_options_ar.index(inv_type_map.get(g_type_raw, "منتجات")), key=f"ed_gt_{offer_id}_{idx}")
                        ed_get_type = type_map[ed_get_type_ar]
                        ed_get_qty = st.number_input("كمية العرض (Y):", min_value=1, value=int(get_obj.get('quantity', 1)), key=f"ed_gq_{offer_id}_{idx}")
                        existing_get_ids = [i.get('id', i) if isinstance(i, dict) else i for i in get_obj.get({'product':'products','category':'categories','brand':'brands'}.get(ed_get_type), [])]
                        ed_get_selected_ids = render_dynamic_selection(f"تعديل {ed_get_type_ar} الممنوحة (Y):", ed_get_type, existing_get_ids, f"ed_get_Y_{offer_id}_{idx}")
                    
                    ed_discount_type_ar = st.selectbox("نوع الخصم Y:", ["منتج مجاني", "خصم بنسبة"], index=1 if get_obj.get('discount_type', 'free-product') == 'percentage' else 0, key=f"ed_dt_ar_{offer_id}_{idx}")
                    if ed_discount_type_ar == "خصم بنسبة":
                        ed_disc_amt = st.number_input("نسبة الخصم Y (%):", min_value=1.0, max_value=100.0, value=safe_float(get_obj.get('discount_amount', 50.0)), key=f"ed_da_{offer_id}_{idx}")
                        ed_disc_type = "percentage"
                    else:
                        ed_disc_amt = 0.0; ed_disc_type = "free-product"
                else:
                    eq1, eq2 = st.columns(2)
                    with eq1:
                        ed_disc_amt = st.number_input("قيمة/نسبة الخصم:", min_value=0.0, value=safe_float(get_obj.get('discount_amount', 10.0)), key=f"ed_da_direct_{offer_id}_{idx}")
                        ed_buy_type_ar = st.selectbox("النوع:", type_options_ar, index=type_options_ar.index(inv_type_map.get(b_type_raw, "منتجات")), key=f"ed_bt_direct_{offer_id}_{idx}")
                        ed_buy_type = type_map[ed_buy_type_ar]
                        existing_buy_ids = [i.get('id', i) if isinstance(i, dict) else i for i in buy_obj.get({'product':'products','category':'categories','brand':'brands'}.get(ed_buy_type), [])]
                        ed_buy_selected_ids = render_dynamic_selection(f"العناصر:", ed_buy_type, existing_buy_ids, f"ed_buy_direct_{offer_id}_{idx}")
                    with eq2: st.caption("مباشر على الخيارات دون اشتراط هدايا")
                    ed_buy_qty = 1; ed_get_type = "product"; ed_get_qty = 1; ed_get_selected_ids = []; ed_disc_type = "percentage" if selected_ed_type_key == "percentage" else "fixed_amount"

                col_ed_start_date, col_ed_start_time = st.columns(2)
                with col_ed_start_date: ed_start_date_val = st.date_input("بدء - تاريخ:", value=safe_parse_date(offer_data.get('start_date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))).date() if safe_parse_date(offer_data.get('start_date')) else datetime.now().date(), key=f"ed_s_date_{offer_id}_{idx}")
                with col_ed_start_time: ed_start_time_val = st.time_input("بدء - وقت:", value=safe_parse_date(offer_data.get('start_date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))).time() if safe_parse_date(offer_data.get('start_date')) else datetime.now().time(), key=f"ed_start_time_{offer_id}_{idx}", step=60)
                ed_start = datetime.combine(ed_start_date_val, ed_start_time_val).strftime('%Y-%m-%d %H:%M:%S')
                
                col_ed_end_date, col_ed_end_time = st.columns(2)
                with col_ed_end_date: ed_end_date_val = st.date_input("انتهاء - تاريخ:", value=safe_parse_date(offer_data.get('expiry_date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))).date() if safe_parse_date(offer_data.get('expiry_date')) else (datetime.now() + timedelta(days=30)).date(), key=f"ed_e_date_{offer_id}_{idx}")
                with col_ed_end_time: ed_end_time_val = st.time_input("انتهاء - وقت:", value=safe_parse_date(offer_data.get('expiry_date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))).time() if safe_parse_date(offer_data.get('expiry_date')) else datetime.now().time().replace(hour=23, minute=59, second=59), key=f"ed_end_time_{offer_id}_{idx}", step=60)
                ed_end = datetime.combine(ed_end_date_val, ed_end_time_val).strftime('%Y-%m-%d %H:%M:%S')
                
                if st.button("💾 اعتماد وحفظ التحديث", key=f"sv_of_{offer_id}_{idx}", type="primary", use_container_width=True):
                    try:
                        cg_p_list = [int(g.strip()) for g in ed_cust_groups.split(",") if g.strip().isdigit()] if ed_cust_groups.strip() else []
                        update_payload = {
                            "name": ed_name, "message": ed_msg, "start_date": ed_start, "expiry_date": ed_end,
                            "status": ed_status, "offer_type": selected_ed_type_key, "applied_channel": selected_ed_chan_key, "applied_to": selected_ed_app_key,
                            "applied_with_coupon": ed_coupon == "نعم", "max_discount_amount": float(ed_max_discount), "min_purchase_amount": float(ed_min_purchase), "min_items_count": int(ed_min_items),
                            "customer_groups": cg_p_list, "buy": {"type": ed_buy_type, "quantity": int(ed_buy_qty)}, "get": {"type": ed_get_type, "quantity": int(ed_get_qty), "discount_type": ed_disc_type}
                        }
                        buy_cat = {'product':'products', 'category':'categories', 'brand':'brands'}[ed_buy_type]
                        if ed_buy_selected_ids: update_payload["buy"][buy_cat] = ed_buy_selected_ids
                        if selected_ed_type_key == "buy_x_get_y":
                            get_cat = {'product':'products', 'category':'categories', 'brand':'brands'}[ed_get_type]
                            if ed_get_selected_ids: update_payload["get"][get_cat] = ed_get_selected_ids
                        if ed_disc_amt > 0: update_payload["get"]["discount_amount"] = float(ed_disc_amt)
                        if safe_api_request("PUT", f"{SALLA_API_URL}/{offer_id}", headers, json=update_payload):
                            st.success("تم التحديث!")
                            st.rerun()
                    except Exception as e: st.error(f"خطأ: {str(e)}")
            st.markdown("</div>", unsafe_allow_html=True)
    
    # ✅ ترقيم الصفحات في الأسفل
    st.markdown("---")
    render_pagination()
    st.markdown("---")
