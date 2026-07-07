import streamlit as st
import pandas as pd
import requests
import pickle
import io
import os
from datetime import datetime
from typing import Dict, List, Optional
from openpyxl import load_workbook
from utils import (
    get_headers, safe_api_request, get_flat_price, update_product_status, 
    export_products_to_excel, attach_product_image_api, update_product_promotions_secure,
    update_product_tax_secure, get_branches_list, generate_quantities_template, 
    process_quantities_import, create_products_template, fill_salla_template,
    generate_salla_new_products_file, delete_product, update_product_price, 
    update_product_sale_price, update_product_prices_bulk, get_product_details, 
    update_group_product_quantity, remove_product_from_group, 
    add_product_to_group, get_group_products
)

TAX_EXEMPTION_CAUSES = ["الخدمات المالية", "عقد تأمين على الحياة", "التوريدات العقارية المعفاة", "صادرات السلع من المملكة", "صادرات الخدمات من المملكة", "النقل الدولي للسلع", "النقل الدولي للركاب", "توريد وسائل النقل", "الأدوية والمعدات الطبية"]

def save_products_to_cache(products):
    with open("products_cache.pkl", "wb") as f:
        pickle.dump(products, f)

def load_products_from_cache():
    try:
        with open("products_cache.pkl", "rb") as f:
            return pickle.load(f)
    except:
        return []
        
def render_products_page():
    # ترويسة جمالية لصفحة المنتجات
    st.markdown("""
    <div style="background: linear-gradient(135deg, #0F1C2E 0%, #00EBCF 100%); padding: 15px 25px; border-radius: 12px; color: white; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        <h2 style="color: white; margin: 0;">📦 مركز إدارة المنتجات الذكي والمتقدم</h2>
    </div>
    """, unsafe_allow_html=True)
    
    headers = get_headers()
    if not headers: return

    # ✅ تعريف المتغيرات في session_state
    if "all_products" not in st.session_state: st.session_state["all_products"] = []
    if "all_products_fetched" not in st.session_state: st.session_state["all_products_fetched"] = False
    if "prod_page" not in st.session_state: st.session_state["prod_page"] = 1
    if "offer_product_ids" not in st.session_state: st.session_state["offer_product_ids"] = set()
    if "branches" not in st.session_state: st.session_state["branches"] = get_branches_list()
    if "last_sync_time" not in st.session_state: st.session_state["last_sync_time"] = None
    if "product_offers_map" not in st.session_state: st.session_state["product_offers_map"] = {}
    
    # تعريف المتغيرات المحلية
    all_products = st.session_state["all_products"]
    offer_product_ids = st.session_state["offer_product_ids"]
    branches = st.session_state["branches"]
    
    # ==========================================
    # 🌟 دالة ذكية لجلب محتويات "مجموعة المنتجات"
    # ==========================================
    def robust_get_group_products(parent_id: int) -> List[Dict]:
        """دالة مخصصة تتجاوز مشاكل API وتلتقط المنتجات الفرعية بكل الطرق الممكنة"""
        return get_group_products(parent_id)

    # زر المزامنة
    c_title, c_btn = st.columns([3, 1])
    with c_btn:
        if st.button("🔄 مزامنة وجلب كافة المنتجات", use_container_width=True, type="primary"):
            with st.spinner("⏳ جاري سحب وتصنيف كافة المنتجات والعروض النشطة..."):
                
                # 1. تحديث الفروع
                st.session_state["branches"] = get_branches_list()
                
                # 2. سحب المنتجات
                all_p = []
                page = 1
                while True:
                    res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products?per_page=60&page={page}", headers)
                    if not res or not res.get("data"): break
                    all_p.extend(res["data"])
                    if page >= res.get("pagination", {}).get("totalPages", 1): break
                    page += 1
                st.session_state["all_products"] = all_p
                
                # 3. سحب وتصنيف العروض النشطة
                all_o = []
                o_page = 1
                while True:
                    ores = safe_api_request("GET", f"https://api.salla.dev/admin/v2/specialoffers?per_page=60&page={o_page}", headers)
                    if not ores or not ores.get("data"): break
                    all_o.extend(ores["data"])
                    if o_page >= ores.get("pagination", {}).get("totalPages", 1): break
                    o_page += 1
                
                active_offers = [o for o in all_o if o.get("status") == "active"]
                po_map = {}
                for o in active_offers:
                    oid = o.get("id")
                    full_o = safe_api_request("GET", f"https://api.salla.dev/admin/v2/specialoffers/{oid}", headers)
                    if full_o and full_o.get("data"):
                        pids = set()
                        for px in full_o["data"].get("buy", {}).get("products", []): 
                            pids.add(str(px.get("id", px) if isinstance(px, dict) else px))
                        for px in full_o["data"].get("get", {}).get("products", []): 
                            pids.add(str(px.get("id", px) if isinstance(px, dict) else px))
                        for pid in pids:
                            if pid not in po_map: po_map[pid] = []
                            po_map[pid].append({"id": oid, "name": o.get("name")})
                st.session_state["product_offers_map"] = po_map
                st.session_state["all_products_fetched"] = True
                st.session_state["last_sync_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                st.success(f"✅ تم سحب {len(all_p)} منتج، وتحليل {len(active_offers)} عرض نشط بنجاح!")
                st.rerun()

    # ✅ عرض حالة المنتجات
    if st.session_state["all_products_fetched"]:
        col_info1, col_info2 = st.columns(2)
        with col_info1:
            st.success(f"✅ تم تحميل {len(st.session_state['all_products'])} منتج في الذاكرة")
        with col_info2:
            if st.session_state["last_sync_time"]:
                st.info(f"🕐 آخر مزامنة: {st.session_state['last_sync_time']}")
    else:
        st.warning("⚠️ يرجى الضغط على زر 'مزامنة وجلب كافة المنتجات' أولاً.")

    # =========================================================================
    # ✅ إعدادات ربط التطبيقات وإدارة الفروع (مختصر)
    # =========================================================================
    col_widget1, col_widget2 = st.columns(2)
    with col_widget1:
        with st.expander("⚙️ إعدادات ربط التطبيقات", expanded=False):
            st.info("إعدادات التوصيات وشاهدتها مؤخراً")
            # ... (كما هو موجود)
    with col_widget2:
        with st.expander("🏢 التحكم في المنتجات وكميات الفروع", expanded=False):
            st.info("قوالب المنتجات ورفع الملفات")
            # ... (كما هو موجود)

    st.divider()
    
    # ==========================================
    # ✅ مطابقة منتجات سلة مع النظام (مختصر)
    # ==========================================
    with st.expander("🔄 مطابقة منتجات سلة مع النظام", expanded=False):
        st.info("قم برفع ملف يحتوي على شيت salla و system")
        # ... (كما هو موجود)

    # ==========================================
    # ✅ 2. الفلاتر والبحث في المنتجات
    # ==========================================
    st.markdown("### 🔍 أدوات التصفية والبحث في المنتجات")
    
    all_products = st.session_state.get("all_products", [])
    
    if not all_products:
        st.warning("⚠️ لم يتم تحميل المنتجات بعد. الرجاء الضغط على زر المزامنة أولاً.")
        return
    
    st.info(f"📊 إجمالي عدد المنتجات المحملة في الذاكرة: {len(all_products)} منتج")
    
    with st.expander("⚙️ إعدادات التحميل والأداء", expanded=False):
        st.info("تحسينات الأداء: عند تحديث منتج واحد، يتم تحديث البيانات في الذاكرة مباشرة")
        col_perf1, col_perf2 = st.columns(2)
        with col_perf1:
            if st.button("🔄 إعادة تحميل المنتجات (كامل)", use_container_width=True):
                st.session_state["all_products_fetched"] = False
                st.rerun()
        with col_perf2:
            if st.button("🗑️ مسح الذاكرة المؤقتة", use_container_width=True):
                st.session_state["all_products"] = []
                st.session_state["all_products_fetched"] = False
                st.success("✅ تم مسح الذاكرة المؤقتة")
                st.rerun()
            
    c_search, _ = st.columns([3, 1])
    with c_search:
        search_query = st.text_input("ابحث عن منتج (اسم، SKU، ID):", placeholder="أدخل اسم المنتج، أو الرقم التعريفي...")
    
    st.markdown("#### 🎯 فلاتر سريعة:")
    f_col1, f_col2, f_col3, f_col4, f_col5, f_col6 = st.columns(6)
    with f_col1: filter_hidden = st.checkbox("المنتجات المخفية", key="f_hidden")
    with f_col2: filter_no_img = st.checkbox("منتجات بدون صورة", key="f_no_img")
    with f_col3: filter_has_promo = st.checkbox("منتجات لها عنوان ترويجي", key="f_promo")
    with f_col4: filter_discounted = st.checkbox("منتجات مخفضة", key="f_discount")
    with f_col5: filter_out_stock = st.checkbox("منتجات نفذت كميتها", key="f_out")
    with f_col6: filter_group = st.checkbox("📦 مجموعات منتجات فقط", key="f_group")

    available_end_dates = set()
    for p in all_products:
        end_d = p.get('sale_end') or (p.get('sale_price', {}).get('expired_at') if isinstance(p.get('sale_price'), dict) else None)
        if end_d: available_end_dates.add(end_d[:10])
        
    date_options = ["الكل"] + sorted(list(available_end_dates))
    selected_end_date = st.selectbox("📅 اختر تاريخ نهاية التخفيض للتصفية:", date_options, key="f_end_date_select")

    st.divider()

    filtered_products = []
    for p in all_products:
        p_id = str(p.get('id', ''))
        p_name = str(p.get('name', '')).lower()
        p_sku = str(p.get('sku', '')).lower()
        
        if search_query:
            sq = search_query.lower()
            if sq not in p_name and sq not in p_sku and sq != p_id: continue
                
        if filter_hidden and p.get('status') != 'hidden': continue
        if filter_no_img and p.get('thumbnail') and p.get('main_image'): continue
        promo_obj = p.get('promotion', {})
        actual_promo_title = p.get('promotion_title') or (promo_obj.get('title') if isinstance(promo_obj, dict) else '')
        if filter_has_promo and not actual_promo_title: continue
        if filter_out_stock and p.get('quantity', 0) > 0: continue
        if filter_group and p.get('type') != 'group_products': continue
            
        has_disc = False
        pr = get_flat_price(p.get('price', 0))
        reg = get_flat_price(p.get('regular_price', 0))
        sl = get_flat_price(p.get('sale_price', 0))
        if sl > 0 and sl < (reg if reg > 0 else pr): has_disc = True
        elif reg > 0 and pr < reg: has_disc = True
            
        if filter_discounted and not has_disc: continue
        
        if selected_end_date != "الكل":
            end_d = p.get('sale_end') or (p.get('sale_price', {}).get('expired_at') if isinstance(p.get('sale_price'), dict) else None)
            if not end_d or not end_d.startswith(selected_end_date): continue
                
        filtered_products.append(p)

    st.markdown(f"**📊 عدد المنتجات المطابقة للبحث والفلترة:** {len(filtered_products)}")

    if filtered_products:
        ex_data = export_products_to_excel(filtered_products)
        st.download_button(
            label="📥 تحميل المنتجات المفلترة الحالية (Excel)",
            data=ex_data,
            file_name=f"Filtered_Products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            key="direct_export_filtered_btn",
            use_container_width=True
        )

    # ==========================================
    # ✅ 3. عرض المنتجات
    # ==========================================
    items_per_page = 20 
    total_pages = max(1, (len(filtered_products) + items_per_page - 1) // items_per_page)
    
    if st.session_state["prod_page"] > total_pages: 
        st.session_state["prod_page"] = total_pages
        
    start_idx = (st.session_state["prod_page"] - 1) * items_per_page
    end_idx = start_idx + items_per_page
    displayed_products = filtered_products[start_idx:end_idx]

    st.markdown("---")
    col_prev, col_page, col_next = st.columns([1, 2, 1])
    with col_prev:
        if st.button("⬅️ الصفحة السابقة", disabled=(st.session_state["prod_page"] == 1), use_container_width=True):
            st.session_state["prod_page"] -= 1
            st.rerun()
    with col_page:
        st.markdown(f"<h4 style='text-align:center; color:#0f1c2e;'>📄 صفحة {st.session_state['prod_page']} من {total_pages}</h4>", unsafe_allow_html=True)
    with col_next:
        if st.button("الصفحة التالية ➡️", disabled=(st.session_state["prod_page"] == total_pages), use_container_width=True):
            st.session_state["prod_page"] += 1
            st.rerun()
    st.markdown("---")

    for idx, p in enumerate(displayed_products):
        p_id = str(p.get('id', 'N/A'))
        p_name = p.get('name', 'منتج بدون اسم')
        p_sku = p.get('sku', 'لا يوجد')
        status = p.get('status', 'sale')
        p_url = p.get('url', 'https://salla.sa')
        p_image = p.get('thumbnail') or p.get('main_image')
        product_type = p.get('type', 'product')
        
        promo = p.get('promotion', {})
        p_promotion = p.get('promotion_title') or (promo.get('title') if isinstance(promo, dict) else '') or "-"
        p_sub_title = (promo.get('sub_title') if isinstance(promo, dict) else '') or "-"
        
        price_val = get_flat_price(p.get('price', 0))
        regular_val = get_flat_price(p.get('regular_price', 0))
        sale_val = get_flat_price(p.get('sale_price', 0))

        base_price = regular_val if regular_val > 0 else price_val
        if sale_val > 0 and sale_val < base_price:
            display_sale_price = sale_val
            has_discount = True
        elif price_val < regular_val and price_val > 0:
            display_sale_price = price_val
            has_discount = True
        else:
            display_sale_price = base_price
            has_discount = False

        discount_percent = int(((base_price - display_sale_price) / base_price) * 100) if has_discount and base_price > 0 else 0
        sale_start_date = p.get('sale_start') or "غير محدد"
        sale_end_date = p.get('sale_end') or "غير محدد"
        
        disp_status = "🟢 معروض بالمتجر" if status == "sale" else "🔴 مخفي في المسودات"
        tax_status_badge = "📗 خاضع للضريبة" if p.get('with_tax', True) else f"⚪ يخضع لنسبة الصفر ({p.get('tax_exemption_cause', 'بدون سبب')})"

        # ✅ أيقونة مجموعة المنتجات
        if product_type == 'group_products':
            type_badge = "<span style='background: linear-gradient(135deg, #6C2BD9 0%, #9B59B6 100%); color: white; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;'>📦 مجموعة منتجات</span>"
            border_color = "#9B59B6"
        else:
            type_badge = ""
            border_color = "#e67e22"

        # ✅ استخراج قائمة العروض المشمول بها هذا المنتج
        p_offers_list = st.session_state.get("product_offers_map", {}).get(str(p_id), [])
        
        # ✅ بناء شارة العروض
        offer_badge_html = ""
        if p_offers_list:
            offer_badge_html = f"<span style='background: linear-gradient(135deg, #FFC107 0%, #FF9800 100%); color: #1a1a2e; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:700; border: 1px solid #FFC107;'>🎁 مشمول في {len(p_offers_list)} عرض</span>"

        # ✅ شريط عنوان المنتج
        st.markdown(f"<div style='background: linear-gradient(135deg, #243b55 0%, #141e30 100%); padding: 14px 20px; border-radius: 12px 12px 0px 0px; margin-top: 25px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; border-bottom: 3px solid {border_color};'><span style='color: #ffffff; font-weight: bold; font-size: 15px;'>📦 {p_name}</span><div style='display: flex; gap: 8px; flex-wrap: wrap;'><span style='background: rgba(255,255,255,0.2); color: #fff; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;'>{disp_status}</span><span style='background: rgba(0, 235, 207, 0.2); color: #00EBCF; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;'>{tax_status_badge}</span>{type_badge}{offer_badge_html}</div></div>", unsafe_allow_html=True)
        
        with st.container(border=True):
            st.markdown("""<div style="background-color: #fafbfc; padding: 20px; border-radius: 0px 0px 12px 12px; border: 1px solid #e1e8ed; border-top: none; box-shadow: 0 4px 10px rgba(0,0,0,0.03); margin-bottom: 25px;">""", unsafe_allow_html=True)
            
            c_img, c_info, c_pricing, c_action = st.columns([1.5, 2.5, 2.5, 2])
            
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
                st.markdown(f"🔗 [🌐 عرض المنتج في المتجر]({p_url})")
            
            with c_pricing:
                if has_discount:
                    st.markdown(f"""
                        <div style="background:#fff3cd; padding:10px; border-radius:8px; border-right:5px solid #ffc107;">
                            <span style="text-decoration: line-through; color: #7f8c8d; font-size:12px;">أصلي: {base_price:,.2f} SAR</span><br>
                            <b style="color: #c0392b; font-size:15px;">مخفض: {display_sale_price:,.2f} SAR</b>
                            <span style="background:#c0392b; color:#fff; padding:2px 5px; border-radius:4px; font-size:10px; margin-right:5px;">وفرت: {discount_percent}%</span>
                        </div>
                    """, unsafe_allow_html=True)
                    st.markdown(f"📅 بداية التخفيض: `{sale_start_date}`")
                    st.markdown(f"📅 نهاية التخفيض: `{sale_end_date}`")
                else:
                    st.markdown(f"""
                        <div style="background:#e2e8f0; padding:10px; border-radius:8px; border-right:5px solid #4a5568;">
                            <b style="color:#2d3748; font-size:14px;">سعر ثابت: {base_price:,.2f} SAR</b>
                        </div>
                    """, unsafe_allow_html=True)
                
                with st.expander("💰 تحديث الأسعار", expanded=False):
                    current_product = None
                    for pr in st.session_state.get("all_products", []):
                        if str(pr.get('id')) == p_id:
                            current_product = pr
                            break
                    
                    real_base_price = get_flat_price(current_product.get('price', 0)) if current_product else base_price
                    real_sale_price = get_flat_price(current_product.get('sale_price', 0)) if current_product else display_sale_price
                    
                    st.info(f"💰 السعر الأصلي الحالي: **{real_base_price:.2f} SAR** | السعر المخفض الحالي: **{real_sale_price:.2f} SAR**")
                    
                    new_price = st.number_input("السعر الأصلي الجديد (SAR)", min_value=0.0, value=float(real_base_price), step=0.5, key=f"new_price_{p_id}_{idx}")
                    new_sale_price = st.number_input("السعر المخفض الجديد (SAR) (اترك 0 للإزالة)", min_value=0.0, value=float(real_sale_price) if real_sale_price > 0 else 0.0, step=0.5, key=f"new_sale_price_{p_id}_{idx}")
                    
                    col_date1, col_date2 = st.columns(2)
                    with col_date1:
                        if sale_start_date != "غير محدد" and sale_start_date:
                            try: default_start = datetime.strptime(sale_start_date, "%Y-%m-%d")
                            except: default_start = None
                        else: default_start = None
                        sale_start_input = st.date_input("بداية التخفيض", value=default_start, key=f"sale_start_{p_id}_{idx}", help="اترك فارغاً إذا لم يكن هناك تاريخ بداية")
                    
                    with col_date2:
                        if sale_end_date != "غير محدد" and sale_end_date:
                            try: default_end = datetime.strptime(sale_end_date, "%Y-%m-%d")
                            except: default_end = None
                        else: default_end = None
                        sale_end_input = st.date_input("نهاية التخفيض", value=default_end, key=f"sale_end_{p_id}_{idx}", help="اترك فارغاً إذا لم يكن هناك تاريخ نهاية")
                    
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        if st.button("💾 تحديث السعر الأصلي", key=f"update_price_{p_id}_{idx}", use_container_width=True):
                            if new_price <= 0: st.error("⚠️ السعر يجب أن يكون أكبر من صفر")
                            elif new_sale_price > 0 and new_price <= new_sale_price: st.error(f"⚠️ السعر الأصلي ({new_price}) يجب أن يكون أكبر من السعر المخفض ({new_sale_price})")
                            else:
                                with st.spinner("جاري التحديث..."):
                                    if update_product_price(int(p_id), new_price):
                                        st.success("✅ تم تحديث السعر الأصلي!")
                                        st.rerun()
                                    else: st.error("❌ فشل تحديث السعر")
                    
                    with col_btn2:
                        if st.button("💾 تحديث السعر المخفض", key=f"update_sale_{p_id}_{idx}", use_container_width=True):
                            if new_sale_price > 0:
                                if new_sale_price >= new_price: st.error(f"⚠️ السعر المخفض ({new_sale_price}) يجب أن يكون أقل من السعر الأصلي ({new_price})")
                                else:
                                    with st.spinner("جاري التحديث..."):
                                        start_date_str = sale_start_input.strftime("%Y-%m-%d") if sale_start_input else None
                                        end_date_str = sale_end_input.strftime("%Y-%m-%d") if sale_end_input else None
                                        if update_product_sale_price(int(p_id), new_sale_price, start_date_str, end_date_str):
                                            st.success("✅ تم تحديث السعر المخفض!")
                                            st.rerun()
                                        else: st.error("❌ فشل تحديث السعر المخفض")
                            else:
                                with st.spinner("جاري إزالة التخفيض..."):
                                    if update_product_sale_price(int(p_id), 0):
                                        st.success("✅ تم إزالة التخفيض!")
                                        st.rerun()
                                    else: st.error("❌ فشل إزالة التخفيض")
                                    
            with c_action:
                st.markdown("<br>", unsafe_allow_html=True)
                
                # ✅ زر استعراض العروض
                current_p_offers = st.session_state.get("product_offers_map", {}).get(str(p.get('id', '')), [])
                if current_p_offers:
                    with st.popover(f"🎁 العروض المشمولة ({len(current_p_offers)})", use_container_width=True):
                        st.markdown("#### 🎯 العروض النشطة المشمول بها هذا المنتج:")
                        for off in current_p_offers:
                            st.markdown(f"""
                            <div style='background: #fef9e7; padding: 8px 12px; border-radius: 8px; margin-bottom: 6px; border-right: 3px solid #FFC107;'>
                                <span style='font-weight: bold;'>🎯 {off['name']}</span>
                                <span style='font-size: 11px; color: #666;'> (ID: {off['id']})</span>
                            </div>
                            """, unsafe_allow_html=True)
                        st.caption("💡 هذه العروض تطبق تلقائياً على هذا المنتج")
                
                target_st = "hidden" if status == "sale" else "sale"
                btn_lbl = "👁️ إخفاء المنتج من المتجر" if status == "sale" else "👁️ إظهار المنتج بالمتجر"
                if st.button(btn_lbl, key=f"sh_{p_id}_{idx}", type="secondary" if status == "sale" else "primary", use_container_width=True):
                    with st.spinner("مزامنة..."):
                        if update_product_status(p_id, target_st):
                            st.success("تم التحديث!")
                            st.rerun()

                with st.popover("حذف المنتج", icon="🗑️", type="primary"):
                    st.warning("⚠️ تحذير: حذف المنتج نهائي ولا يمكن استرجاعه!")
                    st.write(f"**المنتج:** {p_name}")
                    st.write(f"**المعرف:** `{p_id}`")
                    confirm_delete = st.checkbox("☑️ أوافق على حذف هذا المنتج نهائياً", key=f"confirm_delete_{p_id}_{idx}")
                    if st.button("🗑️ حذف المنتج نهائياً", key=f"delete_{p_id}_{idx}", type="primary", disabled=not confirm_delete, use_container_width=True):
                        with st.spinner("جاري حذف المنتج..."):
                            if delete_product(int(p_id)):
                                st.success("✅ تم حذف المنتج بنجاح!")
                                if p in filtered_products: filtered_products.remove(p)
                                if p in all_products: all_products.remove(p)
                                st.rerun()
                            else: st.error("❌ فشل حذف المنتج")
                                
                with st.popover("✏️ تعديل العناوين"):
                    new_promo = st.text_input("العنوان الترويجي:", value=(p_promotion if p_promotion != "لا يوجد عنوان ترويجي" else ""), key=f"promo_in_{p_id}_{idx}")
                    new_sub = st.text_input("العنوان الفرعي:", value=(p_sub_title if p_sub_title != "لا يوجد عنوان فرعي" else ""), key=f"sub_in_{p_id}_{idx}")
                    if st.button("💾 حفظ العناوين الآمن", key=f"save_promo_{p_id}_{idx}", type="primary", use_container_width=True):
                        with st.spinner("جاري الحفظ الآمن للأسعار..."):
                            if update_product_promotions_secure(p_id, new_promo, new_sub, headers):
                                st.success("✅ تم تحديث العناوين بنجاح!")
                                st.rerun()

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
                                st.success("✅ تم تحديث حالة الضريبة!")
                                st.rerun()
                
                with st.popover("🏢 كميات الفروع"):
                    if not branches: st.warning("لا توجد فروع مسجلة.")
                    else:
                        st.markdown("**أدخل الكمية الجديدة للفرع:**")
                        branch_updates = []
                        for b in branches:
                            new_q = st.number_input(f"تحديث الكمية في: {b['name']}", min_value=0, value=0, step=1, key=f"bq_{p_id}_{b['id']}_{idx}")
                            if new_q > 0:
                                branch_updates.append({"identifer": p_sku, "identifer_type": "sku", "branch_id": b['id'], "quantity": new_q, "mode": "overwrite"})
                        if st.button("💾 حفظ كميات الفروع", key=f"save_bq_{p_id}_{idx}", type="primary", use_container_width=True):
                            if branch_updates:
                                with st.spinner("جاري التوزيع في سلة..."):
                                    res = safe_api_request("POST", "https://api.salla.dev/admin/v2/products/quantities/bulk", headers, json={"products": branch_updates})
                                    if res:
                                        st.success("✅ تم تحديث وتوزيع الكميات!")
                                        st.rerun()
                            else: st.warning("الرجاء إدخال كميات أكبر من صفر.")
            
            # ==========================================
            # ✅ عرض المنتجات داخل مجموعة المنتجات
            # ==========================================
            if product_type == 'group_products':
                st.markdown("---")
                st.markdown("#### 📦 محتويات مجموعة المنتجات")
                
                with st.spinner("جاري تحميل المنتجات المضمنة..."):
                    group_products = robust_get_group_products(int(p_id))
                
                with st.expander(f"📋 عرض وإدارة المنتجات داخل المجموعة ({len(group_products)} منتج)", expanded=False):
                    if group_products:
                        for gp_idx, gp in enumerate(group_products):
                            gp_id = str(gp.get('id', 'N/A'))
                            gp_name = gp.get('name', 'منتج بدون اسم')
                            gp_sku = gp.get('sku', 'لا يوجد')
                            gp_price = gp.get('price', 0)
                            gp_bundle_qty = gp.get('bundle_quantity', 1)
                            gp_stock = gp.get('stock_quantity', 0)
                            gp_status = gp.get('status', 'sale')
                            gp_image = gp.get('image')
                            
                            gp_status_text = "🟢 معروض" if gp_status == 'sale' else "🔴 مخفي"
                            gp_tax_text = "📗 خاضع" if gp.get('with_tax', True) else "⚪ معفى"
                            
                            # عرض المنتج الفرعي
                            st.markdown(f"""
                            <div style='background: #f8f9fa; border-radius: 10px; padding: 15px; margin-bottom: 12px; border-right: 4px solid #6C2BD9; box-shadow: 0 2px 4px rgba(0,0,0,0.05);'>
                                <div style='display: flex; align-items: center; gap: 15px; flex-wrap: wrap;'>
                                    <div style='flex: 0 0 60px;'>
                                        {f'<img src="{gp_image}" style="width: 60px; height: 60px; object-fit: cover; border-radius: 8px;">' if gp_image else '<div style="width: 60px; height: 60px; background: #e0e0e0; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 24px;">🚫</div>'}
                                    </div>
                                    <div style='flex: 1; min-width: 150px;'>
                                        <div style='font-weight: bold; font-size: 16px; color: #1a1a2e;'>{gp_name}</div>
                                        <div style='font-size: 12px; color: #666;'>
                                            🆔 {gp_id} | 🔢 {gp_sku} | 💰 {gp_price:.2f} SAR
                                        </div>
                                        <div style='display: flex; gap: 8px; margin-top: 5px; flex-wrap: wrap;'>
                                            <span style='background: {("#2ecc71" if gp_status == "sale" else "#e74c3c")}; color: white; padding: 2px 10px; border-radius: 12px; font-size: 10px; font-weight: 600;'>{gp_status_text}</span>
                                            <span style='background: {("#3498db" if gp.get("with_tax", True) else "#f39c12")}; color: white; padding: 2px 10px; border-radius: 12px; font-size: 10px; font-weight: 600;'>{gp_tax_text}</span>
                                        </div>
                                    </div>
                                    <div style='flex: 0 0 140px;'>
                                        <div style='font-size: 13px; color:#6C2BD9; font-weight:bold;'>
                                            📦 حبات بالمجموعة: {gp_bundle_qty}
                                        </div>
                                        <div style='font-size: 12px; color:#555;'>
                                            🏪 مخزون المستودع: {gp_stock}
                                        </div>
                                    </div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # أزرار التحكم
                            col_gp_qty, col_gp_actions = st.columns([1, 1])
                            with col_gp_qty:
                                new_qty = st.number_input(
                                    f"تعديل الحبات", 
                                    min_value=1, 
                                    value=int(gp_bundle_qty), 
                                    step=1, 
                                    key=f"gp_qty_{gp_id}_{idx}_{gp_idx}",
                                    label_visibility="collapsed"
                                )
                                if st.button(f"💾 تحديث الكمية", key=f"gp_update_qty_{gp_id}_{idx}_{gp_idx}", use_container_width=True):
                                    with st.spinner("تحديث..."):
                                        if update_group_product_quantity(int(p_id), int(gp_id), new_qty):
                                            st.success("✅ تم تحديث الكمية!")
                                            st.rerun()
                                        else:
                                            st.error("❌ فشل التحديث")
                            
                            with col_gp_actions:
                                if gp.get('url'):
                                    st.markdown(f"[🔗 عرض المنتج]({gp.get('url')})")
                                if st.button(f"🗑️ إزالة من المجموعة", key=f"gp_remove_{gp_id}_{idx}_{gp_idx}", use_container_width=True):
                                    with st.spinner("إزالة آمنة..."):
                                        if remove_product_from_group(int(p_id), int(gp_id)):
                                            st.success("✅ تم إزالة المنتج من المجموعة!")
                                            st.rerun()
                                        else:
                                            st.error("❌ فشل الإزالة")
                            
                            st.markdown("<hr style='margin:10px 0; border:0; border-bottom:1px dashed #ddd;'>", unsafe_allow_html=True)
                    else:
                        st.info("ℹ️ لا توجد منتجات مسجلة بداخل هذه المجموعة.")
                    
                    # ✅ إضافة منتج جديد للمجموعة
                    st.markdown("#### ➕ إضافة منتج للمجموعة")
                    search_product = st.text_input(
                        "ابحث باسم أو SKU للإضافة:",
                        key=f"gp_search_{p_id}_{idx}"
                    )
                    
                    if search_product:
                        found_products = []
                        for prod in st.session_state.get("all_products", []):
                            if prod.get('id') != int(p_id):
                                prod_name = str(prod.get('name', '')).lower()
                                prod_sku = str(prod.get('sku', '')).lower()
                                search = search_product.lower()
                                if search in prod_name or search in prod_sku:
                                    found_products.append(prod)
                        
                        if found_products:
                            for prod in found_products[:5]:
                                prod_id = prod.get('id')
                                prod_name = prod.get('name')
                                prod_sku = prod.get('sku')
                                
                                col_find1, col_find2 = st.columns([3, 1])
                                with col_find1:
                                    st.markdown(f"**{prod_name}** | `{prod_sku}`")
                                with col_find2:
                                    if st.button(f"➕ إضافة", key=f"gp_add_{prod_id}_{idx}"):
                                        with st.spinner("جاري الإضافة..."):
                                            if add_product_to_group(int(p_id), prod_id):
                                                st.success("✅ تمت الإضافة بنجاح!")
                                                st.rerun()
                                            else:
                                                st.error("❌ فشل الإضافة")
                        else:
                            st.info("لا توجد منتجات مطابقة.")
            
            st.markdown("</div>", unsafe_allow_html=True)

def update_single_product_in_session(product_id: int, updated_data: Dict):
    all_products = st.session_state.get("all_products", [])
    for i, p in enumerate(all_products):
        if str(p.get('id')) == str(product_id):
            for key, value in updated_data.items():
                all_products[i][key] = value
            break
    st.session_state["all_products"] = all_products
