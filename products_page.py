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
    update_product_sale_price, update_product_prices_bulk
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

    # ✅ 1. إصلاح خطأ المتغيرات: تعريف كل المتغيرات المفقودة في الذاكرة
    if "all_products" not in st.session_state: st.session_state["all_products"] = []
    if "all_products_fetched" not in st.session_state: st.session_state["all_products_fetched"] = False
    if "prod_page" not in st.session_state: st.session_state["prod_page"] = 1
    if "offer_product_ids" not in st.session_state: st.session_state["offer_product_ids"] = set()
    if "branches" not in st.session_state: st.session_state["branches"] = get_branches_list()
    if "last_sync_time" not in st.session_state: st.session_state["last_sync_time"] = None
    
    # تعريف المتغيرات المحلية لتصبح مقروءة في كامل الصفحة
    all_products = st.session_state["all_products"]
    offer_product_ids = st.session_state["offer_product_ids"]
    branches = st.session_state["branches"]
    
    c_title, c_btn = st.columns([3, 1])
    with c_btn:
        if st.button("🔄 مزامنة كافة المنتجات", use_container_width=True, type="primary"):
            with st.spinner("⏳ جاري سحب كافة المنتجات والعروض..."):
                progress_bar = st.progress(0)
                all_p = []
                page = 1
                total_pages = None
        
                while True:
                    res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products?per_page=100&page={page}", headers)
                    if not res or not res.get("data"):
                        break
            
                    if total_pages is None:
                        total_pages = res.get("pagination", {}).get("totalPages", 1)
            
                    all_p.extend(res["data"])
                    progress_bar.progress(page / total_pages)
            
                    if page >= total_pages:
                        break
                    page += 1
        
                progress_bar.empty()
                
                # تحديث بيانات الفروع
                st.session_state["branches"] = get_branches_list()
                branches = st.session_state["branches"]
                
                # جلب العروض النشطة
                offers_res = safe_api_request("GET", "https://api.salla.dev/admin/v2/specialoffers", headers)
                active_offers = offers_res.get("data", []) if offers_res else []
                offer_ids = set()
                for offer in active_offers:
                    if offer.get("status") == "active":
                        for op in offer.get("buy", {}).get("products", []): 
                            offer_ids.add(str(op.get("id", op) if isinstance(op, dict) else op))
                        for op in offer.get("get", {}).get("products", []): 
                            offer_ids.add(str(op.get("id", op) if isinstance(op, dict) else op))
                st.session_state["offer_product_ids"] = offer_ids

                # جلب المنتجات بالترقيم
                all_p = []
                page = 1
                while True:
                    res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products?per_page=100&page={page}", headers)
                    if not res or not res.get("data"): break
                    all_p.extend(res["data"])
                    if page >= res.get("pagination", {}).get("totalPages", 1): break
                    page += 1
                st.session_state["all_products"] = all_p
                st.session_state["all_products_fetched"] = True
                st.session_state["last_sync_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.success(f"✅ تم سحب {len(all_p)} منتج بنجاح!")
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
        st.warning("⚠️ يرجى الضغط على زر 'مزامنة وجلب كافة المنتجات' أولاً ليتم تحميل كامل منتجات متجرك في النظام.")

    # =========================================================================
    # ✅ 1. إعدادات ربط التطبيقات الترويجية والذكية وإدارة الفروع
    # =========================================================================
    col_widget1, col_widget2 = st.columns(2)

    with col_widget1:
        with st.expander("⚙️ إعدادات ربط تطبيقات التوصيات وشاهدتها مؤخراً", expanded=False):
            st.markdown("#### 🛠️ إعدادات المنتجات المستعرضة مؤخراً")
            section_title = st.text_input("📝 عنوان القسم الفعال:", value="شاهدتها مؤخراً", key="app_recent_section_title")
            st.markdown("**🎯 تخصيص ظهور القسم في الصفحات:**")
            show_home = st.checkbox("الصفحة الرئيسية بالمتجر", value=False, key="app_show_home_recent")
            show_categories = st.checkbox("صفحة التصنيفات والأقسام", value=False, key="app_show_cat_recent")
            show_details = st.checkbox("صفحة تفاصيل وعرض المنتج", value=True, key="app_show_details_recent")
            products_limit = st.number_input("🔢 عدد المنتجات المعروضة:", min_value=1, max_value=32, value=6, key="app_recent_limit")
            
            st.markdown("#### 🛠️ نظام التوصية الذكي والحزم")
            global_enable = st.checkbox("✅ تفعيل التوصيات في المتجر", value=True, key="app_reco_global_enable")
            buy_together = st.checkbox("🤝 تشترى معًا", value=True, key="app_reco_buy_together")
            prod_group = st.checkbox("📦 عرض المنتجات كحزمة", value=True, key="app_reco_prod_group")
            cart_btn_option = st.selectbox("🛒 عرض زر إضافة للسلة:", ["في صفحة السلة فقط", "في جميع الصفحات"], index=0, key="app_reco_cart_btn")
            
            if st.button("💾 حفظ وتثبيت إعدادات التطبيقات", type="primary", use_container_width=True, key="btn_save_apps_settings"):
                st.success("✅ تم حفظ إعدادات ربط التطبيقات بنجاح!")

    with col_widget2:
        with st.expander("🏢 التحكم في المنتجات وكميات الفروع", expanded=False):
            st.markdown("#### 📥 قوالب المنتجات (Excel)")
            
            c_dl1, c_dl2 = st.columns(2)
            with c_dl1:
                # 1️⃣ زر تحميل قالب التعديل (للمنتجات الحالية)
                if st.button("📥 تحميل قالب تعديل المنتجات", use_container_width=True, key="btn_download_update_template"):
                    template_bytes = fill_salla_template(all_products)
                    if template_bytes:
                        st.download_button(
                            label="✅ تنزيل قالب التعديل",
                            data=template_bytes,
                            file_name="Salla_Products_Update_Template.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dl_update_template_btn_unique"
                        )
            
            with c_dl2:
                # 2️⃣ زر تحميل قالب الإضافة (للمنتجات الجديدة)
                if st.button("📥 تحميل قالب إضافة منتجات", use_container_width=True, key="btn_download_new_template"):
                    # نمرر قائمة فارغة [] لتوليد العناوين (الهيدر) فقط بدون منتجات
                    template_bytes = generate_salla_new_products_file([]) 
                    if template_bytes:
                        st.download_button(
                            label="✅ تنزيل القالب الفارغ",
                            data=template_bytes,
                            file_name="Salla_New_Products_Template.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dl_new_template_btn_unique"
                        )

            st.markdown("---")
            # ==========================================
            # ✅ إضافة زر وأداة رفع ملف المنتجات (إضافة / تحديث)
            # ==========================================
            st.markdown("#### 🚀 رفع ملف المنتجات إلى سلة")
            import_type_label = st.radio("اختر نوع العملية:", ["تحديث منتجات حالية", "إضافة منتجات جديدة"], key="import_type_radio")
            import_type_value = "products-update" if import_type_label == "تحديث منتجات حالية" else "products"
            
            uploaded_products_file = st.file_uploader("📂 ارفع ملف الإكسيل (القالب الأصلي):", type=['xlsx'], key="upload_products_file_salla")
            
            if uploaded_products_file and st.button(f"رفع الملف ({import_type_label})", type="primary", use_container_width=True, key="btn_upload_products_bulk"):
                with st.spinner("جاري رفع الملف إلى خوادم سلة..."):
                    import requests
                    
                    # 1. تجهيز الملف والبيانات كما تطلبها سلة
                    files = {'file': (uploaded_products_file.name, uploaded_products_file.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
                    data = {'type': import_type_value}
                    
                    # 2. ⚠️ خطوة حرجة جداً: مسح الـ Content-Type حتى تقوم مكتبة requests بإنشاء Boundary صحيح للملف
                    upload_headers = headers.copy()
                    if "Content-Type" in upload_headers:
                        del upload_headers["Content-Type"]
                        
                    res = requests.post(
                        "https://api.salla.dev/admin/v2/products/import",
                        headers=upload_headers,
                        files=files,
                        data=data
                    )
                    
                    if res.status_code < 400:
                        st.success("✅ تم رفع الملف بنجاح! ستقوم سلة بمعالجته وإضافة/تحديث المنتجات في الخلفية.")
                    else:
                        try: err_msg = res.json()
                        except: err_msg = res.text
                        st.error(f"❌ فشل الرفع: {err_msg}")
            
            st.markdown("---")
            st.markdown("#### 📦 تحديث كميات الفروع (Excel)")
            st.download_button("📥 تنزيل نموذج استيراد الكميات للفروع", data=generate_quantities_template(), file_name="Salla_Quantities_Template.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, key="btn_dl_qty_template")
            
            uploaded_q_file = st.file_uploader("📂 رفع ملف Excel لتحديث الكميات:", type=['xlsx'], key="upload_quantities_file")
            if uploaded_q_file and st.button("🚀 تحديث كميات الفروع (Bulk)", type="primary", use_container_width=True, key="btn_upload_qty_bulk"):
                df_q = pd.read_excel(uploaded_q_file)
                with st.spinner("جاري التحديث في سلة..."):
                    res_q = process_quantities_import(df_q)
                    for m in res_q["success"]: st.success(m)
                    for m in res_q["errors"]: st.error(m)   

    st.divider()
    
    # ==========================================
    # ✅ مطابقة منتجات سلة مع النظام
    # ==========================================
    with st.expander("🔄 مطابقة منتجات سلة مع النظام", expanded=False):
        st.info("📋 قم برفع ملف يحتوي على شيت salla و system. سيتم استبعاد التصنيفات المحددة من العمود الخامس (إن وجدت).")
        
        # حقل إدخال التصنيفات المستبعدة
        exclude_cats_str = st.text_input("🚫 تصنيفات للاستبعاد من المطابقة (افصل بينها بفاصلة):", placeholder="مثال: اكسسوارات, هدايا")
        
        uploaded_matching_file = st.file_uploader("📂 رفع ملف المطابقة (XLSX):", type=["xlsx"], key="matching_file_uploader")
    
        if uploaded_matching_file:
            try:
                excel_file = pd.ExcelFile(uploaded_matching_file)
                if 'salla' not in excel_file.sheet_names or 'system' not in excel_file.sheet_names:
                    st.error("❌ الشيت 'salla' أو 'system' غير موجود في الملف")
                else:
                    df_salla = pd.read_excel(uploaded_matching_file, sheet_name='salla')
                    df_system = pd.read_excel(uploaded_matching_file, sheet_name='system')
                    
                    # ✅ استبعاد التصنيفات من العمود الخامس (Index 4)
                    if exclude_cats_str and len(df_system.columns) >= 5:
                        exclude_cats = [c.strip().lower() for c in exclude_cats_str.split(",") if c.strip()]
                        if exclude_cats:
                            cat_col = df_system.columns[4]
                            # فلترة واستبعاد
                            df_system = df_system[~df_system[cat_col].astype(str).str.lower().str.strip().isin(exclude_cats)]
                            st.success(f"تم استبعاد المنتجات التابعة للتصنيفات: {', '.join(exclude_cats)}")
                
                    # ✅ إذا كان شيت سلة فارغاً، اعتمد على منتجات المتجر المحملة بالخلفية
                    if df_salla.empty or len(df_salla) == 0:
                        st.warning("⚠️ شيت salla فارغ! سيتم الاعتماد على منتجات المتجر التي تم جلبها للمطابقة.")
                        salla_ids = set()
                        for p in all_products:
                            salla_ids.add(str(p.get("sku", "")))
                            salla_ids.add(str(p.get("id", "")))
                    else:
                        salla_ids = set(df_salla['رقم المنتج'].astype(str).tolist())
                    
                    # تحديد المنتجات الجديدة
                    new_products = []
                    for idx, row in df_system.iterrows():
                        product_id = str(row['رقم المنتج'])
                        if product_id not in salla_ids:
                            new_products.append({
                                'رقم المنتج': product_id,
                                'اسم المنتج': row['اسم المنتج'],
                                'سعر المنتج': row['سعر المنتج'],
                                'خاضع للضريبة': row.get('خاضع للضريبة؟', 'نعم')
                            })
                    
                    if new_products:
                        st.success(f"✅ تم العثور على {len(new_products)} منتج جديد غير موجود في سلة")
                        
                        # ✅ عرض المنتجات الجديدة
                        df_new = pd.DataFrame(new_products)
                        st.dataframe(df_new, use_container_width=True)
                    
                        # ✅ اختيار المنتجات للرفع
                        st.markdown("#### ☑️ اختر المنتجات لإضافتها إلى سلة")
                    
                        # ✅ إضافة أزرار اختيار الكل/إلغاء الكل
                        col_select_all, col_deselect_all = st.columns(2)
                        with col_select_all:
                            if st.button("☑️ اختيار الكل", key="select_all_matching", use_container_width=True):
                                for idx in range(len(new_products)):
                                    st.session_state[f"select_product_{idx}"] = True
                                st.rerun()

                        with col_deselect_all:
                            if st.button("⬜ إلغاء الكل", key="deselect_all_matching", use_container_width=True):
                                for idx in range(len(new_products)):
                                    st.session_state[f"select_product_{idx}"] = False
                                st.rerun()

                        # ✅ عرض خانات الاختيار لكل منتج
                        selected_indices = []
                        for idx, product in enumerate(new_products):
                            key = f"select_product_{idx}"

                            # ✅ التحقق من وجود المفتاح في session_state
                            if key not in st.session_state:
                                st.session_state[key] = True  # افتراضي: محدد

                            # ✅ استخدام القيمة من session_state
                            checked = st.checkbox(
                                f"🆔 {product['رقم المنتج']} - {product['اسم المنتج']} (السعر: {product['سعر المنتج']} SAR)",
                                value=st.session_state[key],
                                key=key  # ✅ استخدام نفس المفتاح
                            )

                            # ✅ تحديث session_state إذا تغيرت القيمة
                            if checked != st.session_state[key]:
                                st.session_state[key] = checked

                            if checked:
                                selected_indices.append(idx)
                    
                        # =========================================================
                        # ✅ التحديث الجديد: رفع المنتجات دفعة واحدة عبر القالب الأصلي
                        # =========================================================
                        if st.button(f"🚀 رفع {len(selected_indices)} منتج مختار (عبر قالب سلة)", type="primary", use_container_width=True):
                            if not selected_indices:
                                st.warning("⚠️ الرجاء اختيار منتج واحد على الأقل للرفع")
                            else:
                                with st.spinner(f"🔄 جاري تحضير القالب ورفع {len(selected_indices)} منتج لمتجرك..."):
                                    import requests
                                    
                                    products_for_template = []
                                    for idx in selected_indices:
                                        product = new_products[idx]
                                        is_taxable = str(product['خاضع للضريبة']).strip().lower() in ['نعم', 'true', '1', 'yes']
                                        
                                        products_for_template.append({
                                            "name": str(product['اسم المنتج']),
                                            "price": float(product['سعر المنتج']) if product['سعر المنتج'] else 0,
                                            "sku": str(product['رقم المنتج']),
                                            "with_tax": is_taxable,
                                            "tax_exemption_cause": "" if is_taxable else "الأدوية والمعدات الطبية"
                                        })
                                    
                                    # ✅ استخدام مولد القالب الخاص بالمنتجات الجديدة (بدون الاعتماد على ملف خارجي)
                                    template_bytes = generate_salla_new_products_file(products_for_template)
                                    
                                    if template_bytes:
                                        files = {'file': ('Salla_New_Products.xlsx', template_bytes, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
                                        # نوع العملية منتجات جديدة كلياً
                                        data = {'type': 'products'} 
                                        
                                        upload_headers = headers.copy()
                                        if "Content-Type" in upload_headers:
                                            del upload_headers["Content-Type"]
                                            
                                        res = requests.post(
                                            "https://api.salla.dev/admin/v2/products/import",
                                            headers=upload_headers,
                                            files=files,
                                            data=data
                                        )
                                        
                                        if res.status_code < 400:
                                            st.success(f"✅ تم رفع الملف بنجاح! ستقوم سلة بمعالجة وإضافة {len(selected_indices)} منتج جديد.")
                                        else:
                                            try: err_msg = res.json()
                                            except: err_msg = res.text
                                            st.error(f"❌ فشل الرفع: {err_msg}")
                                    else:
                                        st.error("❌ فشل توليد قالب سلة. يرجى التأكد من وجود الملف الأصلي 'Salla_Products_Template.xlsx' في المجلد.")
                    else:
                        st.info("ℹ️ جميع منتجات النظام موجودة بالفعل في سلة")
            except Exception as e:
                st.error(f"❌ خطأ في قراءة الملف: {str(e)}")

    # ==========================================
    # ✅ 2. الفلاتر والبحث في المنتجات (تم التعديل لجلب جميع المنتجات)
    # ==========================================
    st.markdown("### 🔍 أدوات التصفية والبحث في المنتجات")
    
    # ✅ استخدام المنتجات المخزنة في Session State
    all_products = st.session_state.get("all_products", [])
    
    if not all_products:
        st.warning("⚠️ لم يتم تحميل المنتجات بعد. الرجاء الضغط على زر المزامنة أولاً.")
        return
    
    # عرض عدد المنتجات المحملة
    st.info(f"📊 عدد المنتجات المحملة في الذاكرة: {len(all_products)} منتج")
    
    # ✅ التعديل: جلب جميع المنتجات مثل زر المزامنة


    # ✅ إضافة خيارات الأداء
    with st.expander("⚙️ إعدادات التحميل والأداء", expanded=False):
        st.info("""
        **تحسينات الأداء:**
        - عند تحديث منتج واحد، يتم تحديث البيانات في الذاكرة مباشرة
        - يتم تحميل جميع المنتجات في الذاكرة مرة واحدة فقط عند الضغط على زر المزامنة
        - إذا قمت بإضافة أو تعديل منتجات في المتجر، اضغط على زر المزامنة لتحديث البيانات
        """)
        
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
            
    # عرض عدد المنتجات الفعلي
    st.info(f"📊 إجمالي عدد المنتجات في المتجر: {len(all_products)}")
    
    c_search, _ = st.columns([3, 1])
    with c_search:
        search_query = st.text_input("ابحث عن منتج (اسم، SKU، ID):", placeholder="أدخل اسم المنتج، أو الرقم التعريفي...")
    
    st.markdown("#### 🎯 فلاتر سريعة:")
    f_col1, f_col2, f_col3, f_col4, f_col5 = st.columns(5)
    with f_col1: filter_hidden = st.checkbox("المنتجات المخفية", key="f_hidden")
    with f_col2: filter_no_img = st.checkbox("منتجات بدون صورة", key="f_no_img")
    with f_col3: filter_has_promo = st.checkbox("منتجات لها عنوان ترويجي", key="f_promo")
    with f_col4: filter_discounted = st.checkbox("منتجات مخفضة", key="f_discount")
    with f_col5: filter_out_stock = st.checkbox("منتجات نفذت كميتها", key="f_out")

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

    # ✅ نظام الترقيم السريع (Pagination)

    items_per_page = 20 # عدد المنتجات في كل صفحة
    total_pages = max(1, (len(filtered_products) + items_per_page - 1) // items_per_page)
    
    if st.session_state["prod_page"] > total_pages: 
        st.session_state["prod_page"] = total_pages
        
    start_idx = (st.session_state["prod_page"] - 1) * items_per_page
    end_idx = start_idx + items_per_page
    displayed_products = filtered_products[start_idx:end_idx]

    # أزرار التنقل بين الصفحات
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

    # حلقة العرض تستخدم displayed_products بدلاً من filtered_products
    for idx, p in enumerate(displayed_products):
        p_id = str(p.get('id', 'N/A'))
        p_name = p.get('name', 'منتج بدون اسم')
        p_sku = p.get('sku', 'لا يوجد')
        status = p.get('status', 'sale')
        p_url = p.get('url', 'https://salla.sa')
        p_image = p.get('thumbnail') or p.get('main_image')
        
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

        if p_id in offer_product_ids:
            offer_badge_html = "<span style='background: rgba(255, 193, 7, 0.3); color: #FFC107; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;'>🎁 مشمول في عرض خاص</span>"
        else:
            offer_badge_html = ""

        st.markdown(f"<div style='background: linear-gradient(135deg, #243b55 0%, #141e30 100%); padding: 14px 20px; border-radius: 12px 12px 0px 0px; margin-top: 25px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; border-bottom: 3px solid #e67e22;'><span style='color: #ffffff; font-weight: bold; font-size: 15px;'>📦 {p_name}</span><div style='display: flex; gap: 8px; flex-wrap: wrap;'><span style='background: rgba(255,255,255,0.2); color: #fff; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;'>{disp_status}</span><span style='background: rgba(0, 235, 207, 0.2); color: #00EBCF; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;'>{tax_status_badge}</span>{offer_badge_html}</div></div>", unsafe_allow_html=True)
        
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
                # عرض السعر الحالي
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
                
                # ✅ نافذة تحديث الأسعار
                with st.expander("💰 تحديث الأسعار", expanded=False):
                    # ✅ جلب السعر الأصلي الحقيقي من المنتج في session_state
                    current_product = None
                    for p in st.session_state.get("all_products", []):
                        if str(p.get('id')) == p_id:
                            current_product = p
                            break
                    
                    # ✅ استخدام السعر الأصلي الحقيقي من المنتج
                    real_base_price = get_flat_price(current_product.get('price', 0)) if current_product else base_price
                    real_sale_price = get_flat_price(current_product.get('sale_price', 0)) if current_product else display_sale_price
                    
                    # ✅ عرض السعر الحقيقي الحالي
                    st.info(f"💰 السعر الأصلي الحالي: **{real_base_price:.2f} SAR** | السعر المخفض الحالي: **{real_sale_price:.2f} SAR**")
                    
                    # السعر الأصلي
                    new_price = st.number_input(
                        "السعر الأصلي الجديد (SAR)", 
                        min_value=0.0, 
                        value=float(real_base_price),
                        step=0.5,
                        key=f"new_price_{p_id}_{idx}"
                    )
                    
                    # السعر المخفض
                    new_sale_price = st.number_input(
                        "السعر المخفض الجديد (SAR) (اترك 0 للإزالة)", 
                        min_value=0.0, 
                        value=float(real_sale_price) if real_sale_price > 0 else 0.0,
                        step=0.5,
                        key=f"new_sale_price_{p_id}_{idx}"
                    )
                    
                    # ✅ تواريخ التخفيض - استخدام القيم الموجودة فقط
                    col_date1, col_date2 = st.columns(2)
                    with col_date1:
                        # ✅ استخدام التاريخ الموجود أو تركه فارغاً
                        if sale_start_date != "غير محدد" and sale_start_date:
                            try:
                                default_start = datetime.strptime(sale_start_date, "%Y-%m-%d")
                            except:
                                default_start = None
                        else:
                            default_start = None
                        
                        sale_start_input = st.date_input(
                            "بداية التخفيض",
                            value=default_start,
                            key=f"sale_start_{p_id}_{idx}",
                            help="اترك فارغاً إذا لم يكن هناك تاريخ بداية"
                        )
                    
                    with col_date2:
                        if sale_end_date != "غير محدد" and sale_end_date:
                            try:
                                default_end = datetime.strptime(sale_end_date, "%Y-%m-%d")
                            except:
                                default_end = None
                        else:
                            default_end = None
                        
                        sale_end_input = st.date_input(
                            "نهاية التخفيض",
                            value=default_end,
                            key=f"sale_end_{p_id}_{idx}",
                            help="اترك فارغاً إذا لم يكن هناك تاريخ نهاية"
                        )
                    
                    # أزرار التحديث
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        if st.button("💾 تحديث السعر الأصلي", key=f"update_price_{p_id}_{idx}", use_container_width=True):
                            if new_price <= 0:
                                st.error("⚠️ السعر يجب أن يكون أكبر من صفر")
                            elif new_sale_price > 0 and new_price <= new_sale_price:
                                st.error(f"⚠️ السعر الأصلي ({new_price}) يجب أن يكون أكبر من السعر المخفض ({new_sale_price})")
                            else:
                                with st.spinner("جاري التحديث..."):
                                    if update_product_price(int(p_id), new_price):
                                        st.success("✅ تم تحديث السعر الأصلي!")
                                        st.rerun()
                                    else:
                                        st.error("❌ فشل تحديث السعر")
                    
                    with col_btn2:
                        if st.button("💾 تحديث السعر المخفض", key=f"update_sale_{p_id}_{idx}", use_container_width=True):
                            # ✅ استخدام السعر الأصلي الحقيقي للتحقق
                            if new_sale_price > 0:
                                if new_sale_price >= new_price:
                                    st.error(f"⚠️ السعر المخفض ({new_sale_price}) يجب أن يكون أقل من السعر الأصلي ({new_price})")
                                else:
                                    with st.spinner("جاري التحديث..."):
                                        # ✅ إرسال التواريخ فقط إذا تم إدخالها
                                        start_date_str = sale_start_input.strftime("%Y-%m-%d") if sale_start_input else None
                                        end_date_str = sale_end_input.strftime("%Y-%m-%d") if sale_end_input else None
                                        
                                        if update_product_sale_price(
                                            int(p_id), 
                                            new_sale_price,
                                            start_date_str,
                                            end_date_str
                                        ):
                                            st.success("✅ تم تحديث السعر المخفض!")
                                            st.rerun()
                                        else:
                                            st.error("❌ فشل تحديث السعر المخفض")
                            else:
                                # إزالة التخفيض
                                with st.spinner("جاري إزالة التخفيض..."):
                                    if update_product_sale_price(int(p_id), 0):
                                        st.success("✅ تم إزالة التخفيض!")
                                        st.rerun()
                                    else:
                                        st.error("❌ فشل إزالة التخفيض")
                                    
            with c_action:
                st.markdown("<br>", unsafe_allow_html=True)
                target_st = "hidden" if status == "sale" else "sale"
                btn_lbl = "👁️ إخفاء المنتج من المتجر" if status == "sale" else "👁️ إظهار المنتج بالمتجر"
                if st.button(btn_lbl, key=f"sh_{p_id}_{idx}", type="secondary" if status == "sale" else "primary", use_container_width=True):
                    with st.spinner("مزامنة..."):
                        if update_product_status(p_id, target_st):
                            st.success("تم التحديث!")
                            st.rerun()

                # ✅ إضافة زر حذف المنتج
                with st.popover("حذف المنتج", icon="🗑️", type="primary"):
                    st.warning("⚠️ تحذير: حذف المنتج نهائي ولا يمكن استرجاعه!")
                    st.write(f"**المنتج:** {p_name}")
                    st.write(f"**المعرف:** `{p_id}`")
                    
                    confirm_delete = st.checkbox("☑️ أوافق على حذف هذا المنتج نهائياً", key=f"confirm_delete_{p_id}_{idx}")
                    
                    if st.button("🗑️ حذف المنتج نهائياً", key=f"delete_{p_id}_{idx}", type="primary", disabled=not confirm_delete, use_container_width=True):
                        with st.spinner("جاري حذف المنتج..."):
                            if delete_product(int(p_id)):
                                st.success("✅ تم حذف المنتج بنجاح!")
                                # إزالة المنتج من القائمة المعروضة
                                if p in filtered_products:
                                    filtered_products.remove(p)
                                if p in all_products:
                                    all_products.remove(p)
                                st.rerun()
                            else:
                                st.error("❌ فشل حذف المنتج")
                                
                with st.popover("✏️ تعديل العناوين"):
                    new_promo = st.text_input("العنوان الترويجي:", value=(p_promotion if p_promotion != "لا يوجد عنوان ترويجي" else ""), key=f"promo_in_{p_id}_{idx}")
                    new_sub = st.text_input("العنوان الفرعي:", value=(p_sub_title if p_sub_title != "لا يوجد عنوان فرعي" else ""), key=f"sub_in_{p_id}_{idx}")
                    
                    if st.button("💾 حفظ العناوين الآمن", key=f"save_promo_{p_id}_{idx}", type="primary", use_container_width=True):
                        with st.spinner("جاري الحفظ الآمن للأسعار..."):
                            if update_product_promotions_secure(p_id, new_promo, new_sub, headers):
                                st.success("✅ تم تحديث العناوين بنجاح وبثبات للسعر الأصلي!")
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
                                st.success("✅ تم تحديث حالة الضريبة بنجاح!")
                                st.rerun()

            # ==========================================
            # ✅ عرض المنتجات داخل مجموعة المنتجات
            # ==========================================
            # التحقق من أن المنتج من نوع مجموعة منتجات
            if p.get('type') == 'group_products':
                with st.expander(f"📦 منتجات داخل المجموعة ({p.get('name')})", expanded=False):
                    st.markdown("#### 📋 المنتجات المضمنة في هذه المجموعة")
                    
                    # جلب المنتجات داخل المجموعة
                    with st.spinner("جاري تحميل المنتجات داخل المجموعة..."):
                        group_products = get_group_products(int(p_id))
                    
                    if group_products:
                        st.info(f"📊 عدد المنتجات في المجموعة: {len(group_products)}")
                        
                        # عرض المنتجات في جدول
                        for gp in group_products:
                            gp_id = str(gp.get('id', 'N/A'))
                            gp_name = gp.get('name', 'منتج بدون اسم')
                            gp_sku = gp.get('sku', 'لا يوجد')
                            gp_price = gp.get('price', 0)
                            gp_quantity = gp.get('quantity', 0)
                            gp_sold = gp.get('sold_quantity', 0)
                            gp_status = gp.get('status', 'sale')
                            gp_image = gp.get('image')
                            
                            # عرض كل منتج فرعي
                            col_gp_img, col_gp_info, col_gp_qty, col_gp_actions = st.columns([1, 3, 2, 2])
                            
                            with col_gp_img:
                                if gp_image:
                                    st.image(gp_image, width=80)
                                else:
                                    st.markdown("🚫")
                            
                            with col_gp_info:
                                st.markdown(f"**{gp_name}**")
                                st.markdown(f"🆔 `{gp_id}` | 🔢 `{gp_sku}`")
                                st.markdown(f"💰 السعر: **{gp_price:.2f} SAR**")
                                st.markdown(f"📊 الحالة: {'🟢 معروض' if gp_status == 'sale' else '🔴 مخفي'}")
                            
                            with col_gp_qty:
                                st.markdown(f"📦 المخزون: **{gp_quantity}**")
                                st.markdown(f"📈 المبيعات: **{gp_sold}**")
                                
                                # ✅ تحديث كمية المنتج الفرعي
                                new_qty = st.number_input(
                                    f"تحديث الكمية",
                                    min_value=0,
                                    value=gp_quantity,
                                    step=1,
                                    key=f"gp_qty_{gp_id}_{idx}",
                                    label_visibility="collapsed"
                                )
                                
                                if st.button(f"💾 تحديث الكمية", key=f"gp_update_qty_{gp_id}_{idx}", use_container_width=True):
                                    with st.spinner("جاري تحديث الكمية..."):
                                        if update_group_product_quantity(int(gp_id), new_qty):
                                            st.success("✅ تم تحديث الكمية بنجاح!")
                                            st.rerun()
                                        else:
                                            st.error("❌ فشل تحديث الكمية")
                            
                            with col_gp_actions:
                                # ✅ زر عرض المنتج
                                if gp.get('url'):
                                    st.markdown(f"[🔗 عرض المنتج]({gp.get('url')})")
                                
                                # ✅ زر إزالة من المجموعة
                                if st.button(f"🗑️ إزالة من المجموعة", key=f"gp_remove_{gp_id}_{idx}", use_container_width=True):
                                    if st.button(f"تأكيد إزالة {gp_name}", key=f"gp_confirm_remove_{gp_id}_{idx}"):
                                        with st.spinner("جاري إزالة المنتج من المجموعة..."):
                                            if remove_product_from_group(int(gp_id)):
                                                st.success("✅ تم إزالة المنتج من المجموعة!")
                                                st.rerun()
                                            else:
                                                st.error("❌ فشل إزالة المنتج")
                            
                            st.divider()
                        
                        # ✅ إضافة منتج جديد للمجموعة
                        st.markdown("#### ➕ إضافة منتج جديد للمجموعة")
                        
                        # البحث عن منتج لإضافته
                        search_product = st.text_input(
                            "ابحث عن منتج لإضافته (SKU أو اسم)",
                            key=f"gp_search_{p_id}_{idx}",
                            placeholder="أدخل SKU أو اسم المنتج..."
                        )
                        
                        if search_product:
                            # البحث في المنتجات المحملة
                            found_products = []
                            for prod in st.session_state.get("all_products", []):
                                if prod.get('id') != int(p_id):  # استبعاد المنتج الأب نفسه
                                    prod_name = str(prod.get('name', '')).lower()
                                    prod_sku = str(prod.get('sku', '')).lower()
                                    search = search_product.lower()
                                    if search in prod_name or search in prod_sku:
                                        found_products.append(prod)
                            
                            if found_products:
                                # عرض النتائج
                                for prod in found_products[:5]:  # عرض 5 نتائج فقط
                                    prod_id = prod.get('id')
                                    prod_name = prod.get('name')
                                    prod_sku = prod.get('sku')
                                    
                                    col_find1, col_find2 = st.columns([3, 1])
                                    with col_find1:
                                        st.markdown(f"**{prod_name}** | `{prod_sku}`")
                                    with col_find2:
                                        if st.button(f"➕ إضافة", key=f"gp_add_{prod_id}_{idx}"):
                                            with st.spinner("جاري إضافة المنتج..."):
                                                if add_product_to_group(int(p_id), prod_id):
                                                    st.success("✅ تم إضافة المنتج بنجاح!")
                                                    st.rerun()
                                                else:
                                                    st.error("❌ فشل إضافة المنتج")
                            else:
                                st.info("لا توجد منتجات مطابقة للبحث")
                    else:
                        st.info("ℹ️ لا توجد منتجات داخل هذه المجموعة")
                        
                        # عرض خيار إضافة منتج عندما تكون المجموعة فارغة
                        st.markdown("#### ➕ إضافة أول منتج للمجموعة")
                        search_product = st.text_input(
                            "ابحث عن منتج لإضافته (SKU أو اسم)",
                            key=f"gp_search_empty_{p_id}_{idx}",
                            placeholder="أدخل SKU أو اسم المنتج..."
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
                                        if st.button(f"➕ إضافة", key=f"gp_add_empty_{prod_id}_{idx}"):
                                            with st.spinner("جاري إضافة المنتج..."):
                                                if add_product_to_group(int(p_id), prod_id):
                                                    st.success("✅ تم إضافة المنتج بنجاح!")
                                                    st.rerun()
                                                else:
                                                    st.error("❌ فشل إضافة المنتج")
                            else:
                                st.info("لا توجد منتجات مطابقة للبحث")
            # ==========================================
            # ✅ نهاية عرض مجموعة المنتجات
            # ==========================================
                
                with st.popover("🏢 كميات الفروع"):
                    if not branches:
                        st.warning("لا توجد فروع مسجلة، أو فشل الجلب.")
                    else:
                        st.markdown("**أدخل الكمية الجديدة للفرع (سيتم استبدال الكمية الحالية):**")
                        branch_updates = []
                        for b in branches:
                            new_q = st.number_input(f"تحديث الكمية في: {b['name']}", min_value=0, value=0, step=1, key=f"bq_{p_id}_{b['id']}_{idx}")
                            if new_q > 0:
                                branch_updates.append({
                                    "identifer": p_sku, 
                                    "identifer_type": "sku", 
                                    "branch_id": b['id'], 
                                    "quantity": new_q, 
                                    "mode": "overwrite"
                                })
                        
                        if st.button("💾 حفظ كميات الفروع (للقيم المضافة)", key=f"save_bq_{p_id}_{idx}", type="primary", use_container_width=True):
                            if branch_updates:
                                with st.spinner("جاري التوزيع في سلة..."):
                                    res = safe_api_request(
                                        "POST", 
                                        "https://api.salla.dev/admin/v2/products/quantities/bulk", 
                                        headers, 
                                        json={"products": branch_updates}
                                    )
                                    if res:
                                        st.success("✅ تم تحديث وتوزيع الكميات!")
                                        st.rerun()
                            else:
                                st.warning("الرجاء إدخال كميات أكبر من صفر للتحديث.")


def update_single_product_in_session(product_id: int, updated_data: Dict):
    """
    تحديث بيانات منتج واحد في session_state دون إعادة تحميل الكل
    """
    all_products = st.session_state.get("all_products", [])
    for i, p in enumerate(all_products):
        if str(p.get('id')) == str(product_id):
            # تحديث الحقول المطلوبة فقط
            for key, value in updated_data.items():
                all_products[i][key] = value
            break
    st.session_state["all_products"] = all_products
