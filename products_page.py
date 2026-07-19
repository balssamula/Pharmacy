import streamlit as st
import pandas as pd
import requests
import io
from datetime import datetime
from typing import Dict, List, Any

# ✅ استيراد الدوال الخدمية
from utils import (
    get_headers, safe_api_request, get_flat_price, update_product_status, 
    export_products_to_excel, attach_product_image_api, update_product_promotions_secure,
    update_product_tax_secure, get_branches_list, generate_quantities_template, 
    process_quantities_import, fill_salla_template, generate_salla_new_products_file, 
    delete_product, update_product_price, update_product_sale_price, 
    remove_product_from_group, add_product_to_group, get_product_details, get_group_products,
    update_group_product_quantity
)

TAX_EXEMPTION_CAUSES = [
    "الخدمات المالية", "عقد تأمين على الحياة", "التوريدات العقارية المعفاة", 
    "صادرات السلع من المملكة", "صادرات الخدمات من المملكة", "النقل الدولي للسلع", 
    "النقل الدولي للركاب", "توريد وسائل النقل", "الأدوية والمعدات الطبية"
]

# ==========================================
# 🌐 دوال المزامنة والتهيئة
# ==========================================

def initialize_session():
    """تهيئة متغيرات الجلسة المشتركة"""
    defaults = {
        "all_products": [], "all_categories": [], "all_brands": [],
        "all_products_fetched": False, "prod_page": 1, "branches": [],
        "last_sync_time": None, "qa_action_prod": None
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val
            
    if "product_offers_map" not in st.session_state:
        st.session_state["product_offers_map"] = {}

def ensure_product_offers_mapping(headers: Dict[str, str]):
    """كشاف ديناميكي: يقوم بإنشاء خريطة العروض لظهور الشارات فوراً (يدعم كل أنواع سلة)"""
    # سيتم التشغيل إذا كانت الخريطة فارغة ويوجد عروض
    if not st.session_state.get("product_offers_map") and st.session_state.get("all_offers"):
        with st.spinner("🔄 جاري بناء روابط المنتجات بالعروض الخاصة لظهور الشارات..."):
            po_map = {"ALL_PRODUCTS": []}
            for o in st.session_state["all_offers"]:
                if o.get("status") != "active": 
                    continue
                oid = str(o.get("id"))
                full_o = safe_api_request("GET", f"https://api.salla.dev/admin/v2/specialoffers/{oid}", headers)
                if full_o and full_o.get("data"):
                    data = full_o["data"]
                    offer_summary = {"id": oid, "name": data.get("name")}
                    
                    applied_to = data.get("applied_to")
                    offer_type = data.get("offer_type")
                    
                    # ✅ 1. الإصلاح الجذري: العروض التي تُطبق على جميع المنتجات أو السلة كاملة
                    if applied_to in ["order", "all"] or offer_type in ["cart_offer", "tiered_offer"]:
                        po_map["ALL_PRODUCTS"].append(offer_summary)
                    
                    # ✅ 2. العروض المطبقة على منتجات محددة
                    else:
                        pids = set()
                        for px in data.get("buy", {}).get("products", []):
                            pid = str(px.get("id", px) if isinstance(px, dict) else px)
                            if pid.isdigit(): pids.add(pid)
                        for px in data.get("get", {}).get("products", []):
                            pid = str(px.get("id", px) if isinstance(px, dict) else px)
                            if pid.isdigit(): pids.add(pid)
                        for px in data.get("products", []):
                            pid = str(px.get("id", px) if isinstance(px, dict) else px)
                            if pid.isdigit(): pids.add(pid)
                            
                        for pid in pids:
                            if pid not in po_map: po_map[pid] = []
                            po_map[pid].append(offer_summary)
            
            st.session_state["product_offers_map"] = po_map
            st.rerun()

# ==========================================
# 🎨 رسم بطاقات المنتجات
# ==========================================

def render_product_card(idx: int, p: Dict, headers: Dict[str, str]):
    try:
        p_id = str(p.get('id', '')).strip()
        p_name = p.get('name', 'بدون اسم')
        p_sku = p.get('sku', 'لا يوجد')
        status = p.get('status', 'sale')
        p_url = p.get('url', '#')
        p_image = p.get('thumbnail') or p.get('main_image')
        product_type = p.get('type', 'product')
        branches = st.session_state.get("branches", [])
        
        promo = p.get('promotion', {})
        p_promotion = p.get('promotion_title') or (promo.get('title') if isinstance(promo, dict) else '') or "-"
        p_sub_title = (p.get('promotion_subtitle') or (promo.get('sub_title') if isinstance(promo, dict) else '')) or "-"
        
        price_val = get_flat_price(p.get('price', 0))
        reg_val = get_flat_price(p.get('regular_price', 0))
        sale_val = get_flat_price(p.get('sale_price', 0))
        base_price = reg_val if reg_val > 0 else price_val
        has_disc = (sale_val > 0 and sale_val < base_price) or (price_val < reg_val and price_val > 0)
        display_sale_price = sale_val if (sale_val > 0 and sale_val < base_price) else (price_val if has_disc else base_price)
        discount_pct = int(((base_price - display_sale_price) / base_price) * 100) if has_disc and base_price > 0 else 0
        
        sale_start_date = p.get('sale_start') or "غير محدد"
        sale_end_date = p.get('sale_end') or "غير محدد"
        
        disp_status = "🟢 معروض بالمتجر" if status == "sale" else "🔴 مخفي في المسودات"
        tax_status = "📗 خاضع للضريبة" if p.get('with_tax', True) else f"⚪ معفى ({p.get('tax_exemption_cause', '')})"

        type_badge = "<span style='background: linear-gradient(135deg, #6C2BD9 0%, #9B59B6 100%); color: white; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;'>📦 مجموعة منتجات</span>" if product_type == 'group_products' else ""
        border_color = "#9B59B6" if product_type == 'group_products' else "#e67e22"

        # ✅ استخراج شارة التمييز (مشمول في العروض) بأعلى دقة
        po_map = st.session_state.get("product_offers_map", {})
        p_offers_raw = po_map.get(p_id, []) + po_map.get("ALL_PRODUCTS", [])
        unique_offers = {off['id']: off for off in p_offers_raw}.values()
        p_offers = list(unique_offers)
        
        offer_badge = f"<span style='background: linear-gradient(135deg, #F7971E 0%, #FFD200 100%); color: #1a1a2e; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: 700; border: 1px solid #FFD700; box-shadow: 0 2px 8px rgba(255, 215, 0, 0.4);'>🎁 مشمول في ({len(p_offers)}) عروض</span>" if p_offers else ""

        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #243b55 0%, #141e30 100%); padding: 14px 20px; border-radius: 12px 12px 0px 0px; margin-top: 25px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; border-bottom: 3px solid {border_color};'>
            <span style='color: #ffffff; font-weight: bold; font-size: 15px;'>📦 {p_name}</span>
            <div style='display: flex; gap: 8px; flex-wrap: wrap; align-items: center;'>
                <span style='background: rgba(255,255,255,0.2); color: #fff; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;'>{disp_status}</span>
                <span style='background: rgba(0, 235, 207, 0.2); color: #00EBCF; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;'>{tax_status}</span>
                {type_badge}
                {offer_badge}
            </div>
        </div>
        """, unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown("""<div style="background-color: #fafbfc; padding: 20px; border-radius: 0px 0px 12px 12px; border: 1px solid #e1e8ed; border-top: none; margin-bottom: 20px;">""", unsafe_allow_html=True)
            c_img, c_info, c_prc, c_act = st.columns([1.5, 2.5, 2.5, 2])
            
            with c_img:
                if p_image: st.image(p_image, use_container_width=True)
                else: st.markdown("<div style='text-align:center; padding:30px; background:#eee; border-radius:8px;'>🚫 بدون صورة</div>", unsafe_allow_html=True)
                
                with st.popover("🖼️ تحديث الصورة"):
                    img_url_input = st.text_input("أدخل الرابط المباشر:", key=f"img_url_{p_id}_{idx}")
                    if img_url_input and st.button("🚀 ربط الصورة", key=f"btn_link_{p_id}_{idx}", type="primary"):
                        if attach_product_image_api(p_id, image_url=img_url_input): st.rerun()
            with c_info:
                st.markdown(f"🆔 **المعرف:** `{p_id}` | 🔢 **SKU:** `{p_sku}`")
                st.markdown(f"📢 **ترويجي:** <span style='color:#e67e22; font-weight:bold;'>{p_promotion}</span>", unsafe_allow_html=True)
                st.markdown(f"🏷️ **فرعي:** `{p_sub_title}`")
                st.markdown(f"📦 **المخزون الإجمالي:** `{p.get('quantity', 0)}` | 📈 **المبيعات:** `{p.get('sold_quantity', 0)}`")
                st.markdown(f"🔗 [🌐 عرض في المتجر]({p_url})")

            with c_prc:
                if has_disc:
                    st.markdown(f"""<div style="background:#fff3cd; padding:10px; border-radius:8px; border-right:5px solid #ffc107;"><span style="text-decoration: line-through; color: #7f8c8d; font-size:12px;">أصلي: {base_price:,.2f} SAR</span><br><b style="color: #c0392b; font-size:15px;">مخفض: {display_sale_price:,.2f} SAR</b><span style="background:#c0392b; color:#fff; padding:2px 5px; border-radius:4px; font-size:10px;">وفرت {discount_pct}%</span></div>""", unsafe_allow_html=True)
                else:
                    st.markdown(f"""<div style="background:#e2e8f0; padding:10px; border-radius:8px; border-right:5px solid #4a5568;"><b style="color:#2d3748; font-size:14px;">سعر ثابت: {base_price:,.2f} SAR</b></div>""", unsafe_allow_html=True)
                
                with st.expander("💰 تحديث الأسعار"):
                    np = st.number_input("أصلي (SAR):", min_value=0.0, value=float(base_price), key=f"np_{p_id}_{idx}")
                    nsp = st.number_input("مخفض (SAR) [0 للإلغاء]:", min_value=0.0, value=float(display_sale_price) if has_disc else 0.0, key=f"nsp_{p_id}_{idx}")
                    c_btn1, c_btn2 = st.columns(2)
                    with c_btn1:
                        if st.button("💾 حفظ السعر", key=f"sv_p_{p_id}_{idx}", use_container_width=True, type="primary"):
                            if update_product_price(int(p_id), np) and update_product_sale_price(int(p_id), nsp): st.rerun()

            with c_act:
                if p_offers:
                    with st.popover(f"🎁 استعراض عروض المنتج ({len(p_offers)})", use_container_width=True):
                        st.markdown("<b style='color:#b45309;'>العروض النشطة المشمول بها:</b>", unsafe_allow_html=True)
                        for off in p_offers: st.markdown(f"- 🎯 **{off['name']}** `(ID: {off['id']})`")
                
                t_st = "hidden" if status == "sale" else "sale"
                if st.button("👁️ إخفاء" if status == "sale" else "👁️ إظهار", key=f"sh_{p_id}_{idx}", type="secondary" if status == "sale" else "primary", use_container_width=True):
                    if update_product_status(p_id, t_st): st.rerun()

                with st.popover("✏️ تحديث العناوين", use_container_width=True):
                    n_pr = st.text_input("ترويجي:", value=p_promotion if p_promotion != "-" else "", key=f"npr_{p_id}_{idx}")
                    n_su = st.text_input("فرعي:", value=p_sub_title if p_sub_title != "-" else "", key=f"nsu_{p_id}_{idx}")
                    if st.button("💾 حفظ العناوين", key=f"svt_{p_id}_{idx}", type="primary", use_container_width=True):
                        if update_product_promotions_secure(int(p_id), n_pr, n_su, headers): st.rerun()
                        
            st.markdown("</div>", unsafe_allow_html=True)
            
            if product_type == 'group_products':
                st.markdown("---")
                with st.expander(f"📦 إدارة المنتجات الفرعية للمجموعة", expanded=False):
                    g_prods = []
                    if p.get('grouped_items'):
                        for item in p['grouped_items']:
                            sub_p = item.get('product', {})
                            g_prods.append({
                                'id': item.get('product_id') or sub_p.get('id'),
                                'name': sub_p.get('name', 'منتج فرعي'),
                                'sku': sub_p.get('sku', ''),
                                'bundle_quantity': item.get('quantity', 1)
                            })
                    
                    if g_prods:
                        for gp_idx, gp in enumerate(g_prods):
                            st.markdown(f"<div style='background: #f8f9fa; border-radius: 10px; padding: 15px; margin-bottom: 12px; border-left: 4px solid #6C2BD9;'><div style='display: flex; gap: 15px;'><div style='flex: 1;'><b>{gp.get('name')}</b><br><span style='font-size: 12px; color: #666;'>🆔 {gp.get('id')} | 🔢 {gp.get('sku')}</span></div></div></div>", unsafe_allow_html=True)
                            
                            c_q, c_act2 = st.columns(2)
                            with c_q:
                                new_q = st.number_input("تعديل الحبات بالرقم", min_value=1, value=int(gp.get('bundle_quantity', 1)), key=f"gq_{gp.get('id')}_{idx}_{gp_idx}", label_visibility="collapsed")
                                if st.button("💾 حفظ الحبات", key=f"gqs_{gp.get('id')}_{idx}_{gp_idx}"):
                                    if update_group_product_quantity(int(p_id), int(gp.get('id')), new_q): st.rerun()
                            with c_act2:
                                if st.button("🗑️ إزالة من المجموعة", key=f"gqr_{gp.get('id')}_{idx}_{gp_idx}"):
                                    if remove_product_from_group(int(p_id), int(gp.get('id'))): st.rerun()
                            st.markdown("<hr style='margin:10px 0; border:0; border-bottom:1px dashed #ddd;'>", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"❌ خطأ أثناء عرض بطاقة المنتج (ID: {p.get('id')}): {str(e)}")

# ==========================================
# 🚀 הדالة الرئيسية لصفحة المنتجات
# ==========================================
def render_products_page():
    initialize_session()
    headers = get_headers()
    if not headers: return
    
    # ✅ استدعاء بناء الروابط (إذا كانت الخريطة فارغة) لضمان الشارات
    ensure_product_offers_mapping(headers)
    
    st.markdown("""
    <div style="background: linear-gradient(135deg, #0F1C2E 0%, #00EBCF 100%); padding: 15px 25px; border-radius: 12px; color: white; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        <h2 style="color: white; margin: 0;">📦 مركز إدارة المنتجات الذكي والمتقدم</h2>
    </div>
    """, unsafe_allow_html=True)

    # 🌟 CSS اللوحة الجانبية المنزلقة لصفحة المنتجات
    st.markdown("""
    <style>
        div[data-testid="stElementContainer"]:has(span[id^="qa-marker-"]) { display: none !important; margin: 0 !important; padding: 0 !important; }
        div[data-testid="stElementContainer"]:has(span[id^="qa-marker-"]) + div[data-testid="stElementContainer"] {
            position: fixed !important; right: -240px !important; width: 280px !important; background: linear-gradient(135deg, #1E293B 0%, #0F1C2E 100%) !important;
            padding: 5px 10px !important; border-radius: 20px 0 0 20px !important; border: 2px solid #00EBCF !important; border-right: none !important;
            z-index: 999999 !important; transition: right 0.4s cubic-bezier(0.4, 0, 0.2, 1) !important; box-shadow: -4px 4px 12px rgba(0,0,0,0.3) !important;
        }
        div[data-testid="stElementContainer"]:has(span[id^="qa-marker-"]) + div[data-testid="stElementContainer"]:hover { right: 0px !important; }
        div[data-testid="stElementContainer"]:has(span[id="qa-marker-1"]) + div[data-testid="stElementContainer"] { top: 120px; }
        div[data-testid="stElementContainer"]:has(span[id="qa-marker-2"]) + div[data-testid="stElementContainer"] { top: 185px; }
        div[data-testid="stElementContainer"]:has(span[id="qa-marker-3"]) + div[data-testid="stElementContainer"] { top: 250px; }
        div[data-testid="stElementContainer"]:has(span[id^="qa-marker-"]) + div[data-testid="stElementContainer"] button {
            width: 100% !important; text-align: right !important; padding-right: 35px !important; font-size: 14px !important;
            font-weight: bold !important; background: transparent !important; border: none !important; color: white !important; box-shadow: none !important;
        }
        div[data-testid="stElementContainer"]:has(span[id^="qa-marker-"]) + div[data-testid="stElementContainer"]::before {
            content: "👈"; position: absolute; left: 10px; top: 50%; transform: translateY(-50%); font-size: 18px; pointer-events: none;
        }
    </style>
    """, unsafe_allow_html=True)

    # ------------------------------------------
    # أزرار الإجراءات الجانبية العائمة
    # ------------------------------------------
    st.markdown('<span id="qa-marker-1"></span>', unsafe_allow_html=True)
    if st.button("🏢 التحكم بالمنتجات والفروع", key="btn_qa_1"):
        st.session_state.qa_action_prod = "products_control"
        st.rerun()

    st.markdown('<span id="qa-marker-2"></span>', unsafe_allow_html=True)
    if st.button("⚙️ إعدادات ربط التطبيقات", key="btn_qa_2"):
        st.session_state.qa_action_prod = "app_settings"
        st.rerun()

    st.markdown('<span id="qa-marker-3"></span>', unsafe_allow_html=True)
    if st.button("🔄 مطابقة منتجات سلة", key="btn_qa_3"):
        st.session_state.qa_action_prod = "salla_matching"
        st.rerun()

    # لوحة تنفيذ الإجراءات
    if st.session_state.qa_action_prod:
        with st.container(border=True):
            col_t, col_c = st.columns([5, 1])
            with col_c:
                if st.button("❌ إغلاق اللوحة", use_container_width=True, type="primary"):
                    st.session_state.qa_action_prod = None
                    st.rerun()
            
            if st.session_state.qa_action_prod == "products_control":
                with col_t: st.markdown("### 🏢 التحكم بالمنتجات وكميات الفروع (Excel)")
                c_dl1, c_dl2 = st.columns(2)
                with c_dl1: st.download_button("📥 تنزيل قالب التعديل", data=fill_salla_template(st.session_state["all_products"]), file_name="Update.xlsx", use_container_width=True)
                with c_dl2: st.download_button("📥 تنزيل القالب الفارغ", data=generate_salla_new_products_file([]), file_name="New.xlsx", use_container_width=True)
            elif st.session_state.qa_action_prod == "app_settings":
                with col_t: st.markdown("### ⚙️ إعدادات ربط التطبيقات")
                st.checkbox("✅ تفعيل التوصيات في المتجر", value=True)
                if st.button("💾 حفظ", type="primary"): st.success("تم الحفظ")
            elif st.session_state.qa_action_prod == "salla_matching":
                with col_t: st.markdown("### 🔄 مطابقة المنتجات مع النظام")
                st.file_uploader("📂 رفع ملف المطابقة", type=["xlsx"])
    
    # ==========================================
    # 🔍 الفلاتر الأنيقة
    # ==========================================
    st.markdown("### 🔍 أدوات التصفية والبحث في المنتجات")
    with st.container(border=True):
        sq = st.text_input("ابحث باسم أو SKU:", placeholder="أدخل الكود للبحث...").lower()

    with st.container(border=True):
        col_f1, col_f2, col_f3, col_f4, col_f5, col_f6 = st.columns(6)
        with col_f1:
            st.markdown("<div style='text-align:center; color:#00EBCF; font-weight:bold;'>📌 الحالة</div>", unsafe_allow_html=True)
            f_status = st.radio("الحالة", ["الكل", "مخفي", "معروض"], horizontal=True, label_visibility="collapsed", key="f_status_radio")
        with col_f2:
            st.markdown("<div style='text-align:center; color:#00EBCF; font-weight:bold;'>🖼️ الصورة</div>", unsafe_allow_html=True)
            f_img = st.radio("الصورة", ["الكل", "بصورة", "بدون"], horizontal=True, label_visibility="collapsed", key="f_img_radio")
        with col_f3:
            st.markdown("<div style='text-align:center; color:#00EBCF; font-weight:bold;'>📢 العناوين</div>", unsafe_allow_html=True)
            f_promo = st.radio("العناوين", ["الكل", "لها عنوان", "بدون"], horizontal=True, label_visibility="collapsed", key="f_promo_radio")
        with col_f4:
            st.markdown("<div style='text-align:center; color:#00EBCF; font-weight:bold;'>💰 السعر</div>", unsafe_allow_html=True)
            f_disc = st.radio("السعر", ["الكل", "مخفض", "ثابت"], horizontal=True, label_visibility="collapsed", key="f_disc_radio")
        with col_f5:
            st.markdown("<div style='text-align:center; color:#00EBCF; font-weight:bold;'>📦 النوع</div>", unsafe_allow_html=True)
            f_type = st.radio("النوع", ["الكل", "عادية", "مجموعات"], horizontal=True, label_visibility="collapsed", key="f_type_radio")
        with col_f6:
            st.markdown("<div style='text-align:center; color:#00EBCF; font-weight:bold;'>🎁 العروض</div>", unsafe_allow_html=True)
            f_offer = st.radio("العروض", ["الكل", "مشمول", "غير مشمول"], horizontal=True, label_visibility="collapsed", key="f_offer_radio")

    filtered = []
    po_map = st.session_state.get("product_offers_map", {})
    all_products_offers = po_map.get("ALL_PRODUCTS", [])
    
    for p in st.session_state.get("all_products", []):
        if sq and sq not in str(p.get('name', '')).lower() and sq not in str(p.get('sku', '')).lower(): continue
        if f_status == "مخفي" and p.get('status') != 'hidden': continue
        if f_status == "معروض" and p.get('status') == 'hidden': continue
        
        has_img = bool(p.get('thumbnail') or p.get('main_image'))
        if f_img == "بصورة" and not has_img: continue
        if f_img == "بدون" and has_img: continue
            
        has_promo_text = bool(p.get('promotion_title') or (p.get('promotion', {}).get('title')))
        if f_promo == "لها عنوان" and not has_promo_text: continue
        if f_promo == "بدون" and has_promo_text: continue
        
        pr = get_flat_price(p.get('price', 0)); reg = get_flat_price(p.get('regular_price', 0)); sal = get_flat_price(p.get('sale_price', 0))
        is_discounted = (sal > 0 and sal < (reg if reg > 0 else pr))
        if f_disc == "مخفض" and not is_discounted: continue
        if f_disc == "ثابت" and is_discounted: continue
            
        is_group = (p.get('type') == 'group_products')
        if f_type == "عادية" and is_group: continue
        if f_type == "مجموعات" and not is_group: continue
        
        # ✅ فلتر العروض المطبق بدقة بناءً على الخريطة الجديدة
        p_id_str = str(p.get('id', '')).strip()
        is_in_offer = bool(po_map.get(p_id_str)) or bool(all_products_offers)
        if f_offer == "مشمول" and not is_in_offer: continue
        if f_offer == "غير مشمول" and is_in_offer: continue
            
        filtered.append(p)
        
    st.info(f"📊 النتائج: {len(filtered)} منتج مطابِق للبحث")

    # ✅ زر التنزيل للمنتجات المفلترة
    if filtered:
        col_download1, col_download2 = st.columns([2, 1])
        with col_download1:
            st.download_button(
                label="📥 تحميل المنتجات المفلترة (Excel)",
                data=export_products_to_excel(filtered),
                file_name=f"Filtered_Products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                key="download_filtered_products",
                use_container_width=True
            )
        with col_download2:
            st.info(f"📄 يحتوي الملف على {len(filtered)} منتج")

    # Pagination
    limit = 20
    pages = max(1, (len(filtered) + limit - 1) // limit)
    
    if "prod_page" not in st.session_state:
        st.session_state["prod_page"] = 1
        
    if st.session_state["prod_page"] > pages: 
        st.session_state["prod_page"] = pages
        
    start = (st.session_state["prod_page"] - 1) * limit
    
    cp, cc, cn = st.columns([1,2,1])
    with cp:
        if st.button("⬅️ السابقة", disabled=st.session_state["prod_page"]==1, use_container_width=True, key="pg_up_prev"): 
            st.session_state["prod_page"] -= 1; st.rerun()
    with cc: st.markdown(f"<h4 style='text-align:center;'>📄 صفحة {st.session_state['prod_page']} من {pages}</h4>", unsafe_allow_html=True)
    with cn:
        if st.button("التالية ➡️", disabled=st.session_state["prod_page"]==pages, use_container_width=True, key="pg_up_next"): 
            st.session_state["prod_page"] += 1; st.rerun()

    for idx, p in enumerate(filtered[start:start+limit]):
        render_product_card(start + idx, p, headers)
        
    st.markdown("---")
    cp_b, cc_b, cn_b = st.columns([1,2,1])
    with cp_b:
        if st.button("⬅️ السابقة", disabled=st.session_state["prod_page"]==1, use_container_width=True, key="pg_down_prev"): 
            st.session_state["prod_page"] -= 1; st.rerun()
    with cc_b: st.markdown(f"<h4 style='text-align:center;'>📄 صفحة {st.session_state['prod_page']} من {pages}</h4>", unsafe_allow_html=True)
    with cn_b:
        if st.button("التالية ➡️", disabled=st.session_state["prod_page"]==pages, use_container_width=True, key="pg_down_next"): 
            st.session_state["prod_page"] += 1; st.rerun()

    st.markdown("---")

    # ✅ عرض أداة التشخيص (إذا كانت مفتوحة)
    render_diagnose_section(headers)

    # ✅ CSS مخصص للفلاتر (داخل الدالة)
    st.markdown("""
    <style>
        /* تنسيق أزرار الراديو داخل الفلاتر */
        .stRadio > div {
            justify-content: center !important;
            gap: 2px !important;
        }
        .stRadio label {
            color: #cbd5e1 !important;
            font-size: 11px !important;
            padding: 2px 4px !important;
        }
        .stRadio [data-testid="stBaseButton-selected"] {
            background-color: #00EBCF !important;
            color: #0f1c2e !important;
            border-radius: 4px !important;
            font-weight: bold !important;
        }
        .stRadio [data-testid="stBaseButton"] {
            background-color: transparent !important;
            color: #94a3b8 !important;
            border: 1px solid transparent !important;
            border-radius: 4px !important;
            padding: 2px 8px !important;
        }
        .stRadio [data-testid="stBaseButton"]:hover {
            background-color: rgba(0, 235, 207, 0.1) !important;
            color: #00EBCF !important;
            border-color: rgba(0, 235, 207, 0.2) !important;
        }
    </style>
    """, unsafe_allow_html=True)

def render_diagnose_section(headers: Dict[str, str]):
    """عرض أداة تشخيص العناوين وكميات الفروع"""
    # تشخيص العناوين
    if st.session_state.get("show_diagnose", False) and st.session_state.get("diagnose_product_id"):
        product_id = st.session_state["diagnose_product_id"]
        
        with st.container(border=True):
            col_title, col_close = st.columns([5, 1])
            with col_title:
                st.markdown("### 🔍 أداة تشخيص العناوين الترويجية والفرعية")
            with col_close:
                if st.button("❌ إغلاق", use_container_width=True, type="primary"):
                    st.session_state["show_diagnose"] = False
                    st.session_state["diagnose_product_id"] = None
                    st.rerun()
            
            diagnose_product_promotions(product_id, headers)
    
    # تشخيص كميات الفروع
    if st.session_state.get("show_branch_diagnose", False) and st.session_state.get("diagnose_branch_product_id"):
        product_id = st.session_state["diagnose_branch_product_id"]
        
        with st.container(border=True):
            col_title, col_close = st.columns([5, 1])
            with col_title:
                st.markdown("### 🔍 أداة تشخيص كميات الفروع")
            with col_close:
                if st.button("❌ إغلاق التشخيص", use_container_width=True, type="primary"):
                    st.session_state["show_branch_diagnose"] = False
                    st.session_state["diagnose_branch_product_id"] = None
                    st.rerun()
            
            diagnose_branch_quantities(product_id, headers)
            
def render_settings_and_templates(headers: Dict[str, str]):
    """يعرض إعدادات الربط وتحميل القوالب والكميات"""
    col_widget1, col_widget2 = st.columns(2)
    with col_widget1:
        with st.expander("⚙️ إعدادات ربط تطبيقات التوصيات وشاهدتها مؤخراً", expanded=False):
            st.markdown("#### 🛠️ إعدادات المنتجات المستعرضة مؤخراً")
            st.text_input("📝 عنوان القسم الفعال:", value="شاهدتها مؤخراً")
            st.checkbox("الصفحة الرئيسية بالمتجر", value=False)
            st.checkbox("صفحة التصنيفات والأقسام", value=False)
            st.checkbox("صفحة تفاصيل وعرض المنتج", value=True)
            st.number_input("🔢 عدد المنتجات المعروضة:", min_value=1, max_value=32, value=6)
            st.markdown("#### 🛠️ نظام التوصية الذكي والحزم")
            st.checkbox("✅ تفعيل التوصيات في المتجر", value=True)
            st.checkbox("🤝 تشترى معًا", value=True)
            st.selectbox("🛒 عرض زر إضافة للسلة:", ["في صفحة السلة فقط", "في جميع الصفحات"], index=0)
            if st.button("💾 حفظ وتثبيت إعدادات التطبيقات", type="primary", use_container_width=True):
                st.success("✅ تم حفظ إعدادات ربط التطبيقات بنجاح!")

    with col_widget2:
        with st.expander("🏢 التحكم في المنتجات وكميات الفروع", expanded=False):
            c_dl1, c_dl2 = st.columns(2)
            with c_dl1:
                if st.button("📥 تحميل قالب تعديل المنتجات", use_container_width=True):
                    template_bytes = fill_salla_template(st.session_state["all_products"])
                    if template_bytes:
                        st.download_button("✅ تنزيل قالب التعديل", data=template_bytes, file_name="Salla_Products_Update.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            with c_dl2:
                if st.button("📥 تحميل قالب إضافة منتجات", use_container_width=True):
                    template_bytes = generate_salla_new_products_file([]) 
                    if template_bytes:
                        st.download_button("✅ تنزيل القالب الفارغ", data=template_bytes, file_name="Salla_New_Products.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            st.markdown("#### 🚀 رفع ملف المنتجات إلى سلة")
            import_type_label = st.radio("اختر نوع العملية:", ["تحديث منتجات حالية", "إضافة منتجات جديدة"], horizontal=True)
            import_type_value = "products-update" if import_type_label == "تحديث منتجات حالية" else "products"
            
            uploaded_products_file = st.file_uploader("📂 ارفع ملف الإكسيل الأصلي:", type=['xlsx'], key="upload_products_file")
            if uploaded_products_file and st.button(f"رفع الملف ({import_type_label})", type="primary", use_container_width=True):
                with st.spinner("جاري رفع الملف إلى سلة..."):
                    try:
                        files = {'file': (uploaded_products_file.name, uploaded_products_file.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
                        upload_headers = headers.copy()
                        if "Content-Type" in upload_headers: del upload_headers["Content-Type"]
                        res = requests.post("https://api.salla.dev/admin/v2/products/import", headers=upload_headers, files=files, data={'type': import_type_value})
                        if res.status_code < 400: st.success("✅ تم رفع الملف لمعالجته في الخلفية.")
                        else: st.error(f"❌ فشل الرفع: {res.text}")
                    except Exception as e: st.error(f"❌ خطأ: {e}")
            
            st.markdown("---")
            st.markdown("#### 📦 تحديث كميات الفروع (Excel)")
            st.download_button("📥 تنزيل نموذج الكميات", data=generate_quantities_template(), file_name="Salla_Quantities.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            uploaded_q_file = st.file_uploader("📂 رفع ملف لتحديث الكميات:", type=['xlsx'], key="upload_q_file")
            if uploaded_q_file and st.button("🚀 تحديث كميات الفروع (Bulk)", type="primary", use_container_width=True):
                try:
                    df_q = pd.read_excel(uploaded_q_file)
                    with st.spinner("جاري التحديث..."):
                        res_q = process_quantities_import(df_q)
                        for m in res_q["success"]: st.success(m)
                        for m in res_q["errors"]: st.error(m)   
                except Exception as e: st.error(f"❌ خطأ: {e}")

def render_matching_section(headers: Dict[str, str]):
    """قسم مطابقة ورفع المنتجات الجديدة"""
    with st.expander("🔄 مطابقة منتجات سلة مع النظام الداخلي", expanded=False):
        st.info("📋 يرجى رفع ملف المطابقة بصيغة Excel.")
        exclude_cats_str = st.text_input("🚫 تصنيفات مستبعدة (مفصولة بفاصلة):", placeholder="مثال: اكسسوارات")
        uploaded_matching = st.file_uploader("📂 رفع ملف المطابقة (XLSX):", type=["xlsx"])
        
        if uploaded_matching:
            try:
                xl = pd.ExcelFile(uploaded_matching)
                if 'salla' not in xl.sheet_names or 'system' not in xl.sheet_names:
                    st.error("❌ الشيت 'salla' أو 'system' غير موجود")
                    return
                df_salla = pd.read_excel(uploaded_matching, sheet_name='salla')
                df_system = pd.read_excel(uploaded_matching, sheet_name='system')
                
                if exclude_cats_str and len(df_system.columns) >= 5:
                    exclude_cats = [c.strip().lower() for c in exclude_cats_str.split(",") if c.strip()]
                    if exclude_cats:
                        cat_col = df_system.columns[4]
                        df_system = df_system[~df_system[cat_col].astype(str).str.lower().str.strip().isin(exclude_cats)]
                        st.success(f"تم استبعاد المنتجات في: {', '.join(exclude_cats)}")
            
                salla_ids = set()
                if df_salla.empty:
                    st.warning("شيت salla فارغ! سنعتمد على منتجات المتجر المسحوبة.")
                    for p in st.session_state["all_products"]: salla_ids.add(str(p.get("sku", ""))); salla_ids.add(str(p.get("id", "")))
                else:
                    salla_ids = set(df_salla['رقم المنتج'].astype(str).tolist())
                
                new_products = []
                for _, row in df_system.iterrows():
                    pid = str(row['رقم المنتج'])
                    if pid not in salla_ids:
                        new_products.append({'رقم المنتج': pid, 'اسم المنتج': row['اسم المنتج'], 'سعر المنتج': row['سعر المنتج'], 'خاضع للضريبة': row.get('خاضع للضريبة؟', 'نعم')})
                
                if new_products:
                    st.success(f"✅ تم العثور على {len(new_products)} منتج جديد.")
                    st.dataframe(pd.DataFrame(new_products), use_container_width=True)
                    
                    st.markdown("#### ☑️ اختر المنتجات للرفع")
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("☑️ اختيار الكل", use_container_width=True):
                            for idx in range(len(new_products)): st.session_state[f"sel_{idx}"] = True
                            st.rerun()
                    with c2:
                        if st.button("⬜ إلغاء الكل", use_container_width=True):
                            for idx in range(len(new_products)): st.session_state[f"sel_{idx}"] = False
                            st.rerun()

                    selected_indices = []
                    for idx, product in enumerate(new_products):
                        key = f"sel_{idx}"
                        if key not in st.session_state: st.session_state[key] = True
                        checked = st.checkbox(f"🆔 {product['رقم المنتج']} - {product['اسم المنتج']}", value=st.session_state[key], key=key)
                        if checked != st.session_state[key]: st.session_state[key] = checked
                        if checked: selected_indices.append(idx)
                
                    if st.button(f"🚀 رفع {len(selected_indices)} منتج لسلة", type="primary", use_container_width=True):
                        if not selected_indices: st.warning("⚠️ اختر منتجاً واحداً على الأقل")
                        else:
                            with st.spinner("🔄 جاري التجهيز والرفع..."):
                                p_for_template = []
                                for idx in selected_indices:
                                    pr = new_products[idx]
                                    is_taxable = str(pr['خاضع للضريبة']).strip().lower() in ['نعم', 'true', '1', 'yes']
                                    p_for_template.append({"name": str(pr['اسم المنتج']), "price": float(pr['سعر المنتج']) if pr['سعر المنتج'] else 0, "sku": str(pr['رقم المنتج']), "with_tax": is_taxable, "tax_exemption_cause": "" if is_taxable else "الأدوية والمعدات الطبية"})
                                
                                tb = generate_salla_new_products_file(p_for_template)
                                if tb:
                                    try:
                                        files = {'file': ('Salla_New.xlsx', tb, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
                                        uh = headers.copy()
                                        if "Content-Type" in uh: del uh["Content-Type"]
                                        res = requests.post("https://api.salla.dev/admin/v2/products/import", headers=uh, files=files, data={'type': 'products'})
                                        if res.status_code < 400: st.success("✅ تم الرفع للمعالجة في سلة.")
                                        else: st.error(f"❌ فشل الرفع: {res.text}")
                                    except Exception as e: st.error(f"❌ خطأ: {e}")
                else:
                    st.info("ℹ️ جميع المنتجات متطابقة بالفعل.")
            except Exception as e:
                st.error(f"❌ خطأ في معالجة الملف: {str(e)}")

# ==========================================
# 📦 3. نظام عرض وتحرير بطاقات المنتجات
# ==========================================

def render_group_product_section(p_id: str, p_name: str, idx: int, headers: Dict[str, str]):
    """يعرض محتويات مجموعة المنتجات مع تفاصيل الحساب"""
    st.markdown("---")
    
    with st.spinner(f"جاري تحميل منتجات المجموعة..."):
        group_products = get_group_products(int(p_id))
    
    with st.expander(f"📦 تفاصيل مجموعة المنتجات ({len(group_products)} منتج)", expanded=False):
        if not group_products:
            st.info("ℹ️ لا توجد منتجات في هذه المجموعة.")
        else:
            # ✅ عرض إجمالي كمية المجموعة
            total_qty = sum([gp.get('bundle_quantity', 1) / gp.get('stock_quantity', 0) for gp in group_products])
            st.info(f"📊 إجمالي كمية المجموعة: {total_qty} وحدة")
            
            for gp_idx, gp in enumerate(group_products):
                gp_id = str(gp.get('id', 'N/A'))
                gp_name_sub = gp.get('name', 'بدون اسم')
                gp_sku = gp.get('sku', 'لا يوجد')
                gp_price = gp.get('price', 0)
                gp_bundle_qty = gp.get('bundle_quantity', 1)
                gp_stock = gp.get('stock_quantity', 0)
                gp_image = gp.get('image')
                
                # ✅ حساب الكمية الفعلية للمجموعة من هذا المنتج
                group_qty = gp_stock / gp_bundle_qty
                
                st.markdown(f"""
                <div style='background: #f8f9fa; border-radius: 10px; padding: 15px; margin-bottom: 12px; border-right: 4px solid #6C2BD9;'>
                    <div style='display: flex; gap: 15px; align-items: center; flex-wrap: wrap;'>
                        <div style='flex: 0 0 60px;'>
                            {f"<img src='{gp_image}' style='width: 60px; height: 60px; border-radius: 8px;'>" if gp_image else "🚫"}
                        </div>
                        <div style='flex: 1; min-width: 150px;'>
                            <b>{gp_name_sub}</b><br>
                            <span style='font-size: 12px; color: #666;'>🆔 {gp_id} | 🔢 {gp_sku} | 💰 {gp_price:.2f} SAR</span>
                        </div>
                        <div style='flex: 0 0 160px; font-size: 13px;'>
                            <div>📦 حبات بالمجموعة: <b style='color:#6C2BD9;'>{gp_bundle_qty}</b></div>
                            <div>🏪 مخزون المنتج: <b>{gp_stock}</b></div>
                            <div>📊 إجمالي المجموعة: <b style='color:#2ecc71;'>{group_qty}</b></div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                c_q, c_act = st.columns(2)
                with c_q:
                    new_q = st.number_input(
                        "تعديل الحبات",
                        min_value=1,
                        value=int(gp_bundle_qty),
                        step=1,
                        key=f"gq_{gp_id}_{idx}_{gp_idx}",
                        label_visibility="collapsed"
                    )
                    if st.button(f"💾 تحديث الكمية", key=f"gqs_{gp_id}_{idx}_{gp_idx}", use_container_width=True):
                        with st.spinner("جاري تحديث الكمية..."):
                            if update_group_product_quantity(int(p_id), int(gp_id), new_q):
                                st.rerun()
                            else:
                                st.error("❌ فشل التحديث")
                
                with c_act:
                    if gp.get('url'):
                        st.markdown(f"[🔗 عرض]({gp.get('url')})")
                    if st.button(f"🗑️ إزالة", key=f"gqr_{gp_id}_{idx}_{gp_idx}", use_container_width=True):
                        with st.spinner("إزالة..."):
                            if remove_product_from_group(int(p_id), int(gp_id)):
                                st.success("✅ تم الإزالة!")
                                st.rerun()
                            else:
                                st.error("❌ فشل الإزالة")
                
                st.markdown("<hr style='margin:10px 0; border:0; border-bottom:1px dashed #ddd;'>", unsafe_allow_html=True)
        
        # ✅ إضافة منتج للمجموعة
        st.markdown("#### ➕ إضافة منتج للمجموعة")
        search_p = st.text_input("ابحث باسم أو SKU للإضافة:", key=f"gps_{p_id}_{idx}")
        if search_p:
            f_prods = [pr for pr in st.session_state.get("all_products", [])
                      if str(pr.get('id')) != p_id and
                      (search_p.lower() in str(pr.get('name', '')).lower() or
                       search_p.lower() in str(pr.get('sku', '')).lower())]
            if f_prods:
                for pr in f_prods[:5]:
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"**{pr.get('name')}** | `{pr.get('sku')}` | مخزون: {pr.get('quantity', 0)}")
                    with c2:
                        if st.button(f"➕ إضافة", key=f"gpa_{pr.get('id')}_{idx}"):
                            with st.spinner("إضافة..."):
                                if add_product_to_group(int(p_id), pr.get('id')):
                                    st.success("✅ تمت الإضافة!")
                                    st.rerun()
                                else:
                                    st.error("❌ فشل الإضافة")
            else:
                st.info("لا توجد منتجات مطابقة.")

def render_product_card(idx: int, p: Dict, headers: Dict[str, str]):
    """رسم وإدارة كارت منتج واحد بطريقة معزولة وآمنة (Clean Code)"""
    try:
        p_id = str(p.get('id', '')).strip()
        p_name = p.get('name', 'بدون اسم')
        p_sku = p.get('sku', 'لا يوجد')
        status = p.get('status', 'sale')
        p_url = p.get('url', '#')
        p_image = p.get('thumbnail') or p.get('main_image')
        product_type = p.get('type', 'product')
        branches = st.session_state.get("branches", [])
        
        promo = p.get('promotion', {})
        p_promotion = p.get('promotion_title') or (promo.get('title') if isinstance(promo, dict) else '') or "-"
        p_sub_title = (promo.get('sub_title') if isinstance(promo, dict) else '') or "-"
        
        price_val = get_flat_price(p.get('price', 0))
        reg_val = get_flat_price(p.get('regular_price', 0))
        sale_val = get_flat_price(p.get('sale_price', 0))
        base_price = reg_val if reg_val > 0 else price_val
        has_disc = (sale_val > 0 and sale_val < base_price) or (price_val < reg_val and price_val > 0)
        display_sale_price = sale_val if (sale_val > 0 and sale_val < base_price) else (price_val if has_disc else base_price)
        discount_pct = int(((base_price - display_sale_price) / base_price) * 100) if has_disc and base_price > 0 else 0
        
        sale_start_date = p.get('sale_start') or "غير محدد"
        sale_end_date = p.get('sale_end') or "غير محدد"
        
        disp_status = "🟢 معروض بالمتجر" if status == "sale" else "🔴 مخفي في المسودات"
        tax_status = "📗 خاضع للضريبة" if p.get('with_tax', True) else f"⚪ معفى ({p.get('tax_exemption_cause', '')})"

        # ✅ شارات التمييز الآمنة
        type_badge = "<span style='background: linear-gradient(135deg, #6C2BD9 0%, #9B59B6 100%); color: white; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;'>📦 مجموعة منتجات</span>" if product_type == 'group_products' else ""
        border_color = "#9B59B6" if product_type == 'group_products' else "#e67e22"

        # ✅ زر تحديث سريع للمنتج (في شريط العنوان)
        with st.popover("🔄"):
            st.markdown(f"**تحديث بيانات المنتج:** {p_name}")
            if st.button("🔄 تحديث هذا المنتج", key=f"refresh_{p_id}_{idx}", type="primary"):
                with st.spinner("جاري تحديث المنتج..."):
                    fresh_res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products/{int(p_id)}", headers)
                    if fresh_res and fresh_res.get('data'):
                        # تحديث البيانات في session_state
                        for i, prod in enumerate(st.session_state["all_products"]):
                            if str(prod.get('id')) == p_id:
                                st.session_state["all_products"][i] = fresh_res['data']
                                break
                        st.success("✅ تم تحديث المنتج!")
                        st.rerun()
                    else:
                        st.error("❌ فشل تحديث المنتج")
                        
        # ✅ استخراج العروض المربوطة بالمنتج من الذاكرة مع التحقق من وجود البيانات
        product_offers_map = st.session_state.get("product_offers_map", {})
        p_offers = product_offers_map.get(p_id, [])
        
        # ✅ عرض عدد العروض للتأكد (يمكن إزالته بعد التأكد)
        if p_offers:
            # ✅ شارة العروض
            offer_badge = f"""<span style='background: linear-gradient(135deg, #F7971E 0%, #FFD200 100%); 
                color: #1a1a2e; padding: 4px 12px; border-radius: 20px; font-size: 11px; 
                font-weight: 700; border: 2px solid #FFD700; box-shadow: 0 2px 8px rgba(255, 215, 0, 0.4);'>
                🎁 مشمول في {len(p_offers)} عرض
            </span>"""
        else:
            offer_badge = ""
        
        # ✅ شريط العنوان مع الشارة
        st.markdown(f"<div style='background: linear-gradient(135deg, #243b55 0%, #141e30 100%); padding: 14px 20px; border-radius: 12px 12px 0px 0px; margin-top: 25px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; border-bottom: 3px solid {border_color};'><span style='color: #ffffff; font-weight: bold; font-size: 15px;'>📦 {p_name}</span><div style='display: flex; gap: 8px; flex-wrap: wrap; align-items: center;'><span style='background: rgba(255,255,255,0.2); color: #fff; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;'>{disp_status}</span><span style='background: rgba(0, 235, 207, 0.2); color: #00EBCF; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;'>{tax_status}</span>{type_badge}{offer_badge}</div></div>", unsafe_allow_html=True)
        
        # ✅ زر استعراض العروض (يظهر فقط إذا كان هناك عروض)
        if p_offers:
            with st.popover(f"🎁 استعراض العروض ({len(p_offers)})", use_container_width=True):
                st.markdown("<b style='color:#b45309;'>العروض النشطة المشمول بها:</b>", unsafe_allow_html=True)
                for off in p_offers:
                    st.markdown(f"- 🎯 **{off['name']}** `(ID: {off['id']})`")
                    
        with st.container(border=True):
            c_img, c_info, c_prc, c_act = st.columns([1.5, 2.5, 2.5, 2])
            
            with c_img:
                if p_image:
                    st.image(p_image, use_container_width=True)
                else:
                    st.markdown("<div style='text-align:center; padding:30px; background:#eee; border-radius:8px;'>🚫 بدون صورة</div>", unsafe_allow_html=True)
                
                with st.popover("🖼️ إرفاق وتحديث الصورة"):
                    upload_type = st.radio("طريقة الإرفاق:", ["رفع ملف من الجهاز", "استخدام رابط URL"], key=f"img_mode_{p_id}_{idx}")
                    if upload_type == "رفع ملف من الجهاز":
                        uploaded_img = st.file_uploader("اختر صورة للمنتج:", type=['png', 'jpg', 'jpeg'], key=f"img_up_{p_id}_{idx}")
                        if uploaded_img is not None and st.button("🚀 رفع الصورة للمنتج", key=f"btn_up_{p_id}_{idx}", type="primary"):
                            with st.spinner("جاري الرفع..."):
                                if attach_product_image_api(p_id, image_bytes=uploaded_img.getvalue(), filename=uploaded_img.name):
                                    st.success("✅ تم رفع وإرفاق الصورة بنجاح!")
                                    st.rerun()
                    else:
                        img_url_input = st.text_input("أدخل الرابط المباشر للصورة:", placeholder="https://example.com/image.jpg", key=f"img_url_{p_id}_{idx}")
                        if img_url_input and st.button("🚀 ربط الصورة عبر الرابط", key=f"btn_link_{p_id}_{idx}", type="primary"):
                            with st.spinner("جاري الربط..."):
                                if attach_product_image_api(p_id, image_url=img_url_input):
                                    st.success("✅ تم ربط الصورة بنجاح!")
                                    st.rerun()
                
            with c_info:
                st.markdown(f"🆔 **المعرف:** `{p_id}` | 🔢 **SKU:** `{p_sku}`")
                st.markdown(f"📢 **ترويجي:** <span style='color:#e67e22; font-weight:bold;'>{p_promotion}</span>", unsafe_allow_html=True)
                st.markdown(f"🏷️ **فرعي:** `{p_sub_title}`")
                st.markdown(f"📦 **المخزون الإجمالي:** `{p.get('quantity', 0)}` | 📈 **المبيعات:** `{p.get('sold_quantity', 0)}`")
                st.markdown(f"🔗 [🌐 عرض في المتجر]({p_url})")

            with c_prc:
                if has_disc:
                    st.markdown(f"""<div style="background:#fff3cd; padding:10px; border-radius:8px; border-right:5px solid #ffc107;"><span style="text-decoration: line-through; color: #7f8c8d; font-size:12px;">أصلي: {base_price:,.2f} SAR</span><br><b style="color: #c0392b; font-size:15px;">مخفض: {display_sale_price:,.2f} SAR</b><span style="background:#c0392b; color:#fff; padding:2px 5px; border-radius:4px; font-size:10px;">وفرت {discount_pct}%</span></div>""", unsafe_allow_html=True)
                    st.markdown(f"📅 بداية التخفيض: `{sale_start_date}`")
                    st.markdown(f"📅 نهاية التخفيض: `{sale_end_date}`")
                else:
                    st.markdown(f"""<div style="background:#e2e8f0; padding:10px; border-radius:8px; border-right:5px solid #4a5568;"><b style="color:#2d3748; font-size:14px;">سعر ثابت: {base_price:,.2f} SAR</b></div>""", unsafe_allow_html=True)
                
                with st.expander("💰 تحديث الأسعار"):
                    np = st.number_input("أصلي (SAR):", min_value=0.0, value=float(base_price), key=f"np_{p_id}_{idx}")
                    nsp = st.number_input("مخفض (SAR) [0 للإلغاء]:", min_value=0.0, value=float(display_sale_price) if has_disc else 0.0, key=f"nsp_{p_id}_{idx}")
                    
                    col_date1, col_date2 = st.columns(2)
                    with col_date1:
                        if sale_start_date != "غير محدد":
                            try: default_start = datetime.strptime(sale_start_date, "%Y-%m-%d")
                            except: default_start = None
                        else: default_start = None
                        sd = st.date_input("بداية:", value=default_start, key=f"sd_{p_id}_{idx}")
                    with col_date2:
                        if sale_end_date != "غير محدد":
                            try: default_end = datetime.strptime(sale_end_date, "%Y-%m-%d")
                            except: default_end = None
                        else: default_end = None
                        ed = st.date_input("نهاية:", value=default_end, key=f"ed_{p_id}_{idx}")
                    
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        if st.button("💾 تحديث السعر الأصلي", key=f"sv_p_{p_id}_{idx}", use_container_width=True):
                            with st.spinner("تحديث..."):
                                if update_product_price(int(p_id), np):
                                    st.success("✅ تم تحديث السعر الأصلي!"); st.rerun()
                                else: st.error("❌ فشل التحديث")
                    
                    with col_btn2:
                        if st.button("💾 تحديث السعر المخفض", key=f"sv_s_{p_id}_{idx}", use_container_width=True):
                            with st.spinner("تحديث..."):
                                if update_product_sale_price(int(p_id), nsp, sd.strftime("%Y-%m-%d") if sd else None, ed.strftime("%Y-%m-%d") if ed else None):
                                    st.success("✅ تم تحديث السعر المخفض!"); st.rerun()
                                else: st.error("❌ فشل التحديث")

            with c_act:
                # ✅ زر العروض التفاعلي الآمن المستقل
                if p_offers:
                    with st.popover(f"🎁 استعراض العروض الخاصة للمنتج ({len(p_offers)})"):
                        st.markdown("<b style='color:#b45309;'>العروض النشطة المشمول بها:</b>", unsafe_allow_html=True)
                        for off in p_offers:
                            st.markdown(f"- 🎯 **{off['name']}** `(ID: {off['id']})`")
                
                t_st = "hidden" if status == "sale" else "sale"
                if st.button("👁️ إخفاء" if status == "sale" else "👁️ إظهار", key=f"sh_{p_id}_{idx}", type="secondary" if status == "sale" else "primary"):
                    with st.spinner("جاري التحديث..."):
                        if update_product_status(p_id, t_st): st.rerun()

                with st.popover("✏️ تحديث العناوين"):
                    # ✅ استخدام القيم الصحيحة
                    current_promo = p.get('promotion_title', '') or (p.get('promotion', {}).get('title', ''))
                    current_sub = p.get('promotion_subtitle', '') or (p.get('promotion', {}).get('sub_title', ''))
    
                    n_pr = st.text_input("ترويجي:", value=current_promo, key=f"npr_{p_id}_{idx}")
                    n_su = st.text_input("فرعي:", value=current_sub, key=f"nsu_{p_id}_{idx}")
    
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        if st.button("💾 حفظ العناوين", key=f"svt_{p_id}_{idx}", type="primary", use_container_width=True):
                            with st.spinner("جاري الحفظ..."):
                                if update_product_promotions_secure(int(p_id), n_pr, n_su, headers):
                                    st.success("✅ تم تحديث العناوين!")
                                    # تحديث البيانات في session_state
                                    for i, prod in enumerate(st.session_state["all_products"]):
                                        if str(prod.get('id')) == p_id:
                                            st.session_state["all_products"][i]['promotion_title'] = n_pr
                                            st.session_state["all_products"][i]['promotion_subtitle'] = n_su
                                            if 'promotion' in st.session_state["all_products"][i]:
                                                st.session_state["all_products"][i]['promotion']['title'] = n_pr
                                                st.session_state["all_products"][i]['promotion']['sub_title'] = n_su
                                            break
                                    st.rerun()
                                else:
                                    st.error("❌ فشل تحديث العناوين")
    
                    with col_btn2:
                        # ✅ زر التشخيص (يظهر بجانب زر الحفظ)
                        if st.button("🔍 تشخيص العناوين", key=f"diag_{p_id}_{idx}", use_container_width=True):
                            st.session_state["diagnose_product_id"] = int(p_id)
                            st.session_state["show_diagnose"] = True
                            st.rerun()

                # ✅ زر حذف المنتج
                with st.popover("حذف المنتج", icon="🗑️", type="primary"):
                    st.warning("⚠️ تحذير: حذف المنتج نهائي ولا يمكن استرجاعه!")
                    st.write(f"**المنتج:** {p_name}")
                    st.write(f"**المعرف:** `{p_id}`")
                    
                    confirm_delete = st.checkbox("☑️ أوافق على الحذف النهائي", key=f"confirm_delete_{p_id}_{idx}")
                    
                    if st.button("🗑️ حذف نهائياً", key=f"delete_{p_id}_{idx}", type="primary", disabled=not confirm_delete, use_container_width=True):
                        with st.spinner("جاري حذف المنتج..."):
                            if delete_product(int(p_id)):
                                st.success("✅ تم حذف المنتج بنجاح!")
                                st.rerun()
                            else:
                                st.error("❌ فشل حذف المنتج")

                with st.popover("📗 إعدادات الضريبة"):
                    is_taxed = st.checkbox("خاضع للضريبة", value=p.get('with_tax', True), key=f"tax_chk_{p_id}_{idx}")
                    ex_cause = p.get('tax_exemption_cause', '')
                    if not is_taxed:
                        cause_idx = TAX_EXEMPTION_CAUSES.index(ex_cause) if ex_cause in TAX_EXEMPTION_CAUSES else 0
                        selected_cause = st.selectbox("سبب الإعفاء من الضريبة:", TAX_EXEMPTION_CAUSES, index=cause_idx, key=f"tax_cause_{p_id}_{idx}")
                    else:
                        selected_cause = ""
                        
                    if st.button("💾 حفظ حالة الضريبة", key=f"save_tax_{p_id}_{idx}", type="primary", use_container_width=True):
                        with st.spinner("جاري التحديث..."):
                            if update_product_tax_secure(p_id, is_taxed, selected_cause, headers):
                                st.success("✅ تم تحديث حالة الضريبة بنجاح!")
                                st.rerun()
                
                # ✅ كميات الفروع مع زر تحديث عام
                with st.popover("🏢 كميات الفروع"):
                    if not branches:
                        st.warning("⚠️ لا توجد فروع مسجلة في المتجر.")
                    else:
                        st.markdown("**📊 الكميات الحالية في الفروع:**")
        
                        # ✅ زر الكشف التلقائي الحي
                        if st.button("🔍 كشف الأرصدة الحية", key=f"live_fetch_{p_id}_{idx}", use_container_width=True):
                            with st.spinner("جاري جلب الأرصدة الحية من سلة..."):
                                live_qty = get_live_branch_quantities(int(p_id), headers)
                                if live_qty:
                                    st.session_state[f"live_qty_{p_id}"] = live_qty
                                    st.success("✅ تم جلب الأرصدة الحية بنجاح!")
                                    st.rerun()
                                else:
                                    st.error("❌ فشل جلب الأرصدة. تأكد من أن المنتج مدار بواسطة الفروع.")
        
                        # عرض الكميات
                        branch_updates = []
                        live_qty = st.session_state.get(f"live_qty_{p_id}", {})
        
                        for b in branches:
                            branch_id = b.get('id')
                            branch_name = b.get('name', f'فرع {branch_id}')
                            current_qty = live_qty.get(branch_id, 0)
            
                            # عرض الكمية الحالية
                            st.markdown(f"""
                            <div style='
                                background: #f8f9fa; 
                                border-radius: 8px; 
                                padding: 8px 12px; 
                                margin-bottom: 6px;
                                border-right: 3px solid {"#00EBCF" if current_qty > 0 else "#e74c3c"};
                            '>
                                🏪 **{branch_name}**: الكمية الحالية = <b style='color: {"#2ecc71" if current_qty > 0 else "#e74c3c"};'>{current_qty}</b>
                            </div>
                            """, unsafe_allow_html=True)
            
                            # حقل تعديل الكمية
                            new_q = st.number_input(
                                f"تعديل كمية {branch_name}",
                                min_value=0, 
                                value=current_qty,
                                step=1, 
                                key=f"bq_{p_id}_{branch_id}_{idx}",
                                label_visibility="collapsed"
                            )
            
                            # تخزين التغييرات
                            branch_updates.append({
                                "identifer": p_sku, 
                                "identifer_type": "sku", 
                                "branch_id": branch_id, 
                                "quantity": new_q, 
                                "mode": "overwrite"
                            })
        
                        # ✅ زر تحديث الكميات العام (لجميع الفروع دفعة واحدة)
                        st.markdown("---")
                        if st.button("💾 حفظ جميع الكميات (لجميع الفروع)", key=f"save_all_bq_{p_id}_{idx}", type="primary", use_container_width=True):
                            with st.spinner("جاري حفظ جميع الكميات في سلة..."):
                                res = safe_api_request(
                                    "POST", 
                                    "https://api.salla.dev/admin/v2/products/quantities/bulk", 
                                    headers, 
                                    json={"products": branch_updates}
                                )
                                if res:
                                    st.success("✅ تم تحديث جميع الكميات بنجاح!")
                                    if f"live_qty_{p_id}" in st.session_state:
                                        del st.session_state[f"live_qty_{p_id}"]
                                    st.rerun()
                                else:
                                    st.error("❌ فشل تحديث الكميات")
        
                        # ✅ زر تحديث الكميات لفرع واحد (بجانب كل فرع)
                        # هذا موجود بالفعل في الحقل أعلاه
            
            st.markdown("</div>", unsafe_allow_html=True)

            # ✅ قسم عرض المجموعات (يعمل بذكاء)
            if product_type == 'group_products':
                render_group_product_section(p_id, p_name, idx, headers)

    except Exception as e:
        st.error(f"❌ خطأ أثناء عرض بطاقة المنتج (ID: {p.get('id')}): {str(e)}")

# ==========================================
# 🚀 4. الدالة الرئيسية للملف
# ==========================================

def get_branch_quantities(product_id: int) -> Dict:
    """جلب كميات المنتج في جميع الفروع"""
    headers = get_headers()
    if not headers: 
        return {}
    
    branch_qty = {}
    
    try:
        # ✅ الطريقة 1: استخدام API كميات المنتج
        res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products/quantities?product={product_id}", headers)
        if res and res.get('data'):
            for item in res['data']:
                branch_id = item.get('branch_id')
                if branch_id:
                    branch_qty[branch_id] = item.get('quantity', 0)
            return branch_qty
    except Exception as e:
        pass
    
    try:
        # ✅ الطريقة 2: من product details
        res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products/{product_id}", headers)
        if res and res.get('data'):
            product = res['data']
            
            # طريقة branches_quantities
            if product.get('branches_quantities'):
                for item in product['branches_quantities']:
                    branch_id = item.get('id')
                    if branch_id:
                        branch_qty[branch_id] = item.get('quantity', 0)
                return branch_qty
            
            # طريقة scoped_prices
            if product.get('scoped_prices'):
                for item in product['scoped_prices']:
                    scope_id = item.get('scope_id')
                    if scope_id:
                        branch_qty[scope_id] = item.get('quantity', 0)
                return branch_qty
            
            # طريقة branches
            if product.get('branches'):
                for item in product['branches']:
                    branch_id = item.get('id')
                    if branch_id:
                        branch_qty[branch_id] = item.get('quantity', 0)
                return branch_qty
            
            # طريقة default (كمية إجمالية)
            total_qty = product.get('quantity', 0)
            if total_qty > 0:
                branch_qty['default'] = total_qty
            return branch_qty
    except:
        pass
    
    return branch_qty

def fetch_group_products_v2(parent_id: int, headers: Dict[str, str]) -> List[Dict]:
    """جلب المنتجات الفرعية لمجموعة باستخدام API سلة الصحيح"""
    items = []
    try:
        res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products/{parent_id}", headers)
        if not res or not res.get('data'): 
            return items
        
        data = res['data']
        
        # ✅ الطريقة 1: consisted_products (الأفضل والأحدث)
        if data.get('consisted_products'):
            for item in data['consisted_products']:
                items.append({
                    'id': item.get('id'),
                    'name': item.get('name', 'منتج بدون اسم'),
                    'sku': item.get('sku', 'لا يوجد'),
                    'price': get_flat_price(item.get('price', 0)),
                    'bundle_quantity': item.get('quantity_in_group', 1),
                    'stock_quantity': item.get('quantity', 0),
                    'sold_quantity': item.get('sold_quantity', 0),
                    'status': item.get('status', 'sale'),
                    'image': item.get('thumbnail') or item.get('main_image'),
                    'url': item.get('url'),
                    'with_tax': item.get('with_tax', True)
                })
            return items
        
        # ✅ الطريقة 2: bundle.products
        bundle = data.get('bundle', {})
        if bundle.get('products'):
            for item in bundle['products']:
                items.append({
                    'id': item.get('id'),
                    'name': item.get('name', 'منتج بدون اسم'),
                    'sku': item.get('sku', 'لا يوجد'),
                    'price': item.get('price', 0),
                    'bundle_quantity': item.get('quantity_in_group', 1),
                    'stock_quantity': item.get('qty', 0),
                    'sold_quantity': 0,
                    'status': 'sale',
                    'image': item.get('main_image'),
                    'url': None,
                    'with_tax': True
                })
            return items
        
        # ✅ الطريقة 3: grouped_items
        if data.get('grouped_items'):
            for item in data['grouped_items']:
                prod = item.get('product', {})
                if prod and prod.get('id'):
                    items.append({
                        'id': prod.get('id'),
                        'name': prod.get('name', 'منتج بدون اسم'),
                        'sku': prod.get('sku', 'لا يوجد'),
                        'price': get_flat_price(prod.get('price', 0)),
                        'bundle_quantity': item.get('quantity', 1),
                        'stock_quantity': prod.get('quantity', 0),
                        'sold_quantity': prod.get('sold_quantity', 0),
                        'status': prod.get('status', 'sale'),
                        'image': prod.get('thumbnail') or prod.get('main_image'),
                        'url': prod.get('url'),
                        'with_tax': prod.get('with_tax', True)
                    })
            return items
        
    except Exception as e:
        st.error(f"❌ خطأ: {str(e)}")
    
    return items

# ==========================================
# 🔍 أداة كشف تلقائي حي للأرصدة
# ==========================================

def get_live_branch_quantities(product_id: int, headers: Dict[str, str]) -> Dict:
    """
    جلب الأرصدة الحية من API سلة مباشرة
    """
    try:
        # ✅ الطريقة الصحيحة: استخدام API كميات المنتج
        res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products/quantities?product={product_id}", headers)
        if res and res.get('data'):
            branch_qty = {}
            for item in res['data']:
                branch_id = item.get('branch_id')
                if branch_id:
                    branch_qty[branch_id] = item.get('quantity', 0)
            return branch_qty
    except Exception as e:
        pass
    
    try:
        # ✅ طريقة بديلة: من product details
        res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products/{product_id}", headers)
        if res and res.get('data'):
            product = res['data']
            branch_qty = {}
            
            # طريقة branches_quantities
            if product.get('branches_quantities'):
                for item in product['branches_quantities']:
                    branch_qty[item.get('id')] = item.get('quantity', 0)
                return branch_qty
            
            # طريقة scoped_prices
            if product.get('scoped_prices'):
                for item in product['scoped_prices']:
                    branch_qty[item.get('scope_id')] = item.get('quantity', 0)
                return branch_qty
            
            # طريقة branches
            if product.get('branches'):
                for item in product['branches']:
                    branch_qty[item.get('id')] = item.get('quantity', 0)
                return branch_qty
    except:
        pass
    
    return {}
