import streamlit as st
import pandas as pd
import io
import tempfile
import requests
from datetime import datetime
from utils import (
    get_headers, safe_api_request, get_flat_price, update_product_status, 
    export_products_to_excel, attach_product_image_api, update_product_promotions_secure,
    update_product_tax_secure, get_branches_list, generate_quantities_template, 
    process_quantities_import, create_products_template
)

TAX_EXEMPTION_CAUSES = ["الخدمات المالية", "عقد تأمين على الحياة", "التوريدات العقارية المعفاة", "صادرات السلع من المملكة", "صادرات الخدمات من المملكة", "النقل الدولي للسلع", "النقل الدولي للركاب", "توريد وسائل النقل", "الأدوية والمعدات الطبية"]

# ✅ في products_page.py - دالة import_products_to_salla

def import_products_to_salla(df: pd.DataFrame, import_type: str = "products-update") -> Dict:
    """استيراد المنتجات إلى سلة باستخدام /products/import"""
    results = {"success": [], "errors": []}
    headers = get_headers()
    if not headers:
        results["errors"].append("❌ الرجاء إدخال مفتاح الربط أولاً")
        return results
    
    try:
        # ✅ تحويل DataFrame إلى Excel مؤقت مع تنسيق صحيح
        output = io.BytesIO()
        
        # ✅ استخدام ExcelWriter مع engine='openpyxl' وتنسيق صحيح
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
            
            # ✅ ضبط تنسيق الأعمدة
            workbook = writer.book
            worksheet = writer.sheets['Sheet1']
            
            # ✅ ضبط عرض الأعمدة تلقائياً
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 30)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        output.seek(0)
        
        # ✅ رفع الملف إلى API سلة
        files = {
            'file': ('products.xlsx', output.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        }
        data = {
            'type': import_type  # ✅ products, prices, quantities, seo, products-update, etc.
        }
        
        response = requests.post(
            "https://api.salla.dev/admin/v2/products/import",
            headers=headers,
            files=files,
            data=data,
            timeout=60
        )
        
        if response.status_code == 201:
            results["success"].append("✅ تم استيراد المنتجات بنجاح! سيتم معالجتها في الخلفية.")
        else:
            try:
                error_data = response.json()
                results["errors"].append(f"❌ خطأ {response.status_code}: {error_data}")
            except:
                results["errors"].append(f"❌ خطأ {response.status_code}: {response.text}")
                
    except Exception as e:
        results["errors"].append(f"❌ خطأ في الاستيراد: {str(e)}")
    
    return results
    
def render_products_page():
    st.markdown("<h2 style='color:#0f1c2e;'>📦 مركز إدارة المنتجات المتقدمة</h2>", unsafe_allow_html=True)
    
    headers = get_headers()
    if not headers: return

    with st.spinner("جاري تهيئة الإعدادات..."):
        branches = get_branches_list()
        
        # ✅ جلب العروض الترويجية النشطة لتمييز المنتجات المشمولة بها
        offers_res = safe_api_request("GET", "https://api.salla.dev/admin/v2/specialoffers", headers)
        active_offers = offers_res.get("data", []) if offers_res else []
        offer_product_ids = set()
        for offer in active_offers:
            if offer.get("status") == "active":
                for p in offer.get("buy", {}).get("products", []):
                    offer_product_ids.add(str(p.get("id", p) if isinstance(p, dict) else p))
                for p in offer.get("get", {}).get("products", []):
                    offer_product_ids.add(str(p.get("id", p) if isinstance(p, dict) else p))

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
            
            if st.button("💾 حفظ وتثبيت إعدادات التطبيقات", type="primary", use_container_width=True):
                st.success("✅ تم حفظ إعدادات ربط التطبيقات بنجاح!")

    with col_widget2:
        with st.expander("🏢 التحكم في كميات ومخزون الفروع (استيراد)", expanded=False):
            st.markdown("#### 📦 إدارة وتحديث كميات الفروع جماعياً (Excel)")
            st.download_button("📥 تنزيل نموذج استيراد الكميات للفروع", data=generate_quantities_template(), file_name="Salla_Quantities_Template.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            
            uploaded_q_file = st.file_uploader("📂 رفع ملف Excel لتحديث الكميات:", type=['xlsx'], key="upload_quantities_file")
            if uploaded_q_file and st.button("🚀 تحديث كميات الفروع (Bulk)", type="primary", use_container_width=True):
                df_q = pd.read_excel(uploaded_q_file)
                with st.spinner("جاري التحديث في سلة..."):
                    res_q = process_quantities_import(df_q)
                    for m in res_q["success"]: st.success(m)
                    for m in res_q["errors"]: st.error(m)

            # ✅ زر تحميل المنتجات الحالية
            if st.button("📥 المنتجات الحالية", use_container_width=True):
                with st.spinner("🔄 جاري تحميل المنتجات..."):
                    prod_res = safe_api_request("GET", "https://api.salla.dev/admin/v2/products?per_page=200", headers)
                    if prod_res and prod_res.get("data"):
                        current_products = prod_res["data"]
                        template_data = create_products_template(current_products)
                        st.download_button(
                            label="📥 تحميل نموذج تحديث المنتجات الحالية",
                            data=template_data,
                            file_name=f"products_current_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="download_template_current"
                        )
                    else:
                        st.error("❌ فشل تحميل المنتجات")
                    
            st.download_button("📥 تحميل نموذج استيراد منتجات جديدة", data=create_products_template(), file_name="Salla_Products_Template.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

            uploaded_file = st.file_uploader("ارفع ملف المنتجات (XLSX):", type=["xlsx"], key="import_products_file")

            if uploaded_file:
                try:
                    # ✅ قراءة الملف
                    df = pd.read_excel(uploaded_file)
                    st.dataframe(df, use_container_width=True)
                    st.info(f"✅ تم تحميل {len(df)} منتج")
    
                    # ✅ عرض الأعمدة المتوقعة
                    expected_cols = ['معرف المنتج', 'SKU', 'اسم المنتج', 'النوع', 'نوع المنتج', 'حالة المنتج']
                    missing_cols = [col for col in expected_cols if col not in df.columns]
        
                    if missing_cols:
                        st.warning(f"⚠️ الأعمدة المفقودة: {', '.join(missing_cols)}")
                        st.info("💡 تأكد من استخدام النموذج الصحيح")
                    else:
                        st.success("✅ جميع الأعمدة المطلوبة موجودة")
        
                        # ✅ زر استيراد المنتجات
                        if st.button("🚀 استيراد المنتجات إلى سلة", type="primary"):
                            with st.spinner("🔄 جاري استيراد المنتجات..."):
                                try:
                                    # ✅ نسخ DataFrame للاستيراد
                                    import_df = df.copy()
                        
                                    # ✅ تحويل الأعمدة إلى الصيغة المطلوبة لسلة
                                    column_mapping = {
                                        'معرف المنتج': 'id',
                                        'SKU': 'sku',
                                        'اسم المنتج': 'name',
                                        'النوع': 'type',
                                        'نوع المنتج': 'product_type',
                                        'حالة المنتج': 'status',
                                        'السعر (SAR)': 'price',
                                        'السعر المخفض (SAR)': 'sale_price',
                                        'بداية التخفيض': 'sale_start',
                                        'نهاية التخفيض': 'sale_end',
                                        'كمية غير محدودة': 'unlimited_quantity',
                                        'خاضع للضريبة': 'with_tax',
                                        'سبب عدم الخضوع': 'tax_reason_code',
                                        'العنوان الترويجي': 'promotion_title',
                                        'العنوان الفرعي': 'promotion_subtitle'
                                    }
                        
                                    # ✅ إعادة تسمية الأعمدة
                                    import_df = import_df.rename(columns=column_mapping)
                        
                                    # ✅ معالجة قيم "نوع المنتج"
                                    product_type_mapping = {
                                        'منتج جاهز': 'product',
                                        'مجموعة منتجات': 'group_products',
                                        'بطاقة رقمية': 'codes',
                                        'منتج رقمي': 'digital',
                                        'أكل': 'food',
                                        'خدمة حسب الطلب': 'service',
                                        'منتج حجز': 'booking'
                                    }
                        
                                    if 'product_type' in import_df.columns:
                                        import_df['product_type'] = import_df['product_type'].map(product_type_mapping).fillna('product')
                        
                                    # ✅ معالجة حالة المنتج
                                    status_mapping = {
                                        'معروض': 'sale',
                                        'مخفي': 'hidden'
                                    }
                                    if 'status' in import_df.columns:
                                        import_df['status'] = import_df['status'].map(status_mapping).fillna('sale')
                        
                                    # ✅ معالجة "خاضع للضريبة"
                                    tax_mapping = {
                                        'نعم': 'true',
                                        'لا': 'false'
                                    }
                                    if 'with_tax' in import_df.columns:
                                        import_df['with_tax'] = import_df['with_tax'].map(tax_mapping).fillna('true')
                                    
                                    # ✅ معالجة "كمية غير محدودة"
                                    unlimited_mapping = {
                                        'نعم': 'true',
                                        'لا': 'false'
                                    }
                                    if 'unlimited_quantity' in import_df.columns:
                                        import_df['unlimited_quantity'] = import_df['unlimited_quantity'].map(unlimited_mapping).fillna('false')
                        
                                    # ✅ استيراد المنتجات
                                    results = import_products_to_salla(import_df, import_type="products-update")
                        
                                    for msg in results["success"]:
                                        st.success(msg)
                                    for msg in results["errors"]:
                                        st.error(msg)
                        
                                    if results["success"]:
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"❌ خطأ في المعالجة: {str(e)}")
                except Exception as e:
                    st.error(f"❌ خطأ في قراءة الملف: {str(e)}")

    st.divider()

    # ==========================================
    # ✅ مطابقة منتجات سلة مع النظام
    # ==========================================
    with st.expander("🔄 مطابقة منتجات سلة مع النظام", expanded=False):
        st.markdown("#### 🔄 مطابقة منتجات سلة مع النظام")
        st.info("""
        📋 **تعليمات المطابقة:**
        - قم برفع ملف Excel يحتوي على شيتين: `salla` و `system`
        - كل شيت يحتوي على 4 أعمدة: رقم المنتج، اسم المنتج، سعر المنتج، خاضع للضريبة؟
        - سيتم عرض المنتجات الموجودة في النظام (system) وغير الموجودة في سلة (salla)
        - يمكنك اختيار المنتجات لرفعها مباشرة كمنتجات جديدة
        """)
    
        uploaded_matching_file = st.file_uploader(
            "📂 رفع ملف المطابقة (XLSX):",
            type=["xlsx"],
            key="matching_file_uploader"
        )
    
        if uploaded_matching_file:
            try:
                # ✅ قراءة ملف Excel
                excel_file = pd.ExcelFile(uploaded_matching_file)
            
                # ✅ التحقق من وجود الشيتين
                if 'salla' not in excel_file.sheet_names:
                    st.error("❌ الشيت 'salla' غير موجود في الملف")
                elif 'system' not in excel_file.sheet_names:
                    st.error("❌ الشيت 'system' غير موجود في الملف")
                else:
                    # ✅ قراءة الشيتين
                    df_salla = pd.read_excel(uploaded_matching_file, sheet_name='salla')
                    df_system = pd.read_excel(uploaded_matching_file, sheet_name='system')
                
                    # ✅ عرض البيانات
                    st.markdown("**📊 بيانات سلة (Salla):**")
                    st.dataframe(df_salla, use_container_width=True)
                    st.caption(f"عدد المنتجات في سلة: {len(df_salla)}")
                
                    st.markdown("**📊 بيانات النظام (System):**")
                    st.dataframe(df_system, use_container_width=True)
                    st.caption(f"عدد المنتجات في النظام: {len(df_system)}")
                
                    # ✅ التحقق من الأعمدة المطلوبة
                    required_cols = ['رقم المنتج', 'اسم المنتج', 'سعر المنتج', 'خاضع للضريبة؟']
                    salla_missing = [col for col in required_cols if col not in df_salla.columns]
                    system_missing = [col for col in required_cols if col not in df_system.columns]
                
                    if salla_missing:
                        st.warning(f"⚠️ الأعمدة المفقودة في شيت salla: {', '.join(salla_missing)}")
                    if system_missing:
                        st.warning(f"⚠️ الأعمدة المفقودة في شيت system: {', '.join(system_missing)}")
                
                    if not salla_missing and not system_missing:
                        # ✅ استخراج أرقام المنتجات من سلة
                        salla_ids = set(df_salla['رقم المنتج'].astype(str).tolist())
                    
                        # ✅ تحديد المنتجات الموجودة في النظام وليس في سلة
                        new_products = []
                        for idx, row in df_system.iterrows():
                            product_id = str(row['رقم المنتج'])
                            if product_id not in salla_ids:
                                new_products.append({
                                    'رقم المنتج': product_id,
                                    'اسم المنتج': row['اسم المنتج'],
                                    'سعر المنتج': row['سعر المنتج'],
                                    'خاضع للضريبة': row['خاضع للضريبة؟']
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
                                if key not in st.session_state:
                                    st.session_state[key] = True
                            
                                checked = st.checkbox(
                                    f"🆔 {product['رقم المنتج']} - {product['اسم المنتج']} (السعر: {product['سعر المنتج']} SAR)",
                                    value=st.session_state[key],
                                    key=f"matching_check_{idx}"
                                )
                                if checked:
                                    selected_indices.append(idx)
                        
                            # ✅ زر رفع المنتجات المختارة
                            if st.button(f"🚀 رفع {len(selected_indices)} منتج مختار", type="primary", use_container_width=True):
                                if not selected_indices:
                                    st.warning("⚠️ الرجاء اختيار منتج واحد على الأقل للرفع")
                                else:
                                    with st.spinner(f"🔄 جاري رفع {len(selected_indices)} منتج..."):
                                        success_count = 0
                                        error_count = 0
                                    
                                        for idx in selected_indices:
                                            product = new_products[idx]
                                            try:
                                                # ✅ إعداد بيانات المنتج الجديد
                                                is_taxable = str(product['خاضع للضريبة']).strip().lower() in ['نعم', 'true', '1', 'yes']
                                            
                                                # ✅ استخدام 'type' الصحيح وليس 'product_type'
                                                product_data = {
                                                    "name": str(product['اسم المنتج']),
                                                    "price": float(product['سعر المنتج']) if product['سعر المنتج'] else 0,
                                                    "type": "product",  # ✅ النوع الافتراضي
                                                    "status": "sale",
                                                    "sku": f"SKU-{product['رقم المنتج']}",
                                                    "with_tax": is_taxable
                                                }
                                            
                                                # ✅ إذا كان غير خاضع للضريبة، إضافة سبب عدم الخضوع
                                                if not is_taxable:
                                                    product_data['tax_exemption_cause'] = "الأدوية والمعدات الطبية"
                                            
                                                response = safe_api_request(
                                                    "POST",
                                                    "https://api.salla.dev/admin/v2/products",
                                                    headers,
                                                    json=product_data
                                                )
                                                if response:
                                                    success_count += 1
                                                else:
                                                    error_count += 1
                                            except Exception as e:
                                                error_count += 1
                                                st.error(f"❌ خطأ في رفع المنتج {product['رقم المنتج']}: {str(e)}")
                                    
                                        st.success(f"✅ تم رفع {success_count} منتج بنجاح")
                                        if error_count > 0:
                                            st.warning(f"⚠️ فشل رفع {error_count} منتج")
                                    
                                        if success_count > 0:
                                            st.rerun()
                        else:
                            st.info("ℹ️ جميع منتجات النظام موجودة بالفعل في سلة")
            except Exception as e:
                st.error(f"❌ خطأ في قراءة الملف: {str(e)}")

    # ==========================================
    # ✅ 2. الفلاتر والبحث في المنتجات
    # ==========================================
    st.markdown("### 🔍 أدوات التصفية والبحث في المنتجات")
    
    with st.spinner("🔄 جاري تحميل المنتجات..."):
        prod_res = safe_api_request("GET", "https://api.salla.dev/admin/v2/products?per_page=100", headers)
        all_products = prod_res.get("data", []) if prod_res else []
    
    c_search, _ = st.columns([3, 1])
    with c_search:
        search_query = st.text_input("ابحث عن منتج (اسم، SKU، ID):", placeholder="أدخل اسم المنتج، أو الرقم التعريفي...")
    
    st.markdown("#### 🎯 فلاتر سريعة:")
    f_col1, f_col2, f_col3, f_col4, f_col5 = st.columns(5)
    with f_col1: filter_hidden = st.checkbox("المنتجات المخفية فقط", key="f_hidden")
    with f_col2: filter_no_img = st.checkbox("بدون صورة رئيسية", key="f_no_img")
    with f_col3: filter_has_promo = st.checkbox("يحتوي على عنوان ترويجي", key="f_promo")
    with f_col4: filter_discounted = st.checkbox("يوجد عليه خصم", key="f_discount")
    with f_col5: filter_out_stock = st.checkbox("نفذت الكمية", key="f_out")

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
        # ✅ الإصلاح الجذري لفلتر العناوين الترويجية
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
    # ✅ 3. عرض المنتجات وبطاقاتها الفردية والتعديلات
    # ==========================================
    for idx, p in enumerate(filtered_products):
        p_id = str(p.get('id', 'N/A'))
        p_name = p.get('name', 'منتج بدون اسم')
        p_sku = p.get('sku', 'لا يوجد')
        status = p.get('status', 'sale')
        p_url = p.get('url', 'https://salla.sa')
        p_image = p.get('thumbnail') or p.get('main_image')
        
        promo = p.get('promotion', {})
        p_promotion = p.get('promotion_title') or (promo.get('title') if isinstance(promo, dict) else '') or "لا يوجد عنوان ترويجي"
        p_sub_title = (promo.get('sub_title') if isinstance(promo, dict) else '') or "لا يوجد عنوان فرعي"
        
        price_val = get_flat_price(p.get('price', 0))
        regular_val = get_flat_price(p.get('regular_price', 0))
        sale_val = get_flat_price(p.get('sale_price', 0))

        base_price = regular_val if regular_val > 0 else price_val
        if sale_val > 0 and sale_val < base_price:
            display_sale_price = sale_val; has_discount = True
        elif price_val < regular_val and price_val > 0:
            display_sale_price = price_val; has_discount = True
        else:
            display_sale_price = base_price; has_discount = False

        discount_percent = int(((base_price - display_sale_price) / base_price) * 100) if has_discount and base_price > 0 else 0
        sale_start_date = p.get('sale_start') or (p.get('sale_price', {}).get('start_at') if isinstance(p.get('sale_price'), dict) else None) or "غير محدد"
        sale_end_date = p.get('sale_end') or (p.get('sale_price', {}).get('expired_at') if isinstance(p.get('sale_price'), dict) else None) or "غير محدد"
        
        disp_status = "🟢 معروض بالمتجر" if status == "sale" else "🔴 مخفي في المسودات"
        tax_status_badge = "🔥 خاضع للضريبة" if p.get('with_tax', True) else f"⚪ يخضع لنسبة الصفر ({p.get('tax_exemption_cause', 'بدون سبب')})"

        if p_id in offer_product_ids:
            offer_badge_html = "<span style='background: rgba(255, 193, 7, 0.3); color: #FFC107; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;'>🎁 مشمول في عرض خاص</span>"
        else:
            offer_badge_html = "" # نتركه فارغاً تماماً

        st.markdown(f"<div style='background: linear-gradient(135deg, #243b55 0%, #141e30 100%); padding: 14px 20px; border-radius: 12px 12px 0px 0px; margin-top: 25px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; border-bottom: 3px solid #e67e22;'><span style='color: #ffffff; font-weight: bold; font-size: 15px;'>📦 {p_name}</span><div style='display: flex; gap: 8px; flex-wrap: wrap;'><span style='background: rgba(255,255,255,0.2); color: #fff; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;'>{disp_status}</span><span style='background: rgba(0, 235, 207, 0.2); color: #00EBCF; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;'>{tax_status_badge}</span>{offer_badge_html}</div></div>", unsafe_allow_html=True)
        
        # ✅ استخدام الحاوية الأصلية من Streamlit لمنع ظهور </div> كـ نص
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
                    st.markdown(f"""<div style="background:#e2e8f0; padding:10px; border-radius:8px; border-right:5px solid #4a5568;"><b style="color:#2d3748; font-size:14px;">سعر ثابت: {base_price:,.2f} SAR</b></div>""", unsafe_allow_html=True)
                    
            with c_action:
                st.markdown("<br>", unsafe_allow_html=True)
                target_st = "hidden" if status == "sale" else "sale"
                btn_lbl = "👁️ إخفاء المنتج من المتجر" if status == "sale" else "👁️ إظهار المنتج بالمتجر"
                if st.button(btn_lbl, key=f"sh_{p_id}_{idx}", type="secondary" if status == "sale" else "primary", use_container_width=True):
                    with st.spinner("مزامنة..."):
                        if update_product_status(p_id, target_st):
                            st.success("تم التحديث!")
                            st.rerun()
                            
                with st.popover("✏️ تعديل العناوين"):
                    new_promo = st.text_input("العنوان الترويجي:", value=(p_promotion if p_promotion != "لا يوجد عنوان ترويجي" else ""), key=f"promo_in_{p_id}_{idx}")
                    new_sub = st.text_input("العنوان الفرعي:", value=(p_sub_title if p_sub_title != "لا يوجد عنوان فرعي" else ""), key=f"sub_in_{p_id}_{idx}")
                    
                    if st.button("💾 حفظ العناوين الآمن", key=f"save_promo_{p_id}_{idx}", type="primary", use_container_width=True):
                        with st.spinner("جاري الحفظ الآمن للأسعار..."):
                            if update_product_promotions_secure(p_id, new_promo, new_sub, headers):
                                st.success("✅ تم تحديث العناوين بنجاح وبثبات للسعر الأصلي!")
                                st.rerun()

                with st.popover("🧾 إعدادات الضريبة"):
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

                with st.popover("🏢 كميات الفروع"):
                    if not branches:
                        st.warning("لا توجد فروع مسجلة، أو فشل الجلب.")
                    else:
                        st.markdown("**أدخل الكمية الجديدة للفرع (سيتم استبدال الكمية الحالية):**")
                        branch_updates = []
                        for b in branches:
                            # السماح للمستخدم بإدخال الكمية الجديدة بشكل مباشر دون الخلط بين المنتجات
                            new_q = st.number_input(f"تحديث الكمية في: {b['name']}", min_value=0, value=0, step=1, key=f"bq_{p_id}_{b['id']}_{idx}")
                            if new_q > 0:
                                branch_updates.append({"identifer": p_id, "identifer_type": "id", "branch_id": b['id'], "quantity": new_q, "mode": "overwrite"})
                        
                        if st.button("💾 حفظ كميات الفروع (للقيم المضافة)", key=f"save_bq_{p_id}_{idx}", type="primary", use_container_width=True):
                            if branch_updates:
                                with st.spinner("جاري التوزيع في سلة..."):
                                    res = safe_api_request("POST", "https://api.salla.dev/admin/v2/products/quantities/bulk", headers, json={"products": branch_updates})
                                    if res:
                                        st.success("✅ تم تحديث وتوزيع الكميات!")
                                        st.rerun()
                            else:
                                st.warning("الرجاء إدخال كميات أكبر من صفر للتحديث.")

            st.markdown("</div>", unsafe_allow_html=True)
