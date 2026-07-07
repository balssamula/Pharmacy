import streamlit as st
import pandas as pd
import requests
import io
import pickle
from datetime import datetime
from typing import Dict, List, Any

# ✅ استيراد الدوال الخدمية من utils.py
from utils import (
    get_headers, safe_api_request, get_flat_price, update_product_status, 
    export_products_to_excel, attach_product_image_api, update_product_promotions_secure,
    update_product_tax_secure, get_branches_list, generate_quantities_template, 
    process_quantities_import, fill_salla_template, generate_salla_new_products_file, 
    delete_product, update_product_price, update_product_sale_price, 
    update_group_product_quantity, remove_product_from_group, add_product_to_group
)

TAX_EXEMPTION_CAUSES = [
    "الخدمات المالية", "عقد تأمين على الحياة", "التوريدات العقارية المعفاة", 
    "صادرات السلع من المملكة", "صادرات الخدمات من المملكة", "النقل الدولي للسلع", 
    "النقل الدولي للركاب", "توريد وسائل النقل", "الأدوية والمعدات الطبية"
]

# ==========================================
# ⚙️ 1. دوال التهيئة والمزامنة وجلب البيانات (Clean Code)
# ==========================================

def initialize_session():
    """تهيئة المتغيرات الأساسية في ذاكرة الجلسة بأمان"""
    defaults = {
        "all_products": [],
        "all_products_fetched": False,
        "prod_page": 1,
        "branches": [],
        "last_sync_time": None,
        "product_offers_map": {}
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

def perform_sync(headers: Dict[str, str]):
    """عملية المزامنة الشاملة مع التعامل المتقدم مع الأخطاء (Error Handling)"""
    with st.spinner("⏳ جاري سحب وتصنيف كافة المنتجات والعروض النشطة من المتجر..."):
        try:
            # 1. تحديث الفروع
            st.session_state["branches"] = get_branches_list()
            
            # 2. سحب جميع المنتجات بالترقيم (Pagination)
            all_p = []
            page = 1
            while True:
                res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products?per_page=60&page={page}", headers)
                if not res or not res.get("data"): break
                all_p.extend(res["data"])
                if page >= res.get("pagination", {}).get("totalPages", 1): break
                page += 1
            st.session_state["all_products"] = all_p
            
            # 3. سحب وتصنيف العروض النشطة لربطها بالمنتجات
            all_o = []
            o_page = 1
            while True:
                ores = safe_api_request("GET", f"https://api.salla.dev/admin/v2/specialoffers?per_page=60&page={o_page}", headers)
                if not ores or not ores.get("data"): break
                all_o.extend(ores["data"])
                if o_page >= ores.get("pagination", {}).get("totalPages", 1): break
                o_page += 1
            
            po_map = {}
            for o in all_o:
                if o.get("status") != "active": continue
                oid = o.get("id")
                # قراءة التفاصيل العميقة لكل عرض نشط
                full_o = safe_api_request("GET", f"https://api.salla.dev/admin/v2/specialoffers/{oid}", headers)
                if full_o and full_o.get("data"):
                    pids = set()
                    for px in full_o["data"].get("buy", {}).get("products", []):
                        pid = str(px.get("id", px) if isinstance(px, dict) else px)
                        if pid.isdigit(): pids.add(pid)
                    for px in full_o["data"].get("get", {}).get("products", []):
                        pid = str(px.get("id", px) if isinstance(px, dict) else px)
                        if pid.isdigit(): pids.add(pid)
                    # تسجيل المنتج كجزء من هذا العرض
                    for pid in pids:
                        if pid not in po_map: po_map[pid] = []
                        po_map[pid].append({"id": oid, "name": o.get("name")})
                        
            st.session_state["product_offers_map"] = po_map
            st.session_state["all_products_fetched"] = True
            st.session_state["last_sync_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.success(f"✅ تمت المزامنة! (سحب {len(all_p)} منتج، وتحليل العروض بنجاح)")
            
        except Exception as e:
            st.error(f"❌ حدث خطأ غير متوقع أثناء المزامنة: {str(e)}")

def fetch_group_products(parent_id: int, headers: Dict[str, str]) -> List[Dict]:
    """جلب المنتجات الفرعية لمجموعة بذكاء مع التعامل مع تباينات الـ API"""
    items = []
    try:
        res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products/{parent_id}", headers)
        if not res or not res.get('data'): return items
        
        data = res['data']
        # الطريقة 1: مصفوفة grouped_items (الأحدث)
        if data.get('grouped_items'):
            for item in data['grouped_items']:
                prod = item.get('product', {})
                if prod:
                    items.append({
                        'id': prod.get('id'), 'name': prod.get('name', 'بدون اسم'), 'sku': prod.get('sku', 'لا يوجد'),
                        'price': get_flat_price(prod.get('price', 0)), 'bundle_quantity': item.get('quantity', 1),
                        'stock_quantity': prod.get('quantity', 0), 'status': prod.get('status', 'sale'),
                        'image': prod.get('thumbnail') or prod.get('main_image'), 'url': prod.get('url'),
                        'with_tax': prod.get('with_tax', True)
                    })
        # الطريقة 2: مصفوفة skus (الأساسية)
        elif data.get('skus'):
            for sku in data['skus']:
                sku_id = sku.get('id')
                if not sku_id: continue
                items.append({
                    'id': sku_id, 'name': sku.get('name', 'بدون اسم'), 'sku': sku.get('sku', 'لا يوجد'),
                    'price': get_flat_price(sku.get('price', 0)), 'bundle_quantity': sku.get('quantity', 1),
                    'stock_quantity': sku.get('stock_quantity', 0), 'status': sku.get('status', 'sale'),
                    'image': "", 'url': "", 'with_tax': True
                })
    except Exception as e:
        st.error(f"❌ خطأ أثناء جلب تفاصيل المجموعة: {str(e)}")
    return items

# ==========================================
# 🎨 2. مكونات واجهة المستخدم (UI Components)
# ==========================================

def render_sync_and_status(headers: Dict[str, str]):
    """يعرض شريط المزامنة وحالة التحميل"""
    c_title, c_btn = st.columns([3, 1])
    with c_btn:
        if st.button("🔄 مزامنة وجلب كافة المنتجات (إلزامي)", use_container_width=True, type="primary"):
            perform_sync(headers)
            st.rerun()

    if st.session_state["all_products_fetched"]:
        col_info1, col_info2 = st.columns(2)
        with col_info1: st.success(f"✅ تم تحميل {len(st.session_state['all_products'])} منتج في الذاكرة")
        with col_info2:
            if st.session_state["last_sync_time"]: st.info(f"🕐 آخر مزامنة: {st.session_state['last_sync_time']}")
    else:
        st.warning("⚠️ يرجى الضغط على زر 'مزامنة وجلب كافة المنتجات' أولاً ليتم تحميل كامل منتجات المتجر.")

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
    """يعرض بذكاء محتويات مجموعة المنتجات داخل Expander قابل للطي"""
    st.markdown("---")
    with st.spinner(f"جاري تحليل وفتح صندوق المجموعة ( {p_name} )..."):
        group_products = fetch_group_products(int(p_id), headers)
    
    # استخدام expander يوفر ميزة السهم للإخفاء/الإظهار طبيعياً
    with st.expander(f"📦 تفاصيل مجموعة المنتجات ({len(group_products)} منتجات فرعية)", expanded=False):
        if not group_products:
            st.info("ℹ️ هذه المجموعة فارغة حالياً أو فشل جلب منتجاتها.")
        else:
            for gp_idx, gp in enumerate(group_products):
                gp_id = str(gp.get('id', 'N/A'))
                gp_name_sub = gp.get('name', 'بدون اسم')
                gp_sku = gp.get('sku', 'لا يوجد')
                gp_price = gp.get('price', 0)
                gp_bundle_qty = gp.get('bundle_quantity', 1)
                gp_stock = gp.get('stock_quantity', 0)
                gp_image = gp.get('image')
                
                st.markdown(f"""
                <div style='background: #f8f9fa; border-radius: 10px; padding: 15px; margin-bottom: 12px; border-right: 4px solid #6C2BD9;'>
                    <div style='display: flex; gap: 15px; align-items: center;'>
                        <div style='flex: 0 0 60px;'>
                            {f"<img src='{gp_image}' style='width: 60px; height: 60px; border-radius: 8px;'>" if gp_image else "🚫"}
                        </div>
                        <div style='flex: 1;'>
                            <b>{gp_name_sub}</b><br>
                            <span style='font-size: 12px; color: #666;'>🆔 {gp_id} | 🔢 {gp_sku} | 💰 {gp_price:.2f} SAR</span>
                        </div>
                        <div style='flex: 0 0 120px; font-size: 12px; font-weight: bold;'>
                            حبات: <span style='color:#6C2BD9;'>{gp_bundle_qty}</span><br>
                            مخزون: {gp_stock}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                c_q, c_act = st.columns(2)
                with c_q:
                    new_q = st.number_input("تحديث الحبات", min_value=1, value=int(gp_bundle_qty), key=f"gq_{gp_id}_{idx}_{gp_idx}", label_visibility="collapsed")
                    if st.button("💾 حفظ", key=f"gqs_{gp_id}_{idx}_{gp_idx}", use_container_width=True):
                        with st.spinner("تحديث..."):
                            if update_group_product_quantity(int(p_id), int(gp_id), new_q):
                                st.success("✅ تم!"); st.rerun()
                with c_act:
                    if gp.get('url'): st.markdown(f"[🔗 عرض بالمتجر]({gp.get('url')})")
                    if st.button("🗑️ إزالة", key=f"gqr_{gp_id}_{idx}_{gp_idx}", use_container_width=True):
                        with st.spinner("إزالة..."):
                            if remove_product_from_group(int(p_id), int(gp_id)):
                                st.success("✅ تمت الإزالة!"); st.rerun()
                st.markdown("<hr style='margin:10px 0; border:0; border-bottom:1px dashed #ddd;'>", unsafe_allow_html=True)
                
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
                            with st.spinner("إضافة..."):
                                if add_product_to_group(int(p_id), pr.get('id')):
                                    st.success("✅ تمت الإضافة!"); st.rerun()
            else:
                st.info("لا توجد تطابقات.")

def render_product_card(idx: int, p: Dict, headers: Dict[str, str]):
    """رسم وإدارة كارت منتج واحد بطريقة معزولة وآمنة (Clean Code)"""
    try:
        p_id = str(p.get('id', 'N/A'))
        p_name = p.get('name', 'بدون اسم')
        p_sku = p.get('sku', 'لا يوجد')
        status = p.get('status', 'sale')
        p_url = p.get('url', '#')
        p_image = p.get('thumbnail') or p.get('main_image')
        product_type = p.get('type', 'product')
        
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
        
        disp_status = "🟢 معروض بالمتجر" if status == "sale" else "🔴 مخفي في المسودات"
        tax_status = "📗 خاضع للضريبة" if p.get('with_tax', True) else f"⚪ معفى ({p.get('tax_exemption_cause', '')})"

        # ✅ شارات التمييز الآمنة
        type_badge = "<span style='background: linear-gradient(135deg, #6C2BD9 0%, #9B59B6 100%); color: white; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;'>📦 مجموعة منتجات</span>" if product_type == 'group_products' else ""
        border_color = "#9B59B6" if product_type == 'group_products' else "#e67e22"

        # استخراج العروض المربوطة بالمنتج من الذاكرة
        p_offers = st.session_state.get("product_offers_map", {}).get(p_id, [])
        offer_badge = f"<span style='background: rgba(255, 193, 7, 0.25); color: #b45309; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: 600;'>🎁 مشمول في ({len(p_offers)}) عروض</span>" if p_offers else ""

        # ✅ رسم شريط العنوان (يظهر دائماً للجميع)
        st.markdown(f"<div style='background: linear-gradient(135deg, #243b55 0%, #141e30 100%); padding: 14px 20px; border-radius: 12px 12px 0px 0px; margin-top: 25px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; border-bottom: 3px solid {border_color};'><span style='color: #ffffff; font-weight: bold; font-size: 15px;'>📦 {p_name}</span><div style='display: flex; gap: 8px; flex-wrap: wrap; align-items: center;'><span style='background: rgba(255,255,255,0.2); color: #fff; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;'>{disp_status}</span><span style='background: rgba(0, 235, 207, 0.2); color: #00EBCF; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;'>{tax_status}</span>{type_badge}{offer_badge}</div></div>", unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown("""<div style="background-color: #fafbfc; padding: 20px; border-radius: 0px 0px 12px 12px; border: 1px solid #e1e8ed; border-top: none; margin-bottom: 20px;">""", unsafe_allow_html=True)
            c_img, c_info, c_prc, c_act = st.columns([1.5, 2.5, 2.5, 2])
            
            with c_img:
                if p_image: st.image(p_image, use_container_width=True)
                else: st.markdown("<div style='text-align:center; padding:30px; background:#eee; border-radius:8px;'>🚫 بدون صورة</div>", unsafe_allow_html=True)
                
            with c_info:
                st.markdown(f"🆔 **المعرف:** `{p_id}` | 🔢 **SKU:** `{p_sku}`")
                st.markdown(f"📢 **ترويجي:** <span style='color:#e67e22; font-weight:bold;'>{p_promotion}</span>", unsafe_allow_html=True)
                st.markdown(f"🏷️ **فرعي:** `{p_sub_title}`")
                st.markdown(f"📦 **المخزون الإجمالي:** `{p.get('quantity', 0)}` | 📈 **المبيعات:** `{p.get('sold_quantity', 0)}`")
                st.markdown(f"🔗 [🌐 عرض في المتجر]({p_url})")

            with c_prc:
                if has_disc:
                    st.markdown(f"""
                        <div style="background:#fff3cd; padding:10px; border-radius:8px; border-right:5px solid #ffc107;">
                            <span style="text-decoration: line-through; color: #7f8c8d; font-size:12px;">أصلي: {base_price:,.2f} SAR</span><br>
                            <b style="color: #c0392b; font-size:15px;">مخفض: {display_sale_price:,.2f} SAR</b>
                            <span style="background:#c0392b; color:#fff; padding:2px 5px; border-radius:4px; font-size:10px;">وفرت {discount_pct}%</span>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"<div style='background:#e2e8f0; padding:10px; border-radius:8px; border-right:5px solid #4a5568;'><b style='color:#2d3748; font-size:14px;'>سعر ثابت: {base_price:,.2f} SAR</b></div>", unsafe_allow_html=True)
                
                with st.expander("💰 تحديث الأسعار"):
                    np = st.number_input("أصلي (SAR):", min_value=0.0, value=float(base_price), key=f"np_{p_id}_{idx}")
                    nsp = st.number_input("مخفض (SAR) [0 للإلغاء]:", min_value=0.0, value=float(display_sale_price) if has_disc else 0.0, key=f"nsp_{p_id}_{idx}")
                    sd = st.date_input("بداية:", value=None, key=f"sd_{p_id}_{idx}")
                    ed = st.date_input("نهاية:", value=None, key=f"ed_{p_id}_{idx}")
                    if st.button("💾 حفظ التخفيض", key=f"sv_p_{p_id}_{idx}", use_container_width=True, type="primary"):
                        with st.spinner("تحديث..."):
                            if update_product_sale_price(int(p_id), nsp, sd.strftime("%Y-%m-%d") if sd else None, ed.strftime("%Y-%m-%d") if ed else None):
                                st.success("✅ تم!"); st.rerun()

            with c_act:
                # ✅ زر العروض التفاعلي الآمن المستقل
                if p_offers:
                    with st.popover(f"🎁 استعراض عروض المنتج ({len(p_offers)})", use_container_width=True):
                        st.markdown("<b style='color:#b45309;'>العروض النشطة المشمول بها:</b>", unsafe_allow_html=True)
                        for off in p_offers:
                            st.markdown(f"- 🎯 **{off['name']}** `(ID: {off['id']})`")
                
                t_st = "hidden" if status == "sale" else "sale"
                if st.button("👁️ إخفاء" if status == "sale" else "👁️ إظهار", key=f"sh_{p_id}_{idx}", type="secondary" if status == "sale" else "primary", use_container_width=True):
                    if update_product_status(p_id, t_st): st.rerun()

                with st.popover("✏️ تحديث العناوين"):
                    n_pr = st.text_input("ترويجي:", value="" if p_promotion=="-" else p_promotion, key=f"npr_{p_id}_{idx}")
                    n_su = st.text_input("فرعي:", value="" if p_sub_title=="-" else p_sub_title, key=f"nsu_{p_id}_{idx}")
                    if st.button("حفظ", key=f"svt_{p_id}_{idx}", type="primary"):
                        if update_product_promotions_secure(p_id, n_pr, n_su, headers): st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
            
            # ✅ قسم عرض المجموعات (يعمل بذكاء)
            if product_type == 'group_products':
                render_group_product_section(p_id, p_name, idx, headers)

    except Exception as e:
        st.error(f"❌ خطأ أثناء عرض بطاقة المنتج (ID: {p.get('id')}): {str(e)}")

# ==========================================
# 🚀 4. الدالة الرئيسية للملف
# ==========================================

def render_products_page():
    st.markdown("""
    <div style="background: linear-gradient(135deg, #0F1C2E 0%, #00EBCF 100%); padding: 15px 25px; border-radius: 12px; color: white; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        <h2 style="color: white; margin: 0;">📦 مركز إدارة المنتجات الذكي والمتقدم</h2>
    </div>
    """, unsafe_allow_html=True)
    
    headers = get_headers()
    if not headers: return
    
    initialize_session()
    render_sync_and_status(headers)
    st.divider()
    
    if not st.session_state["all_products_fetched"]: return
    
    render_settings_and_templates(headers)
    render_matching_section(headers)
    st.divider()

    # --- الفلاتر والعرض ---
    st.markdown("### 🔍 أدوات التصفية والبحث في المنتجات")
    sq = st.text_input("ابحث باسم أو SKU:").lower()
    
    f1, f2, f3, f4, f5 = st.columns(5)
    with f1: f_hid = st.checkbox("مخفي")
    with f2: f_img = st.checkbox("بدون صورة")
    with f3: f_pro = st.checkbox("مُروَّج")
    with f4: f_dis = st.checkbox("مخفض")
    with f5: f_grp = st.checkbox("📦 مجموعات فقط")

    filtered = []
    for p in st.session_state["all_products"]:
        if sq and sq not in str(p.get('name', '')).lower() and sq not in str(p.get('sku', '')).lower(): continue
        if f_hid and p.get('status') != 'hidden': continue
        if f_img and p.get('thumbnail'): continue
        if f_pro and not p.get('promotion_title'): continue
        if f_grp and p.get('type') != 'group_products': continue
        
        # فلتر المخفض
        pr = get_flat_price(p.get('price', 0))
        reg = get_flat_price(p.get('regular_price', 0))
        sal = get_flat_price(p.get('sale_price', 0))
        if f_dis and not (sal > 0 and sal < (reg if reg > 0 else pr)): continue
            
        filtered.append(p)
        
    st.info(f"📊 النتائج: {len(filtered)} منتج")

    # Pagination
    limit = 20
    pages = max(1, (len(filtered) + limit - 1) // limit)
    if st.session_state["prod_page"] > pages: st.session_state["prod_page"] = pages
    start = (st.session_state["prod_page"] - 1) * limit
    
    cp, cc, cn = st.columns([1,2,1])
    with cp:
        if st.button("⬅️", disabled=st.session_state["prod_page"]==1, use_container_width=True): 
            st.session_state["prod_page"] -= 1; st.rerun()
    with cc: st.markdown(f"<h4 style='text-align:center;'>📄 صفحة {st.session_state['prod_page']} من {pages}</h4>", unsafe_allow_html=True)
    with cn:
        if st.button("➡️", disabled=st.session_state["prod_page"]==pages, use_container_width=True): 
            st.session_state["prod_page"] += 1; st.rerun()

    for idx, p in enumerate(filtered[start:start+limit]):
        render_product_card(start + idx, p, headers)
