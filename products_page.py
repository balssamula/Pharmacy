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

def initialize_session():
    if "qa_action_prod" not in st.session_state: st.session_state.qa_action_prod = None
    if "prod_page" not in st.session_state: st.session_state.prod_page = 1

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
    </style>
    """, unsafe_allow_html=True)

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
            elif st.session_state.qa_action_prod == "app_settings":
                with col_t: st.markdown("### ⚙️ إعدادات ربط التطبيقات")
                st.checkbox("✅ تفعيل التوصيات في المتجر", value=True)
                if st.button("💾 حفظ", type="primary"): st.success("تم الحفظ")
            elif st.session_state.qa_action_prod == "salla_matching":
                with col_t: st.markdown("### 🔄 مطابقة المنتجات مع النظام")
                st.file_uploader("📂 رفع ملف المطابقة", type=["xlsx"])
    
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
    
    if filtered:
        st.download_button("📥 تحميل المنتجات المفلترة (Excel)", data=export_products_to_excel(filtered), file_name="Filtered.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

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
