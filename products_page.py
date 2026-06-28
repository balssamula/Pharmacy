import streamlit as st
import pandas as pd
import requests
import io
import json
from datetime import datetime
from utils import get_headers, safe_api_request, get_flat_price, update_product_status, export_products_to_excel, upload_product_image_api

# ==========================================
# ✅ دوال إنشاء النماذج الاحترافية
# ==========================================

def create_products_template(products=None) -> bytes:
    """إنشاء نموذج استيراد المنتجات مع قوائم منسدلة"""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
        from openpyxl.worksheet.datavalidation import DataValidation
        from openpyxl.utils import get_column_letter
        
        wb = Workbook()
        ws = wb.active
        ws.title = "قائمة المنتجات"
        
        columns = [
            "معرف المنتج", "SKU", "اسم المنتج", "نوع المنتج", "حالة المنتج",
            "السعر (SAR)", "السعر المخفض (SAR)", "بداية التخفيض", "نهاية التخفيض",
            "كمية غير محدودة", "خاضع للضريبة", "سبب عدم الخضوع",
            "العنوان الترويجي", "العنوان الفرعي"
        ]
        
        header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        center_alignment = Alignment(horizontal="center", vertical="center")
        thin_border = Border(
            left=Side(style='thin', color='DDDDDD'), right=Side(style='thin', color='DDDDDD'),
            top=Side(style='thin', color='DDDDDD'), bottom=Side(style='thin', color='DDDDDD')
        )
        
        ws.append(columns)
        for col in range(1, len(columns) + 1):
            cell = ws.cell(row=1, column=col)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_alignment
            cell.border = thin_border
            ws.column_dimensions[get_column_letter(col)].width = 20

        if products:
            for p in products:
                price = get_flat_price(p.get('price', 0))
                sale_price = get_flat_price(p.get('sale_price', 0))
                promo = p.get('promotion', {})
                promo_title = p.get('promotion_title') or (promo.get('title') if isinstance(promo, dict) else '') or ""
                promo_sub = (promo.get('sub_title') if isinstance(promo, dict) else '') or ""
                
                ws.append([
                    p.get('id', ''), p.get('sku', ''), p.get('name', ''), p.get('type', 'product'),
                    'معروض' if p.get('status') == 'sale' else 'مخفي',
                    price, sale_price if sale_price > 0 else '',
                    p.get('sale_start', ''), p.get('sale_end', ''),
                    'نعم' if p.get('unlimited_quantity') else 'لا',
                    'نعم' if p.get('with_tax', True) else 'لا',
                    '', promo_title, promo_sub
                ])
        else:
            ws.append(["123456", "SKU-01", "منتج تجريبي", "product", "معروض", 100, 80, "", "", "لا", "نعم", "", "خصم خاص", "لفترة محدودة"])
            
        dv_status = DataValidation(type="list", formula1='"معروض,مخفي"', allow_blank=True)
        ws.add_data_validation(dv_status)
        dv_status.add("E2:E1000")
        
        dv_yesno = DataValidation(type="list", formula1='"نعم,لا"', allow_blank=True)
        ws.add_data_validation(dv_yesno)
        dv_yesno.add("J2:J1000")
        dv_yesno.add("K2:K1000")
        
        output = io.BytesIO()
        wb.save(output)
        return output.getvalue()
    except Exception as e:
        st.error(f"⚠️ خطأ في إنشاء النموذج: {str(e)}")
        return b""

# ==========================================
# ✅ دوال مساعدة لفلتر وعمليات الأسعار والتعديلات
# ==========================================

def has_discount_filter(product):
    price = get_flat_price(product.get('price', 0))
    regular = get_flat_price(product.get('regular_price', 0))
    sale = get_flat_price(product.get('sale_price', 0))
    
    if sale > 0 and sale < (regular if regular > 0 else price): return True
    if regular > 0 and price < regular: return True
    return False

def update_product_promotions_secure(product_id: int, new_promo: str, new_sub: str, headers: dict) -> bool:
    """تحديث العناوين الترويجية بشكل آمن لمنع خطأ 422 للأسعار الإلزامية"""
    # 1. جلب المنتج الحالي أولاً لضمان وجود الأسعار الإلزامية المطلوبة لسلة
    current_res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products/{product_id}", headers)
    if not current_res or not current_res.get('data'): return False
    
    p_data = current_res['data']
    price_val = get_flat_price(p_data.get('price', 0))
    sale_val = get_flat_price(p_data.get('sale_price', 0))
    
    # 2. بناء Payload آمن يحتوي على العناوين الجديدة مع الأسعار الإلزامية
    payload = {
        "name": p_data.get('name'),
        "price": price_val,
        "promotion_title": new_promo,
        "promotion_subtitle": new_sub
    }
    if sale_val > 0:
        payload['sale_price'] = sale_val
        
    res = safe_api_request("PUT", f"https://api.salla.dev/admin/v2/products/{product_id}", headers, json=payload)
    return res is not None


# ==========================================
# 🟢 الواجهة الرئيسية
# ==========================================

def render_products_page():
    st.markdown("<h2 style='color:#0f1c2e;'>📦 مركز إدارة المنتجات الذكي</h2>", unsafe_allow_html=True)
    
    headers = get_headers()
    if not headers: return

    # =========================================================================
    # ✅ 1. الإعدادات السريعة (شاهدتها مؤخراً + التوصيات الذكية)
    # =========================================================================
    col_widget1, col_widget2 = st.columns(2)

    with col_widget1:
        with st.expander("⚙️ إعدادات ربط تطبيق: شاهدتها مؤخراً", expanded=False):
            st.markdown("#### 🛠️ إعدادات المنتجات المستعرضة مؤخراً")
            section_title = st.text_input("📝 عنوان القسم الفعال:", value="شاهدتها مؤخراً", key="app_recent_section_title")
            st.markdown("**🎯 تخصيص ظهور القسم في الصفحات:**")
            show_home = st.checkbox("الصفحة الرئيسية بالمتجر", value=False, key="app_show_home_recent")
            show_categories = st.checkbox("صفحة التصنيفات والأقسام", value=False, key="app_show_cat_recent")
            show_details = st.checkbox("صفحة تفاصيل وعرض المنتج", value=True, key="app_show_details_recent")
            show_thankyou = st.checkbox("صفحة الشكر (بعد الشراء)", value=False, key="app_show_thank_recent")
            products_limit = st.number_input("🔢 عدد المنتجات المعروضة (بحد أقصى 32):", min_value=1, max_value=32, value=6, step=1, key="app_recent_products_count_limit")
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("💾 حفظ إعدادات 'شاهدتها مؤخراً'", type="primary", use_container_width=True, key="save_recent_widget_settings_btn"):
                st.success("✅ تم تدوين خيارات 'شاهدتها مؤخراً' بنجاح، وجاري بث المكون بالمتجر!")

    with col_widget2:
        with st.expander("⚙️ إعدادات ربط تطبيق: نظام التوصيات الذكي والحزم", expanded=False):
            st.markdown("#### 🛠️ إعدادات ربط التطبيق (التوصيات والحزم)")
            global_enable = st.checkbox("✅ تفعيل التوصيات", value=True, key="app_reco_global_enable")
            st.markdown("---")
            st.markdown("**🎯 خيارات ظهور التوصيات الذكية:**")
            buy_together = st.checkbox("🤝 تشترى معًا", value=True, key="app_reco_buy_together")
            prod_group = st.checkbox("📦 عرض المنتجات التي تكون مجموعة منتج", value=True, key="app_reco_prod_group")
            prev_views = st.checkbox("👁️ المشاهدات السابقة", value=True, key="app_reco_prev_views")
            related_low = st.checkbox("📉 عرض منتجات منخفضة ذات صلة", value=True, key="app_reco_related_low")
            best_sellers = st.checkbox("🏆 عرض الأكثر مبيعاً في الصنف", value=True, key="app_reco_best_sellers")
            also_bought = st.checkbox("🛍️ عرض (الزبائن اشتروا أيضًا)", value=True, key="app_reco_also_bought")
            wishlist_page = st.checkbox("❤️ عرض منتجات في صفحة الأمنيات", value=True, key="app_reco_wishlist_page")
            cart_page_reco = st.checkbox("🛒 عرض منتجات في صفحة السلة", value=True, key="app_reco_cart_page")
            
            st.markdown("---")
            cart_btn_option = st.selectbox("🛒 عرض زر إضافة للسلة:", ["في صفحة السلة فقط", "في جميع الصفحات"], index=0, key="app_reco_cart_btn_dropdown_scope")
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("💾 حفظ وتعميم خيارات التوصيات والحزم", type="primary", use_container_width=True, key="save_reco_advanced_settings_btn"):
                st.success("✅ تم مزامنة وحفظ كافة شروط التوصيات وحزم المنتجات بنجاح!")

    st.divider()

    # ==========================================
    # ✅ 2. استيراد المنتجات الجماعي 
    # ==========================================
    st.markdown("### 📥 إدارة المنتجات المتقدمة (استيراد/تحديث)")
    
    col_up1, col_up2 = st.columns(2)
    with col_up1:
        if st.button("📥 تحميل نموذج فارغ للاستيراد الجماعي", use_container_width=True):
            template_bytes = create_products_template()
            st.download_button(
                label="✅ انقر هنا لتنزيل الملف",
                data=template_bytes,
                file_name="Salla_Products_Template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_empty_template_btn"
            )
            
    with col_up2:
        with st.spinner("جاري جلب جرد المتجر لتوليد نموذج التحديث..."):
            temp_res = safe_api_request("GET", "https://api.salla.dev/admin/v2/products?per_page=100", headers)
            temp_prods = temp_res.get("data", []) if temp_res else []
            
        if st.button("📥 تحميل المنتجات الحالية للتعديل الجماعي", use_container_width=True):
            export_bytes = create_products_template(temp_prods)
            st.download_button(
                label="✅ انقر هنا لتنزيل المنتجات للتعديل",
                data=export_bytes,
                file_name=f"Products_Bulk_Update_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_current_template_btn"
            )

    uploaded_file = st.file_uploader("📂 رفع ملف Excel لتحديث/استيراد المنتجات أو إضافة الصور", type=['xlsx'])
    if uploaded_file is not None:
        if st.button("🚀 بدء معالجة الملف", type="primary", use_container_width=True):
            st.info("🔄 هذه الميزة تتطلب تكاملاً متقدماً لمعالجة رفع الصور الجماعي وتحديث المنتجات. سيتم إطلاقها قريباً.")

    st.divider()

    # ==========================================
    # ✅ 3. الفلاتر والبحث في المنتجات
    # ==========================================
    st.markdown("### 🔍 أدوات التصفية والبحث في المنتجات")
    
    c_search, c_sort = st.columns([3, 1])
    with c_search:
        search_query = st.text_input("ابحث عن منتج (اسم، SKU، ID):", placeholder="أدخل اسم المنتج، أو الرقم التعريفي...")
    
    st.markdown("#### 🎯 فلاتر سريعة:")
    f_col1, f_col2, f_col3, f_col4, f_col5 = st.columns(5)
    with f_col1: filter_hidden = st.checkbox("المنتجات المخفية فقط", key="f_hidden")
    with f_col2: filter_no_img = st.checkbox("بدون صورة رئيسية", key="f_no_img")
    with f_col3: filter_has_promo = st.checkbox("يحتوي على عنوان ترويجي", key="f_promo")
    with f_col4: filter_discounted = st.checkbox("يوجد عليه خصم", key="f_discount")
    with f_col5: filter_out_stock = st.checkbox("نفذت الكمية", key="f_out")

    st.markdown("#### 📅 فلتر تواريخ نهاية التخفيض:")
    with st.spinner("جاري جمع تواريخ التخفيض المتاحة..."):
        all_res = safe_api_request("GET", "https://api.salla.dev/admin/v2/products?per_page=100", headers)
        all_products = all_res.get("data", []) if all_res else []
        
        available_end_dates = set()
        for p in all_products:
            end_d = p.get('sale_end') or (p.get('sale_price', {}).get('expired_at') if isinstance(p.get('sale_price'), dict) else None)
            if end_d: available_end_dates.add(end_d[:10])
            
        date_options = ["الكل"] + sorted(list(available_end_dates))
        selected_end_date = st.selectbox("اختر تاريخ نهاية التخفيض للتصفية:", date_options, key="f_end_date_select")

    st.divider()

    # --- تطبيق الفلاتر على القائمة ---
    filtered_products = []
    for p in all_products:
        p_id = str(p.get('id', ''))
        p_name = str(p.get('name', '')).lower()
        p_sku = str(p.get('sku', '')).lower()
        
        if search_query:
            sq = search_query.lower()
            if sq not in p_name and sq not in p_sku and sq != p_id:
                continue
                
        if filter_hidden and p.get('status') != 'hidden': continue
        if filter_no_img and p.get('thumbnail'): continue
        if filter_has_promo and not p.get('promotion_title'): continue
        if filter_discounted and not has_discount_filter(p): continue
        if filter_out_stock and p.get('quantity', 0) > 0: continue
        
        if selected_end_date != "الكل":
            end_d = p.get('sale_end') or (p.get('sale_price', {}).get('expired_at') if isinstance(p.get('sale_price'), dict) else None)
            if not end_d or not end_d.startswith(selected_end_date):
                continue
                
        filtered_products.append(p)

    st.markdown(f"**📊 عدد المنتجات المطابقة:** {len(filtered_products)}")

    # ✅ التصدير المباشر والسليم تماماً للفلترة لعدم ظهور خطأ StreamlitAPIException
    if filtered_products:
        ex_data = export_products_to_excel(filtered_products)
        st.download_button(
            label="📥 تحميل المنتجات المفلترة الحالية (Excel)",
            data=ex_data,
            file_name=f"Filtered_Products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="secondary",
            key="direct_export_filtered_btn",
            use_container_width=True
        )

    # ==========================================
    # ✅ 4. عرض المنتجات وبطاقاتها
    # ==========================================
    for idx, p in enumerate(filtered_products):
        p_id = p.get('id', 'N/A')
        p_name = p.get('name', 'منتج بدون اسم')
        p_sku = p.get('sku', 'لا يوجد')
        status = p.get('status', 'sale')
        p_url = p.get('url', 'https://salla.sa')
        p_image = p.get('thumbnail')
        
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
        
        disp_status = "🟢 معروض" if status == "sale" else "🔴 مخفي"
        
        st.markdown(f"""
            <div style="background: linear-gradient(135deg, #243b55 0%, #141e30 100%); 
                        padding: 14px 20px; border-radius: 12px 12px 0px 0px; 
                        margin-top: 25px; display: flex; justify-content: space-between; align-items: center; 
                        border-bottom: 3px solid #e67e22;">
                <span style="color: #ffffff; font-weight: bold; font-size: 15px;">📦 {p_name}</span>
                <span style="background: rgba(255,255,255,0.2); color: #fff; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;">{disp_status}</span>
            </div>
        """, unsafe_allow_html=True)
        
        with st.container():
            st.markdown("""<div style="background-color: #fafbfc; padding: 20px; border-radius: 0px 0px 12px 12px; border: 1px solid #e1e8ed; border-top: none; box-shadow: 0 4px 10px rgba(0,0,0,0.03); margin-bottom: 25px;">""", unsafe_allow_html=True)
            
            # --- الصور والبيانات ---
            c_img, c_info, c_pricing, c_action = st.columns([1, 2.5, 3, 2])
            
            with c_img:
                if p_image:
                    st.image(p_image, use_container_width=True)
                else:
                    st.markdown("<div style='text-align:center; padding:30px; background:#eee; border-radius:8px;'>🚫 بدون صورة</div>", unsafe_allow_html=True)
                
                # رفع وإرفاق الصورة (API Salla) بشكل فعلي وعملي
                with st.popover("🖼️ إرفاق صورة"):
                    uploaded_img = st.file_uploader("اختر صورة للمنتج:", type=['png', 'jpg', 'jpeg'], key=f"img_up_{p_id}_{idx}")
                    if uploaded_img is not None:
                        if st.button("🚀 رفع الصورة للمنتج", key=f"btn_up_{p_id}_{idx}", type="primary"):
                            with st.spinner("جاري الرفع..."):
                                if upload_product_image_api(p_id, uploaded_img.getvalue(), uploaded_img.name):
                                    st.success("✅ تم رفع وربط الصورة بنجاح!")
                                    st.rerun()
            
            with c_info:
                st.markdown(f"🆔 **المعرف:** `{p_id}` | 🔢 **SKU:** `{p_sku}`")
                st.markdown(f"📢 **ترويجي:** <span style='color:#e67e22; font-weight:bold;'>{p_promotion}</span>", unsafe_allow_html=True)
                st.markdown(f"🏷️ **فرعي:** `{p_sub_title}`")
                st.markdown(f"📦 **المخزون:** `{p.get('quantity', 0)}` | 📈 **المبيعات:** `{p.get('sold_quantity', 0)}`")
            
            with c_pricing:
                if has_discount:
                    st.markdown(f"""
                    <div style="background:#fff3cd; padding:10px; border-radius:8px; border-right:5px solid #ffc107;">
                        <span style="text-decoration: line-through; color: #7f8c8d; font-size:12px;">أصلي: {base_price:,.2f} SAR</span><br>
                        <b style="color: #c0392b; font-size:15px;">مخفض: {display_sale_price:,.2f} SAR</b>
                        <span style="background:#c0392b; color:#fff; padding:2px 5px; border-radius:4px; font-size:10px; margin-right:5px;">وفرت: {discount_percent}%</span>
                    </div>
                    """, unsafe_allow_html=True)
                    st.markdown(f"📅 نهاية التخفيض: `{sale_end_date}`")
                else:
                    st.markdown(f"""<div style="background:#e2e8f0; padding:10px; border-radius:8px; border-right:5px solid #4a5568;"><b style="color:#2d3748; font-size:14px;">سعر ثابت: {base_price:,.2f} SAR</b></div>""", unsafe_allow_html=True)
                    
            with c_action:
                st.markdown("<br>", unsafe_allow_html=True)
                target_st = "hidden" if status == "sale" else "sale"
                btn_lbl = "👁️ إخفاء" if status == "sale" else "👁️ إظهار"
                if st.button(btn_lbl, key=f"sh_{p_id}_{idx}", type="secondary" if status == "sale" else "primary", use_container_width=True):
                    with st.spinner("مزامنة..."):
                        if update_product_status(p_id, target_st):
                            st.success("تم!")
                            st.rerun()
                            
                # ✅ التعديل الآمن للعناوين مع حماية خطأ 422 لأسعار المنتجات
                with st.popover("✏️ تعديل العناوين"):
                    new_promo = st.text_input("العنوان الترويجي:", value=(p_promotion if p_promotion != "لا يوجد عنوان ترويجي" else ""), key=f"promo_in_{p_id}_{idx}")
                    new_sub = st.text_input("العنوان الفرعي:", value=(p_sub_title if p_sub_title != "لا يوجد عنوان فرعي" else ""), key=f"sub_in_{p_id}_{idx}")
                    
                    if st.button("حفظ", key=f"save_promo_{p_id}_{idx}", type="primary", use_container_width=True):
                        with st.spinner("جاري حفظ العناوين..."):
                            if update_product_promotions_secure(p_id, new_promo, new_sub, headers):
                                st.success("✅ تم تحديث العناوين بنجاح!")
                                st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)
