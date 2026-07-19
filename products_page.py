import streamlit as st
import pandas as pd
import requests
import io
from datetime import datetime
from typing import Dict, List, Any

from utils import (
    get_headers, safe_api_request, get_flat_price, update_product_status, 
    export_products_to_excel, attach_product_image_api, update_product_promotions_secure,
    update_product_tax_secure, get_branches_list, generate_quantities_template, 
    process_quantities_import, fill_salla_template, generate_salla_new_products_file, 
    delete_product, update_product_price, update_product_sale_price, 
    remove_product_from_group, add_product_to_group, get_product_details, get_group_products,
    update_group_product_quantity
)

TAX_EXEMPTION_CAUSES = ["الخدمات المالية", "عقد تأمين على الحياة", "التوريدات العقارية المعفاة", "صادرات السلع من المملكة", "صادرات الخدمات من المملكة", "النقل الدولي للسلع", "النقل الدولي للركاب", "توريد وسائل النقل", "الأدوية والمعدات الطبية"]

# ==========================================
# 🌐 1. دوال المزامنة والتهيئة
# ==========================================
def initialize_session():
    if "qa_action_prod" not in st.session_state: st.session_state.qa_action_prod = None
    if "prod_page" not in st.session_state: st.session_state.prod_page = 1
# ==========================================
# 📦 2. دوال جلب المجموعات 
# ==========================================
def update_group_product_quantity(parent_product_id: int, child_product_id: int, new_quantity: int) -> bool:
    """تحديث عدد الحبات للمنتج الفرعي داخل المجموعة بأمان تام (بدون إرسال حقل المخزون الكلي)"""
    headers = get_headers()
    if not headers: return False
    
    parent = get_product_details(parent_product_id)
    if not parent: return False
    
    # 1. استخراج المنتجات الفرعية الحالية
    items = []
    updated = False
    
    for item in parent.get('grouped_items', []):
        pid = item.get('product_id') or item.get('product', {}).get('id')
        qty = item.get('quantity', 1)
        
        if str(pid) == str(child_product_id):
            # تحديث عدد الحبات للمنتج المستهدف فقط
            items.append({"product_id": int(pid), "quantity": int(new_quantity)})
            updated = True
        else:
            # الاحتفاظ بباقي المنتجات كما هي
            items.append({"product_id": int(pid), "quantity": int(qty)})
            
    if not updated: 
        return False
        
    # 2. بناء Payload نظيف جداً!
    # 🚨 تحذير: يمنع إرسال "quantity" أو "price" للمنتج الأب هنا لتجنب خطأ 422 من سلة
    payload = {
        "name": parent.get('name'),
        "type": "group_products",
        "grouped_items": items 
    }
    
    # 3. إرسال الطلب
    res = safe_api_request("PUT", f"https://api.salla.dev/admin/v2/products/{parent_product_id}", headers, json=payload)
    if res:
        return True
    return False
    
def fetch_group_products_smart(parent_id: int, headers: Dict[str, str]) -> List[Dict]:
    items = []
    try:
        res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products/{parent_id}", headers)
        if not res or not res.get('data'): return items
        data = res['data']
        
        if data.get('consisted_products'):
            for item in data['consisted_products']:
                items.append({
                    'id': str(item.get('id', '')), 'name': item.get('name', 'بدون اسم'), 'sku': item.get('sku', 'لا يوجد'),
                    'price': get_flat_price(item.get('price', 0)), 'bundle_quantity': item.get('quantity_in_group', 1),
                    'stock_quantity': item.get('quantity', 0), 'status': item.get('status', 'sale'),
                    'image': item.get('thumbnail') or item.get('main_image'), 'url': item.get('url'),
                    'with_tax': item.get('with_tax', True)
                })
            return items
            
        if data.get('grouped_items'):
            for item in data['grouped_items']:
                prod_id = item.get('product_id') or (item.get('product', {}).get('id') if isinstance(item.get('product'), dict) else None)
                if prod_id:
                    sub_res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products/{prod_id}", headers)
                    if sub_res and sub_res.get('data'):
                        sp = sub_res['data']
                        items.append({
                            'id': str(sp.get('id', '')), 'name': sp.get('name', 'بدون اسم'), 'sku': sp.get('sku', 'لا يوجد'),
                            'price': get_flat_price(sp.get('price', 0)), 'bundle_quantity': item.get('quantity', 1),
                            'stock_quantity': sp.get('quantity', 0), 'status': sp.get('status', 'sale'),
                            'image': sp.get('thumbnail') or sp.get('main_image'), 'url': sp.get('url'),
                            'with_tax': sp.get('with_tax', True)
                        })
            return items
    except Exception as e:
        st.error(f"❌ خطأ جلب تفاصيل المجموعة: {str(e)}")
    return items

# ==========================================
# 🎨 3. رسم بطاقات المنتجات
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

        # ✅ قراءة الشارة الترويجية مباشرة من خريطة الـ Session State
        po_map = st.session_state.get("product_offers_map", {})
        p_offers_raw = po_map.get(p_id, []) + po_map.get("ALL_PRODUCTS", [])
        unique_offers = {off['id']: off for off in p_offers_raw}.values()
        p_offers = list(unique_offers)
        
        offer_badge = f"<span style='background: linear-gradient(135deg, #F7971E 0%, #FFD200 100%); color: #1a1a2e; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: 700; border: 1px solid #FFD700; box-shadow: 0 2px 8px rgba(255, 215, 0, 0.4);'>🎁 مشمول في ({len(p_offers)}) عروض</span>" if p_offers else ""

        st.markdown(f"<div style='background: linear-gradient(135deg, #243b55 0%, #141e30 100%); padding: 14px 20px; border-radius: 12px 12px 0px 0px; margin-top: 25px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; border-bottom: 3px solid {border_color};'><span style='color: #ffffff; font-weight: bold; font-size: 15px;'>📦 {p_name}</span><div style='display: flex; gap: 8px; flex-wrap: wrap; align-items: center;'><span style='background: rgba(255,255,255,0.2); color: #fff; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;'>{disp_status}</span><span style='background: rgba(0, 235, 207, 0.2); color: #00EBCF; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;'>{tax_status}</span>{type_badge}{offer_badge}</div></div>", unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown("""<div style="background-color: #fafbfc; padding: 20px; border-radius: 0px 0px 12px 12px; border: 1px solid #e1e8ed; border-top: none; margin-bottom: 20px;">""", unsafe_allow_html=True)
            c_img, c_info, c_prc, c_act = st.columns([1.5, 2.5, 2.5, 2])
            
            with c_img:
                if p_image: st.image(p_image, use_container_width=True)
                else: st.markdown("<div style='text-align:center; padding:30px; background:#eee; border-radius:8px;'>🚫 بدون صورة</div>", unsafe_allow_html=True)
                
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
                    col_d1, col_d2 = st.columns(2)
                    with col_d1:
                        sd_val = datetime.strptime(sale_start_date, "%Y-%m-%d") if sale_start_date != "غير محدد" else None
                        sd = st.date_input("بداية:", value=sd_val, key=f"sd_{p_id}_{idx}")
                    with col_d2:
                        ed_val = datetime.strptime(sale_end_date, "%Y-%m-%d") if sale_end_date != "غير محدد" else None
                        ed = st.date_input("نهاية:", value=ed_val, key=f"ed_{p_id}_{idx}")

                    c_btn1, c_btn2 = st.columns(2)
                    with c_btn1:
                        if st.button("💾 حفظ", key=f"sv_p_{p_id}_{idx}", use_container_width=True, type="primary"):
                            if update_product_price(int(p_id), np) and update_product_sale_price(int(p_id), nsp): st.rerun()

            with c_act:
                if p_offers:
                    with st.popover(f"🎁 استعراض عروض المنتج ({len(p_offers)})", use_container_width=True):
                        st.markdown("<b style='color:#b45309;'>العروض النشطة المشمول بها:</b>", unsafe_allow_html=True)
                        for off in p_offers: st.markdown(f"- 🎯 **{off['name']}** `({off['id']})`")
                
                t_st = "hidden" if status == "sale" else "sale"
                if st.button("👁️ إخفاء" if status == "sale" else "👁️ إظهار", key=f"sh_{p_id}_{idx}", type="secondary" if status == "sale" else "primary", use_container_width=True):
                    if update_product_status(p_id, t_st): st.rerun()

                with st.popover("✏️ تحديث العناوين", use_container_width=True):
                    n_pr = st.text_input("ترويجي:", value="" if p_promotion=="-" else p_promotion, key=f"npr_{p_id}_{idx}")
                    n_su = st.text_input("فرعي:", value="" if p_sub_title=="-" else p_sub_title, key=f"nsu_{p_id}_{idx}")
                    if st.button("💾 حفظ العناوين", key=f"svt_{p_id}_{idx}", type="primary", use_container_width=True):
                        if update_product_promotions_secure(int(p_id), n_pr, n_su, headers): st.rerun()
                        
            st.markdown("</div>", unsafe_allow_html=True)
            
            if product_type == 'group_products':
                st.markdown("---")
                with st.spinner(f"جاري جلب تفاصيل المجموعة..."):
                    g_prods = fetch_group_products_smart(int(p_id), headers)
                with st.expander(f"📦 استعراض وإدارة المنتجات الفرعية للمجموعة (العدد: {len(g_prods)})", expanded=False):
                    if not g_prods: st.info("ℹ️ لا توجد منتجات فرعية مسجلة.")
                    else:
                        for gp_idx, gp in enumerate(g_prods):
                            st.markdown(f"<div style='background: #f8f9fa; border-radius: 10px; padding: 15px; margin-bottom: 12px; border-left: 4px solid #6C2BD9;'><div style='display: flex; gap: 15px;'><div style='flex: 1;'><b>{gp.get('name', 'بدون اسم')}</b><br><span style='font-size: 12px; color: #666;'>🆔 {gp.get('id', '')} | 🔢 {gp.get('sku', '')} | 💰 {get_flat_price(gp.get('price', 0)):.2f} SAR</span></div><div style='flex: 0 0 120px; font-size: 13px; font-weight: bold;'>📦 حبات بالمجموعة: <span style='color:#6C2BD9;'>{gp.get('bundle_quantity', 1)}</span><br>🏪 متوفر: {gp.get('stock_quantity', 0)}</div></div></div>", unsafe_allow_html=True)
                            
                            c_q, c_act2 = st.columns(2)
                            with c_q:
                                new_q = st.number_input("تعديل الحبات", min_value=1, value=int(gp.get('bundle_quantity', 1)), key=f"gq_{gp.get('id')}_{idx}_{gp_idx}", label_visibility="collapsed")
                                if st.button("💾 تحديث الكمية", key=f"gqs_{gp.get('id')}_{idx}_{gp_idx}"):
                                    if update_group_product_quantity(int(p_id), int(gp.get('id')), new_q): st.rerun()
                            with c_act2:
                                if st.button("🗑️ إزالة من المجموعة", key=f"gqr_{gp.get('id')}_{idx}_{gp_idx}"):
                                    if remove_product_from_group(int(p_id), int(gp.get('id'))): st.rerun()
                            st.markdown("<hr style='margin:10px 0; border:0; border-bottom:1px dashed #ddd;'>", unsafe_allow_html=True)
                            
                        # إضافة منتج للمجموعة
                        st.markdown("#### ➕ إضافة منتج للمجموعة")
                        search_p = st.text_input("ابحث باسم أو SKU للإضافة:", key=f"gps_{p_id}_{idx}")
                        if search_p:
                            f_prods = [pr for pr in st.session_state.get("all_products", []) if str(pr.get('id')) != p_id and (search_p.lower() in str(pr.get('name', '')).lower() or search_p.lower() in str(pr.get('sku', '')).lower())]
                            if f_prods:
                                for pr in f_prods[:5]:
                                    c1, c2 = st.columns([3, 1])
                                    with c1: st.markdown(f"**{pr.get('name')}** | `{pr.get('sku')}`")
                                    with c2:
                                        if st.button("➕ إضافة", key=f"gpa_{pr.get('id')}_{idx}"):
                                            if add_product_to_group(int(p_id), pr.get('id')): st.rerun()
                            else:
                                st.info("لا توجد تطابقات.")

    except Exception as e:
        st.error(f"❌ خطأ أثناء عرض بطاقة المنتج (ID: {p.get('id')}): {str(e)}")

# ==========================================
# 🚀 4. الدالة الرئيسية للصفحة (تشمل الفلاتر واللوحة الجانبية)
# ==========================================
def render_products_page():
    initialize_session()
    headers = get_headers()
    if not headers: return
    
    st.markdown("""
    <div style="background: linear-gradient(135deg, #0F1C2E 0%, #00EBCF 100%); padding: 15px 25px; border-radius: 12px; color: white; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        <h2 style="color: white; margin: 0;">📦 مركز إدارة المنتجات الذكي والمتقدم</h2>
    </div>
    """, unsafe_allow_html=True)

    # 🌟 CSS اللوحة الجانبية
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
        div[data-testid="stElementContainer"]:has(span[id^="qa-marker-"]) + div[data-testid="stElementContainer"]::before { content: "👈"; position: absolute; left: 10px; top: 50%; transform: translateY(-50%); font-size: 18px; pointer-events: none; }
        /* زر الجوال */
        .mobile-toggle-btn {
            position: fixed; right: 0px; top: 50%; transform: translateY(-50%); background: #00EBCF; color: #0f1c2e; border: none;
            border-radius: 8px 0 0 8px; padding: 10px 6px; font-size: 14px; cursor: pointer; z-index: 999998; writing-mode: vertical-rl;
            font-weight: bold; box-shadow: -2px 2px 10px rgba(0,0,0,0.3); display: none;
        }
        @media (pointer: coarse) {
            .mobile-toggle-btn { display: block !important; }
            div[data-testid="stElementContainer"]:has(span[id^="qa-marker-"]) + div[data-testid="stElementContainer"] {
                right: 0px !important; width: 200px !important; opacity: 0.85 !important;
            }
            div[data-testid="stElementContainer"]:has(span[id^="qa-marker-"]) + div[data-testid="stElementContainer"] button {
                font-size: 12px !important; padding-right: 10px !important; padding: 4px 8px !important;
            }
            div[data-testid="stElementContainer"]:has(span[id^="qa-marker-"]) + div[data-testid="stElementContainer"]::before { display: none !important; }
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
                
                st.markdown("#### 🚀 رفع ملف المنتجات إلى سلة")
                import_type_label = st.radio("اختر نوع العملية:", ["تحديث منتجات حالية", "إضافة منتجات جديدة"], horizontal=True)
                import_type_value = "products-update" if import_type_label == "تحديث منتجات حالية" else "products"
                uploaded_products_file = st.file_uploader("📂 ارفع ملف الإكسيل الأصلي:", type=['xlsx'], key="upload_products_file")
                if uploaded_products_file and st.button(f"رفع الملف ({import_type_label})", type="primary", use_container_width=True):
                    with st.spinner("جاري رفع الملف إلى سلة..."):
                        try:
                            files = {'file': (uploaded_products_file.name, uploaded_products_file.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
                            uh = headers.copy()
                            if "Content-Type" in uh: del uh["Content-Type"]
                            res = requests.post("https://api.salla.dev/admin/v2/products/import", headers=uh, files=files, data={'type': import_type_value})
                            if res.status_code < 400: st.success("✅ تم الرفع للمعالجة في الخلفية.")
                            else: st.error(f"❌ فشل الرفع: {res.text}")
                        except Exception as e: st.error(f"❌ خطأ: {e}")
                
                st.markdown("---")
                st.markdown("#### 📦 تحديث كميات الفروع (Bulk)")
                st.download_button("📥 تنزيل نموذج الكميات", data=generate_quantities_template(), file_name="Salla_Quantities.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                uploaded_q_file = st.file_uploader("📂 رفع ملف تحديث الكميات:", type=['xlsx'], key="upload_q_file")
                if uploaded_q_file and st.button("🚀 تحديث الكميات (Bulk)", type="primary", use_container_width=True):
                    try:
                        df_q = pd.read_excel(uploaded_q_file)
                        with st.spinner("جاري التحديث..."):
                            res_q = process_quantities_import(df_q)
                            for m in res_q["success"]: st.success(m)
                            for m in res_q["errors"]: st.error(m)   
                    except Exception as e: st.error(f"❌ خطأ: {e}")

            elif st.session_state.qa_action_prod == "app_settings":
                with col_t: st.markdown("### ⚙️ إعدادات ربط التطبيقات")
                st.text_input("📝 عنوان القسم الفعال:", value="شاهدتها مؤخراً")
                c1, c2, c3 = st.columns(3)
                with c1: st.checkbox("الصفحة الرئيسية بالمتجر", value=False)
                with c2: st.checkbox("صفحة التصنيفات والأقسام", value=False)
                with c3: st.checkbox("صفحة تفاصيل وعرض المنتج", value=True)
                st.number_input("🔢 عدد المنتجات المعروضة:", min_value=1, max_value=32, value=6)
                st.markdown("#### 🛠️ نظام التوصية الذكي والحزم")
                st.checkbox("✅ تفعيل التوصيات في المتجر", value=True)
                st.checkbox("🤝 تشترى معًا", value=True)
                st.selectbox("🛒 عرض زر إضافة للسلة:", ["في صفحة السلة فقط", "في جميع الصفحات"], index=0)
                if st.button("💾 حفظ وتثبيت إعدادات التطبيقات", type="primary", use_container_width=True):
                    st.success("✅ تم الحفظ بنجاح!")
                    
            # --- 3. المطابقة ---
            elif st.session_state.qa_action_prod == "salla_matching":
                with col_t: st.markdown("### 🔄 مطابقة منتجات سلة مع النظام الداخلي")
                st.info("📋 يرجى رفع ملف المطابقة بصيغة Excel.")
                exclude_cats_str = st.text_input("🚫 تصنيفات مستبعدة (مفصولة بفاصلة):", placeholder="مثال: اكسسوارات")
                uploaded_matching = st.file_uploader("📂 رفع ملف المطابقة (XLSX):", type=["xlsx"])
                if uploaded_matching:
                    try:
                        xl = pd.ExcelFile(uploaded_matching)
                        if 'salla' not in xl.sheet_names or 'system' not in xl.sheet_names:
                            st.error("❌ الشيت 'salla' أو 'system' غير موجود")
                        else:
                            df_salla = pd.read_excel(uploaded_matching, sheet_name='salla')
                            df_system = pd.read_excel(uploaded_matching, sheet_name='system')
                            
                            if exclude_cats_str and len(df_system.columns) >= 5:
                                exclude_cats = [c.strip().lower() for c in exclude_cats_str.split(",") if c.strip()]
                                if exclude_cats:
                                    cat_col = df_system.columns[4]
                                    df_system = df_system[~df_system[cat_col].astype(str).str.lower().str.strip().isin(exclude_cats)]
                                    st.success(f"تم استبعاد تصنيفات: {', '.join(exclude_cats)}")
                        
                            salla_ids = set()
                            if df_salla.empty:
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
                                
                                c_all, c_none = st.columns(2)
                                with c_all:
                                    if st.button("☑️ اختيار الكل", use_container_width=True):
                                        for i in range(len(new_products)): st.session_state[f"sel_{i}"] = True
                                        st.rerun()
                                with c_none:
                                    if st.button("⬜ إلغاء الكل", use_container_width=True):
                                        for i in range(len(new_products)): st.session_state[f"sel_{i}"] = False
                                        st.rerun()

                                selected_indices = []
                                for i, product in enumerate(new_products):
                                    key = f"sel_{i}"
                                    if key not in st.session_state: st.session_state[key] = True
                                    checked = st.checkbox(f"🆔 {product['رقم المنتج']} - {product['اسم المنتج']}", value=st.session_state[key], key=key)
                                    if checked != st.session_state[key]: st.session_state[key] = checked
                                    if checked: selected_indices.append(i)
                            
                                if st.button(f"🚀 رفع {len(selected_indices)} منتج لسلة", type="primary", use_container_width=True):
                                    if not selected_indices: st.warning("⚠️ اختر منتجاً")
                                    else:
                                        with st.spinner("🔄 جاري التجهيز والرفع..."):
                                            p_for_template = []
                                            for i in selected_indices:
                                                pr = new_products[i]
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
    # 🔍 الفلاتر السريعة
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
            
        pr = get_flat_price(p.get('price', 0)); reg = get_flat_price(p.get('regular_price', 0)); sal = get_flat_price(p.get('sale_price', 0))
        is_discounted = (sal > 0 and sal < (reg if reg > 0 else pr))
        if f_disc == "مخفض" and not is_discounted: continue
        if f_disc == "ثابت" and is_discounted: continue
            
        is_group = (p.get('type') == 'group_products')
        if f_type == "عادية" and is_group: continue
        if f_type == "مجموعات" and not is_group: continue
        
        # ✅ فلتر العروض الدقيق
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
            st.download_button("📥 تحميل المنتجات المفلترة (Excel)", data=export_products_to_excel(filtered), file_name="Filtered_Products.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary", key="download_filtered_products", use_container_width=True)
        with col_download2:
            st.info(f"📄 يحتوي الملف على {len(filtered)} منتج")

    # Pagination
    limit = 20
    pages = max(1, (len(filtered) + limit - 1) // limit)
    start = (st.session_state["prod_page"] - 1) * limit
    
    cp, cc, cn = st.columns([1,2,1])
    with cp:
        if st.button("⬅️ السابقة", disabled=st.session_state["prod_page"]==1, use_container_width=True): 
            st.session_state["prod_page"] -= 1; st.rerun()
    with cc: st.markdown(f"<h4 style='text-align:center;'>📄 صفحة {st.session_state['prod_page']} من {pages}</h4>", unsafe_allow_html=True)
    with cn:
        if st.button("التالية ➡️", disabled=st.session_state["prod_page"]==pages, use_container_width=True): 
            st.session_state["prod_page"] += 1; st.rerun()

    for idx, p in enumerate(filtered[start:start+limit]):
        render_product_card(start + idx, p, headers)
