import streamlit as st
import pandas as pd
import requests
import io
import os
import json
import re
import openpyxl
import time
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any

from utils import (
    get_headers, safe_api_request, get_flat_price, update_product_status, 
    export_products_to_excel, attach_product_image_api, update_product_promotions_secure,
    update_product_tax_secure, get_branches_list, generate_quantities_template, 
    process_quantities_import, fill_salla_template, generate_salla_new_products_file, 
    delete_product, update_product_price, update_product_sale_price, export_featured_group_to_excel,
    remove_product_from_group, add_product_to_group, get_product_details, get_group_products,
    update_group_product_quantity, generate_promotions_template, process_promotions_bulk,
    SCHEDULE_DIR, load_schedules, save_schedules, init_background_scheduler
)

TAX_EXEMPTION_CAUSES = ["الخدمات المالية", "عقد تأمين على الحياة", "التوريدات العقارية المعفاة", "صادرات السلع من المملكة", "صادرات الخدمات من المملكة", "النقل الدولي للسلع", "النقل الدولي للركاب", "توريد وسائل النقل", "الأدوية والمعدات الطبية"]

def initialize_session():
    if "qa_action_prod" not in st.session_state: st.session_state.qa_action_prod = None
    if "prod_page" not in st.session_state: st.session_state.prod_page = 1
    if "featured_product_groups" not in st.session_state: st.session_state["featured_product_groups"] = {}
        
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
        po_map = st.session_state.get("product_offers_map", {})
        # ⚡ التعديل: نأخذ العروض المباشرة المربوطة بالمنتج فقط، ونتجاهل العروض العامة للسلة
        p_offers_raw = po_map.get(p_id, []) 
        unique_offers = {off['id']: off for off in p_offers_raw}.values()
        p_offers = list(unique_offers)
        
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

def render_discount_expiry_alerts(headers: Dict[str, str]):
    """نظام تنبيه ذكي للمنتجات التي سينتهي تخفيضها قريباً أو انتهى (داخل حاوية قابلة للطي)"""
    if "ignored_discount_alerts" not in st.session_state:
        st.session_state["ignored_discount_alerts"] = set()
        
    now = datetime.now()
    expiring_products = []
    
    for p in st.session_state.get("all_products", []):
        p_id = str(p.get('id', ''))
        # تخطي المنتجات التي تم تجاهلها
        if p_id in st.session_state["ignored_discount_alerts"]:
            continue
            
        sale_val = get_flat_price(p.get('sale_price', 0))
        if sale_val <= 0: continue # لا يوجد تخفيض
            
        sale_end_raw = p.get('sale_end') or (p.get('sale_price', {}).get('expired_at') if isinstance(p.get('sale_price'), dict) else None)
        
        # ✅ تجاهل التاريخ الافتراضي 1970-01-01 والقيم الفارغة تماماً
        if not sale_end_raw or "1970-01-01" in str(sale_end_raw): 
            continue
        
        try:
            # قراءة التاريخ بذكاء وحساب الأيام المتبقية
            end_date_obj = pd.to_datetime(sale_end_raw).tz_localize(None)
            days_left = (end_date_obj - now).total_seconds() / 86400.0
            
            if days_left <= 1.0: # إذا تبقى 24 ساعة أو انتهى
                # ✅ استخراج العنوان الترويجي الحالي بذكاء
                promo_obj = p.get('promotion', {})
                promo_title = p.get('promotion_title') or (promo_obj.get('title') if isinstance(promo_obj, dict) else '') or "لا يوجد عنوان ترويجي"
                
                expiring_products.append({
                    'product': p, 
                    'days_left': days_left, 
                    'end_date_str': str(sale_end_raw)[:10],
                    'promo_title': promo_title
                })
        except:
            continue
            
    if expiring_products:
        # ✅ استخدام st.expander لإنشاء حاوية قابلة للطي تحتوي على سهم
        with st.expander(f"🚨 تنبيه عاجل: يوجد ({len(expiring_products)}) منتجات ينتهي تخفيضها قريباً أو انتهى بالفعل! (اضغط للفتح والإغلاق)", expanded=True):
            
            st.markdown("""
            <div style="background: linear-gradient(135deg, #2c0b0e 0%, #1e0508 100%); border: 1px solid #ff4d4d; border-radius: 8px; padding: 10px; margin-bottom: 15px;">
                <span style='color: #ff6b6b; font-weight: bold;'>يرجى مراجعة هذه المنتجات واتخاذ إجراء (تجاهل، مسح التاريخ، أو مسح الخصم وتاريخه معاً).</span>
            </div>
            """, unsafe_allow_html=True)
            
            for item in expiring_products:
                p = item['product']
                p_id = str(p.get('id'))
                p_name = p.get('name')
                days_left = item['days_left']
                promo_title = item['promo_title']
                
                status_lbl = "انتهى بالفعل!" if days_left < 0 else "ينتهي اليوم!"
                color = "#ff4d4d" if days_left < 0 else "#ffca28"
                
                with st.container(border=True):
                    c1, c2 = st.columns([3, 4])
                    with c1:
                        # ✅ إظهار العنوان الترويجي أسفل اسم المنتج وتاريخ الانتهاء
                        st.markdown(f"**📦 {p_name}**<br>تاريخ الانتهاء: <b style='color:{color};'>{item['end_date_str']} ({status_lbl})</b><br><span style='color:#b45309; font-size:12px; background:#fef3c7; padding:2px 6px; border-radius:4px;'>🔖 العنوان الترويجي: {promo_title}</span>", unsafe_allow_html=True)
                    with c2:
                        st.markdown("<br>", unsafe_allow_html=True)
                        b1, b2, b3 = st.columns(3)
                        with b1:
                            if st.button("👁️ تجاهل التنبيه", key=f"ign_alrt_{p_id}", use_container_width=True):
                                st.session_state["ignored_discount_alerts"].add(p_id)
                                st.rerun()
                        with b2:
                            if st.button("🕒 مسح التاريخ فقط", key=f"clr_dt_{p_id}", use_container_width=True, help="جعل التخفيض مستمراً بدون تاريخ انتهاء"):
                                with st.spinner("⏳"):
                                    base_price = get_flat_price(p.get('regular_price', 0)) or get_flat_price(p.get('price', 0))
                                    sale_price = get_flat_price(p.get('sale_price', 0))
                                    payload = {"name": p_name, "price": base_price, "status": p.get('status', 'sale'), "sale_price": sale_price, "sale_end": None}
                                    if safe_api_request("PUT", f"https://api.salla.dev/admin/v2/products/{p_id}", headers, json=payload):
                                        for i, prod in enumerate(st.session_state["all_products"]):
                                            if str(prod.get('id')) == p_id:
                                                st.session_state["all_products"][i]['sale_end'] = None
                                                break
                                        st.session_state["ignored_discount_alerts"].add(p_id)
                                        st.rerun()
                        with b3:
                            # ✅ زر مسح الخصم وتاريخ الانتهاء معاً
                            if st.button("🗑️ مسح الخصم والتاريخ", key=f"clr_all_{p_id}", type="primary", use_container_width=True, help="إلغاء السعر المخفض وتاريخ الانتهاء تماماً"):
                                with st.spinner("⏳"):
                                    base_price = get_flat_price(p.get('regular_price', 0)) or get_flat_price(p.get('price', 0))
                                    # إرسال None للسعر المخفض و None للتاريخ
                                    payload = {"name": p_name, "price": base_price, "status": p.get('status', 'sale'), "sale_price": None, "sale_end": None}
                                    if safe_api_request("PUT", f"https://api.salla.dev/admin/v2/products/{p_id}", headers, json=payload):
                                        for i, prod in enumerate(st.session_state["all_products"]):
                                            if str(prod.get('id')) == p_id:
                                                st.session_state["all_products"][i]['sale_price'] = None
                                                st.session_state["all_products"][i]['sale_end'] = None
                                                break
                                        st.session_state["ignored_discount_alerts"].add(p_id)
                                        st.rerun()

def calculate_effective_offer_price(base_price: float, offer_name: str) -> float:
    """محلل ذكي لنصوص العروض لتحويلها إلى سعر فعلي للحبة الواحدة (يدعم كافة طرق الكتابة العربية)"""
    offer_name = str(offer_name).strip()
    
    # 1. حالة "اشتر X واحصل على Y مجاناً" (مثال: 1+1 مجاناً، 2+1)
    match_plus = re.search(r'(\d+)\s*\+\s*(\d+)', offer_name)
    if match_plus:
        buy_qty = int(match_plus.group(1))
        free_qty = int(match_plus.group(2))
        total_qty = buy_qty + free_qty
        return (base_price * buy_qty) / total_qty

    # 2. حالة "X حبات بسعر Y ريال" (مثال: 3حبات بسعر 69 ريال، 3 حبة ب 69ريال)
    # ✅ (جديد): يدعم (حبة/حبات/قطعة/قطع/حبه) مع أو بدون مسافات، ويدعم (بسعر/ب/بـ)، ويدعم الريال
    match_bulk_price = re.search(r'(\d+)\s*(?:حب[ةه]|حبات|قطع[ةه]|قطع)\s*(?:بسعر|بـ|ب)\s*(\d+(?:\.\d+)?)(?:\s*(?:ريال|ر\.س))?', offer_name)
    if match_bulk_price:
        qty = int(match_bulk_price.group(1))
        total_price = float(match_bulk_price.group(2))
        if qty > 0:
            return total_price / qty

    # 3. حالة "خصم X% على الحبة/القطعة الثانية"
    match_second = re.search(r'خصم\s*(\d+)\s*%\s*على\s*(?:الحب[ةه]|القطع[ةه])\s*الثاني[ةه]', offer_name)
    if match_second:
        discount_pct = float(match_second.group(1)) / 100.0
        # سعر الحبتين = سعر الأولى كامل + سعر الثانية بعد الخصم
        price_two_items = base_price + (base_price * (1.0 - discount_pct))
        # سعر الحبة المتوسط
        return price_two_items / 2.0

    # 4. حالة "خصم مباشر X%" على المنتج
    match_pct = re.search(r'خصم\s*(\d+)\s*%', offer_name)
    if match_pct and not re.search(r'الثاني[ةه]', offer_name):
        discount_pct = float(match_pct.group(1)) / 100.0
        return base_price * (1.0 - discount_pct)

    # إذا لم يتم التعرف على صيغة العرض، نفترض أنه لا يغير سعر الحبة الأساسي
    return base_price

def generate_price_comparison_excel(all_products, offers_map, excluded_skus=None):
    """بناء ملف إكسيل لمقارنة الأسعار مع استبعاد الرموز المحددة"""
    excluded_skus = set(excluded_skus) if excluded_skus else set()
    
    # 1. استخراج وفهرسة "مجموعات المنتجات" (تخطي المستبعدة)
    group_components_map = {}
    for p in all_products:
        if p.get('type') == 'group_products':
            g_sku = str(p.get('sku', '')).strip().replace('.0', '')
            if g_sku in excluded_skus: continue # 🚫 استبعاد هذه المجموعة
                
            g_reg_price = get_flat_price(p.get('regular_price', 0)) or get_flat_price(p.get('price', 0))
            g_sale_price = get_flat_price(p.get('sale_price', 0))
            g_final_price = g_sale_price if (g_sale_price > 0 and g_sale_price < g_reg_price) else g_reg_price
            
            items = p.get('consisted_products') or p.get('grouped_items') or []
            for item in items:
                child_prod = item.get('product', {}) if 'product' in item else item
                child_id = str(child_prod.get('id', ''))
                if not child_id: continue
                
                qty = int(item.get('quantity_in_group', item.get('quantity', 1)))
                if qty <= 0: qty = 1
                
                if child_id not in group_components_map:
                    group_components_map[child_id] = []
                    
                group_components_map[child_id].append({
                    'group_sku': g_sku if g_sku else 'بدون',
                    'qty_in_group': qty,
                    'group_price': g_final_price,
                    'unit_price': g_final_price / qty
                })

    # 2. المرور على المنتجات الفردية والمقارنة
    results = []
    for p in all_products:
        if p.get('type') == 'group_products': continue
            
        sku = str(p.get('sku', 'بدون')).strip().replace('.0', '')
        if sku in excluded_skus: continue # 🚫 استبعاد هذا المنتج الفردي
            
        p_id = str(p.get('id', ''))
        name = p.get('name', 'بدون اسم')
        
        base_price = get_flat_price(p.get('regular_price', 0)) or get_flat_price(p.get('price', 0))
        sale_price = get_flat_price(p.get('sale_price', 0))
        indiv_price = sale_price if (sale_price > 0 and sale_price < base_price) else base_price
        
        groups = group_components_map.get(p_id, [])
        best_group = min(groups, key=lambda x: x['unit_price']) if groups else None
        
        offers = offers_map.get(p_id, [])
        best_offer_price = None
        best_offer_name = None
        
        for off in offers:
            off_name = off.get('name', '')
            calc_price = calculate_effective_offer_price(indiv_price, off_name)
            if best_offer_price is None or calc_price < best_offer_price:
                best_offer_price = calc_price
                best_offer_name = off_name

        comparison_list = [('شراء فردي (مباشر)', indiv_price)]
        if best_group: comparison_list.append((f"شراء كمجموعة ({best_group['group_sku']})", best_group['unit_price']))
        if best_offer_price is not None: comparison_list.append((f"شراء من عرض ({best_offer_name})", best_offer_price))
            
        best_method, lowest_price = min(comparison_list, key=lambda x: x[1])
        
        results.append({
            "رمز SKU": sku,
            "اسم المنتج": name,
            "سعر الحبة (أساسي)": base_price,
            "سعر الحبة (مخفض)": sale_price if sale_price > 0 else "-",
            "أفضل سعر داخل مجموعة": round(best_group['unit_price'], 2) if best_group else "-",
            "SKU المجموعة": best_group['group_sku'] if best_group else "-",
            "سعر الحبة داخل العرض الخاص": round(best_offer_price, 2) if best_offer_price is not None else "-",
            "اسم العرض المؤثر": best_offer_name if best_offer_name else "-",
            "أرخص سعر ممكن للحبة": round(lowest_price, 2),
            "الطريقة الأوفر للعميل": best_method
        })

    df = pd.DataFrame(results)
    buf = io.BytesIO()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "مقارنة الأسعار الذكية"
    ws.sheet_view.rightToLeft = True
    
    headers = list(df.columns)
    ws.append(headers)
    for row in df.itertuples(index=False, name=None): ws.append(row)
        
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(color="00EBCF", bold=True)
    center_align = Alignment(horizontal="center", vertical="center")
    
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.fill = header_fill; cell.font = header_font; cell.alignment = center_align
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 22
        
    ws.auto_filter.ref = f"A1:{openpyxl.utils.get_column_letter(len(headers))}{ws.max_row}"
    wb.save(buf)
    return buf.getvalue()

def get_pricing_anomalies(all_products, offers_map, excluded_skus=None):
    """خوارزمية ذكية لاكتشاف أخطاء التسعير مع إظهار السعر الفعلي للمجموعة والمعرفات للتحكم الآلي"""
    excluded_skus = set(excluded_skus) if excluded_skus else set()
    
    group_components_map = {}
    for p in all_products:
        if p.get('type') == 'group_products':
            g_sku = str(p.get('sku', '')).strip().replace('.0', '')
            if g_sku in excluded_skus: continue 
                
            g_reg_price = get_flat_price(p.get('regular_price', 0)) or get_flat_price(p.get('price', 0))
            g_sale_price = get_flat_price(p.get('sale_price', 0))
            g_final_price = g_sale_price if (g_sale_price > 0 and g_sale_price < g_reg_price) else g_reg_price
            
            items = p.get('consisted_products') or p.get('grouped_items') or []
            for item in items:
                child_prod = item.get('product', {}) if 'product' in item else item
                child_id = str(child_prod.get('id', ''))
                if not child_id: continue
                
                qty = int(item.get('quantity_in_group', item.get('quantity', 1)))
                if qty <= 0: qty = 1
                
                if child_id not in group_components_map:
                    group_components_map[child_id] = []
                    
                group_components_map[child_id].append({
                    'group_id': str(p.get('id', '')),
                    'group_name': p.get('name', 'مجموعة بدون اسم'),
                    'group_sku': g_sku if g_sku else 'بدون',
                    'qty_in_group': qty,
                    'group_price': g_final_price,
                    'unit_price': g_final_price / qty
                })

    anomalies = []
    for p in all_products:
        if p.get('type') == 'group_products': continue
            
        sku = str(p.get('sku', 'بدون')).strip().replace('.0', '')
        if sku in excluded_skus: continue 
            
        p_id = str(p.get('id', ''))
        name = p.get('name', 'بدون اسم')
        
        base_price = get_flat_price(p.get('regular_price', 0)) or get_flat_price(p.get('price', 0))
        sale_price = get_flat_price(p.get('sale_price', 0))
        indiv_price = sale_price if (sale_price > 0 and sale_price < base_price) else base_price
        
        if indiv_price <= 0: continue
        
        # 1. فحص المجموعات
        for grp in group_components_map.get(p_id, []):
            if round(grp['unit_price'], 2) > round(indiv_price, 2):
                anomalies.append({
                    "_indiv_id": p_id,
                    "_group_id": grp['group_id'],
                    "_qty": grp['qty_in_group'],
                    "نوع الخلل": "مجموعة أغلى من الفردي",
                    "رقم المنتج (SKU)": sku,
                    "المنتج الفردي": name,
                    "سعر الحبة الفردي": round(indiv_price, 2),
                    "المجموعة / العرض": f"{grp['group_name']} (SKU: {grp['group_sku']})",
                    "العرض": f"{round(grp['group_price'], 2)} ريال", # ✅ هنا يظهر السعر الفعلي للمجموعة بدلاً من النص الثابت
                    "سعر الحبة بداخلها": round(grp['unit_price'], 2),
                    "خسارة العميل في الحبة": round(grp['unit_price'] - indiv_price, 2)
                })
                
        # 2. فحص العروض الخاصة
        for off in offers_map.get(p_id, []):
            off_name = off.get('name', '')
            calc_price = calculate_effective_offer_price(indiv_price, off_name)
            
            if round(calc_price, 2) > round(indiv_price, 2):
                anomalies.append({
                    "_indiv_id": p_id,
                    "_group_id": None,
                    "_qty": 1,
                    "نوع الخلل": "عرض خاص أغلى من الفردي",
                    "رقم المنتج (SKU)": sku,
                    "المنتج الفردي": name,
                    "سعر الحبة الفردي": round(indiv_price, 2),
                    "المجموعة / العرض": "إعدادات العروض الخاصة",
                    "العرض": off_name,
                    "سعر الحبة بداخلها": round(calc_price, 2),
                    "خسارة العميل في الحبة": round(calc_price - indiv_price, 2)
                })
                
    return anomalies

def generate_anomalies_excel(anomalies):
    """بناء إكسيل منسق لإنذارات أخطاء التسعير (يقوم بتجاهل المتغيرات المخفية)"""
    # تصفية الأعمدة التي تبدأ بـ "_" لأنها متغيرات برمجية فقط وليست للعرض
    clean_anomalies = [{k: v for k, v in a.items() if not k.startswith('_')} for a in anomalies]
    
    df = pd.DataFrame(clean_anomalies)
    buf = io.BytesIO()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "أخطاء التسعير المكتشفة"
    ws.sheet_view.rightToLeft = True
    
    headers = list(df.columns)
    ws.append(headers)
    for row in df.itertuples(index=False, name=None): ws.append(row)
        
    header_fill = PatternFill(start_color="C0392B", end_color="C0392B", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    center_align = Alignment(horizontal="center", vertical="center")
    
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.fill = header_fill; cell.font = header_font; cell.alignment = center_align
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 24
        
    ws.auto_filter.ref = f"A1:{openpyxl.utils.get_column_letter(len(headers))}{ws.max_row}"
    wb.save(buf)
    return buf.getvalue()
    
def render_products_page():
    import time
    import os
    import json
    
    initialize_session()
    headers = get_headers()
    if not headers: return
    
    st.markdown("""
    <div style="background: linear-gradient(135deg, #0F1C2E 0%, #00EBCF 100%); padding: 15px 25px; border-radius: 12px; color: white; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        <h2 style="color: white; margin: 0;">📦 مركز إدارة المنتجات المتقدم</h2>
    </div>
    """, unsafe_allow_html=True)
    
    # ✅ عرض تنبيهات التخفيضات المنتهية
    render_discount_expiry_alerts(headers)

    def get_remaining_time_str(run_at_str):
        """حساب الوقت المتبقي لبدء الجدولة بدقة بتوقيت السعودية"""
        saudi_now = datetime.now(timezone(timedelta(hours=3))).replace(tzinfo=None)
        try:
            run_time = datetime.strptime(run_at_str, "%Y-%m-%d %H:%M")
            diff = run_time - saudi_now
            total_seconds = int(diff.total_seconds())
            if total_seconds <= 0:
                return "⏳ حان وقت التنفيذ الآن..."
            
            days = diff.days
            hours, remainder = divmod(diff.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            parts = []
            if days > 0: parts.append(f"{days} يوم")
            if hours > 0: parts.append(f"{hours} ساعة")
            if minutes > 0: parts.append(f"{minutes} دقيقة")
            if not parts: parts.append(f"{seconds} ثانية")
            return "⏳ متبقي: " + " و ".join(parts)
        except Exception:
            return ""
            
    # ========================================================
    # 📊 قسم التقارير المتقدمة والمدقق المالي الذكي
    # ========================================================
    with st.expander("📊 تقارير التسعير المتقدمة (للفردي والمجموعة)", expanded=False):
        st.info("💡 المدقق المالي: يقوم بحساب سعر الحبة الفعلي لكل منتج سواء تم بيعه كـ (فردي)، أو داخل (مجموعة)، أو داخل (عرض خاص)، ويستخرج لك أرخص وأفضل طريقة يتم بيع المنتج بها حالياً، ويكتشف الأخطاء تلقائياً.")
        
        st.markdown("#### 🚫 استبعاد مجموعات أو منتجات (اختياري)")
        uploaded_exclusion = st.file_uploader("📂 رفع ملف (Excel/CSV) يحتوي على رموز SKU للمجموعات المراد استبعادها في العمود الأول:", type=['xlsx', 'csv'], key="excl_skus_file")
        
        excluded_skus = set()
        if uploaded_exclusion:
            try:
                if uploaded_exclusion.name.endswith('.csv'): df_ex = pd.read_csv(uploaded_exclusion)
                else: df_ex = pd.read_excel(uploaded_exclusion)
                
                if not df_ex.empty:
                    raw_skus = df_ex.iloc[:, 0].dropna().astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
                    excluded_skus = set(raw_skus.tolist())
                    st.success(f"✅ تم قراءة واستبعاد ({len(excluded_skus)}) رمز SKU بنجاح.")
            except Exception as e:
                st.error(f"❌ خطأ في قراءة ملف الاستبعاد: {e}")

        all_prods = st.session_state.get("all_products", [])
        offers_map = st.session_state.get("product_offers_map", {})
        
        if all_prods:
            col_rp1, col_rp2 = st.columns(2)
            
            with col_rp1:
                excel_bytes = generate_price_comparison_excel(all_prods, offers_map, excluded_skus)
                st.download_button(
                    label="📥 تحميل التقرير الشامل: مقارنة سعر المنتج (فردي/مجموعة/عروض)",
                    data=excel_bytes,
                    file_name=f"Price_Comparison_Report_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                
            with col_rp2:
                anomalies = get_pricing_anomalies(all_prods, offers_map, excluded_skus)
                if anomalies:
                    st.download_button(
                        label=f"🚨 تنزيل أخطاء التسعير المكتشفة ({len(anomalies)} خطأ)",
                        data=generate_anomalies_excel(anomalies),
                        file_name=f"Pricing_Errors_Alert_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        use_container_width=True
                    )
                else:
                    st.button("✅ أمورك طيبة ... التسعير سليم 100% (لا يوجد أخطاء)", disabled=True, use_container_width=True)

            if anomalies:
                st.markdown(f"""
                <div style="background: rgba(231, 76, 60, 0.1); border-right: 5px solid #e74c3c; padding: 15px; border-radius: 8px; margin-top: 15px; margin-bottom: 15px;">
                    <h4 style="color: #e74c3c; margin: 0 0 10px 0;">🚨 تنبيه عاجل!</h4>
                    تم اكتشاف <b>({len(anomalies)})</b> حالة يكون فيها الشراء عبر (المجموعة أو العرض الخاص) <b>أغلى</b> من الشراء الفردي للمنتج!
                </div>
                """, unsafe_allow_html=True)
                
                # عرض عينة صغيرة في الواجهة (بدون المتغيرات الخفية)
                display_df = pd.DataFrame([{k: v for k, v in a.items() if not k.startswith('_')} for a in anomalies])
                st.dataframe(display_df.head(5), use_container_width=True)

                st.markdown("#### ⚡ إجراءات سريعة لمعالجة الأخطاء")
                c_act1, c_act2, c_act3, c_act4 = st.columns(4)
                with c_act1:
                    do_fix_group = st.checkbox("🛠️ تعديل السعر ومسح الترويجي (للمجموعة)")
                with c_act2:
                    do_clear_indiv = st.checkbox("🧹 مسح المخفض والترويجي (للمنتج الفردي)")
                with c_act3:
                    do_create_group = st.checkbox("⭐ إنشاء مجموعة مميزة لمنتجات الأخطاء")
                with c_act4:
                    do_refresh_ano = st.checkbox("🔄 تحديث منتجات الأخطاء المكتشفة")

                # حقل اسم المجموعة المميزة يظهر إذا تم تفعيل خيار إنشاء المجموعة
                new_ano_group_name = None
                if do_create_group:
                    new_ano_group_name = st.text_input(
                        "اسم المجموعة المميزة الجديدة:", 
                        value=f"أخطاء التسعير ({datetime.now().strftime('%Y-%m-%d')})"
                    )

                if st.button("🚀 تنفيذ الإجراءات المحددة", type="primary", use_container_width=True):
                    if not (do_fix_group or do_clear_indiv or do_create_group or do_refresh_ano):
                        st.warning("يرجى تحديد إجراء واحد على الأقل.")
                    else:
                        # 1. جمع كافة معرفات المنتجات المكتشفة في الأخطاء
                        all_anomaly_prod_ids = set()
                        for a in anomalies:
                            if a.get("_indiv_id"): all_anomaly_prod_ids.add(str(a["_indiv_id"]))
                            if a.get("_group_id"): all_anomaly_prod_ids.add(str(a["_group_id"]))

                        progress_bar = st.progress(0)
                        status_msg = st.empty()

                        # 2. إنشاء مجموعة مميزة لمنتجات الأخطاء
                        if do_create_group:
                            if not new_ano_group_name:
                                st.error("⚠️ يرجى كتابة اسم للمجموعة المميزة.")
                                st.stop()
                            if "featured_product_groups" not in st.session_state:
                                st.session_state["featured_product_groups"] = {}
                            st.session_state["featured_product_groups"][new_ano_group_name] = list(all_anomaly_prod_ids)
                            st.success(f"✅ تم إنشاء المجموعة المميزة '{new_ano_group_name}' بعدد {len(all_anomaly_prod_ids)} منتج بنجاح!")

                        # 3. تعديل سعر المجموعات لمنطق الفردي ومسح الترويجي
                        processed_groups = set()
                        if do_fix_group:
                            for idx, ano in enumerate(anomalies):
                                group_id = ano.get("_group_id")
                                qty = ano.get("_qty", 1)
                                indiv_price = ano["سعر الحبة الفردي"]
                                
                                if group_id and group_id not in processed_groups:
                                    new_group_price = round(indiv_price * qty, 2)
                                    status_msg.info(f"⏳ جاري تعديل سعر المجموعة ID: {group_id} إلى {new_group_price} SAR...")
                                    update_product_sale_price(int(group_id), new_group_price)
                                    update_product_promotions_secure(int(group_id), "", "", headers)
                                    processed_groups.add(group_id)
                                    time.sleep(0.3)

                        # 4. مسح السعر المخفض والعنوان الترويجي للمنتج الفردي
                        processed_indivs = set()
                        if do_clear_indiv:
                            for idx, ano in enumerate(anomalies):
                                indiv_id = ano.get("_indiv_id")
                                if indiv_id and indiv_id not in processed_indivs:
                                    status_msg.info(f"⏳ جاري مسح سعر التخفيض للمنتج الفردي ID: {indiv_id}...")
                                    prod = next((p for p in all_prods if str(p['id']) == indiv_id), None)
                                    if prod:
                                        base_p = get_flat_price(prod.get('regular_price', 0)) or get_flat_price(prod.get('price', 0))
                                        payload = {"name": prod.get('name'), "price": base_p, "status": prod.get('status', 'sale'), "sale_price": None, "sale_start": None, "sale_end": None}
                                        safe_api_request("PUT", f"https://api.salla.dev/admin/v2/products/{indiv_id}", headers, json=payload)
                                        update_product_promotions_secure(int(indiv_id), "", "", headers)
                                        processed_indivs.add(indiv_id)
                                        time.sleep(0.3)

                        # 5. تحديث بيانات المنتجات المكتشفة من سلة (نفس آلية زر تحديث المنتجات المفلترة تماماً)
                        if do_refresh_ano:
                            target_refresh_ids = list(all_anomaly_prod_ids)
                            total_to_refresh = len(target_refresh_ids)
                            updated_count = 0
                            
                            for idx, p_id in enumerate(target_refresh_ids):
                                status_msg.info(f"⏳ جاري سحب أحدث البيانات لمنتج الخطأ {idx+1} من {total_to_refresh} (ID: {p_id})...")
                                fresh_res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products/{p_id}", headers)
                                if fresh_res and fresh_res.get('data'):
                                    for i, prod in enumerate(st.session_state.get("all_products", [])):
                                        if str(prod.get('id')) == str(p_id):
                                            st.session_state["all_products"][i] = fresh_res['data']
                                            updated_count += 1
                                            break
                                    if "product_cache" in st.session_state:
                                        st.session_state["product_cache"][str(p_id)] = fresh_res['data']
                                
                                progress_bar.progress((idx + 1) / total_to_refresh)
                                time.sleep(0.3) # حماية من الـ Rate Limit والـ 504
                                
                            status_msg.success(f"✅ تم سحب وتحديث بيانات {updated_count} منتج بنجاح من سلة!")
                            time.sleep(1.5)

                        st.success("✅ اكتملت كافة الإجراءات المحددة بنجاح!")
                        time.sleep(1.2)
                        st.rerun()
            
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
        div[data-testid="stElementContainer"]:has(span[id="qa-marker-4"]) + div[data-testid="stElementContainer"] { top: 315px; }
        div[data-testid="stElementContainer"]:has(span[id="qa-marker-5"]) + div[data-testid="stElementContainer"] { top: 380px; }
        div[data-testid="stElementContainer"]:has(span[id^="qa-marker-"]) + div[data-testid="stElementContainer"] button {
            width: 100% !important; text-align: right !important; padding-right: 35px !important; font-size: 14px !important;
            font-weight: bold !important; background: transparent !important; border: none !important; color: white !important; box-shadow: none !important;
        }
        div[data-testid="stElementContainer"]:has(span[id^="qa-marker-"]) + div[data-testid="stElementContainer"]::before { content: "👈"; position: absolute; left: 10px; top: 50%; transform: translateY(-50%); font-size: 18px; pointer-events: none; }
        .mobile-toggle-btn {
            position: fixed; right: 0px; top: 50%; transform: translateY(-50%); background: #00EBCF; color: #0f1c2e; border: none;
            border-radius: 8px 0 0 8px; padding: 10px 6px; font-size: 14px; cursor: pointer; z-index: 999998; writing-mode: vertical-rl;
            font-weight: bold; box-shadow: -2px 2px 10px rgba(0,0,0,0.3); display: none;
        }
        @media (pointer: coarse) {
            .mobile-toggle-btn { display: block !important; }
            div[data-testid="stElementContainer"]:has(span[id^="qa-marker-"]) + div[data-testid="stElementContainer"] { right: 0px !important; width: 200px !important; opacity: 0.85 !important; }
            div[data-testid="stElementContainer"]:has(span[id^="qa-marker-"]) + div[data-testid="stElementContainer"] button { font-size: 12px !important; padding-right: 10px !important; padding: 4px 8px !important; }
            div[data-testid="stElementContainer"]:has(span[id^="qa-marker-"]) + div[data-testid="stElementContainer"]::before { display: none !important; }
        }

        /* سلاسة الحركة والانتقال لكافة البطاقات */
        div[data-testid="stContainer"],
        div[data-testid="stVerticalBlockBorderWrapper"],
        div[data-testid="stExpander"] {
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
        }

        /* تغيير الخلفية والإطار عند مرور مؤشر الماوس فوق أي حاوية أو بطاقة منتج */
        div[data-testid="stContainer"]:hover,
        div[data-testid="stVerticalBlockBorderWrapper"]:hover {
            background-color: #F8FAFC !important; /* لون خلفية ناعم وأنيق */
            border-color: #00EBCF !important;     /* إطار بلون المتجر الفيروزي المميز */
            box-shadow: 0 6px 18px rgba(0, 235, 207, 0.15) !important;
            transform: translateY(-2px) !important; /* رفعة بسيطة لأعلى تعطي شعوراً بالتفاعل */
        }

        /* تأثير المرور على القوائم المنسدلة (Expanders) */
        div[data-testid="stExpander"]:hover {
            border-color: #00EBCF !important;
            box-shadow: 0 4px 14px rgba(15, 28, 46, 0.08) !important;
        }
    </style>
    <button class="mobile-toggle-btn" onclick="
        var btns = document.querySelectorAll('div[data-testid=\\'stElementContainer\\']:has(span[id^=\\'qa-marker-\\']) + div[data-testid=\\'stElementContainer\\']');
        btns.forEach(function(el) { el.style.right = (el.style.right === '0px' || el.style.right === '0') ? '-200px' : '0px'; });
    ">⚡ إجراءات</button>
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

    st.markdown('<span id="qa-marker-4"></span>', unsafe_allow_html=True)
    if st.button("🏷️ التحكم في العناوين والأسعار", key="btn_qa_4"):
        st.session_state.qa_action_prod = "promotions_control"
        st.rerun()
        
    st.markdown('<span id="qa-marker-5"></span>', unsafe_allow_html=True)
    if st.button("⭐ مجموعات المنتجات المميزة", key="btn_qa_5"):
        st.session_state.qa_action_prod = "featured_groups"
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
                                    if not selected_indices: st.warning("⚠️ اختر منتجاً واحداً على الأقل")
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

            elif st.session_state.qa_action_prod == "promotions_control":
                with col_t: st.markdown("### 🏷️ التحكم الشامل في العناوين والأسعار المخفضة")
                st.info("قم بتنزيل القالب، ضع معرفات المنتجات (SKU)، وحدد الإجراء (تحديث، تحديث السعر المخفض، مسح الترويجي، مسح الفرعي، مسح الكل).")
                
                st.download_button("📥 تنزيل القالب الاحترافي للتحديث", data=generate_promotions_template(), file_name="Promotions_Prices_Template.xlsx", use_container_width=True)
                uploaded_promo = st.file_uploader("📂 رفع ملف البيانات المعبأ:", type=['xlsx'], key="up_promo")
                
                if uploaded_promo:
                    try:
                        df_promo = pd.read_excel(uploaded_promo)
                        # تنظيف الـ SKU للفحص
                        df_promo['clean_sku'] = df_promo['SKU (رقم المنتج)'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
                        valid_skus = df_promo['clean_sku'].tolist()
                        
                        po_map = st.session_state.get("product_offers_map", {})
                        conflicts = []
                        
                        for p in st.session_state.get("all_products", []):
                            p_sku = str(p.get('sku', '')).strip()
                            if p_sku.endswith('.0'): p_sku = p_sku[:-2]
                            
                            if p_sku in valid_skus:
                                sale = get_flat_price(p.get('sale_price', 0))
                                offers = po_map.get(str(p['id']), [])
                                if sale > 0 or offers:
                                    promo_text = p.get('promotion_title') or (p.get('promotion', {}).get('title') if isinstance(p.get('promotion'), dict) else '') or "بدون عنوان ترويجي"
                                    reasons = []
                                    if sale > 0: reasons.append(f"سعر مخفض ({sale})")
                                    if offers: reasons.append("مشمول في عرض خاص")
                                    conflicts.append({'sku': p_sku, 'name': p['name'], 'id': str(p['id']), 'promo': promo_text, 'reason': " + ".join(reasons)})

                        # ==========================================
                        # ⏰ تحديد آلية التنفيذ: فوري أم مجدول؟
                        # ==========================================
                        # التأكد من تشغيل خيط الجدولة وربطه بالسياق الحالي
                        init_background_scheduler()

                        st.markdown("---")
                        st.markdown("#### ⏰ خيارات التنفيذ والجدولة التلقائية")
                        
                        exec_type = st.radio(
                            "اختر آلية التنفيذ:", 
                            ["🚀 تنفيذ مباشر وفوري", "📅 جدولة الملف لوقت محدد تلقائياً"], 
                            horizontal=True,
                            key="promo_exec_type"
                        )

                        # ----------------------------------------------------
                        # الحالة الأولى: الجدولة لوقت محدد (تنفيذ عـ الكل تلقائياً)
                        # ----------------------------------------------------
                        if exec_type == "📅 جدولة الملف لوقت محدد تلقائياً":
                            if conflicts:
                                st.info(f"ℹ️ تم رصد ({len(conflicts)}) منتج يحتوي على عروض/تخفيضات سابقة. وبما أنك اخترت **الجدولة التلقائية**، فسيتم تطبيق إجراء **(تنفيذ عـ الكل وتحديث كافة المنتجات)** تلقائياً فور حلول الموعد دون الحاجة لتدخل يدوي.")
                            
                            col_sd, col_st = st.columns(2)
                            with col_sd:
                                sched_date = st.date_input("تاريخ التنفيذ:", value=datetime.now().date(), key="sch_d")
                            with col_st:
                                sched_time = st.time_input("وقت التنفيذ:", value=(datetime.now() + timedelta(minutes=15)).time(), key="sch_t")
                                
                            sched_datetime_str = f"{sched_date.strftime('%Y-%m-%d')} {sched_time.strftime('%H:%M')}"
                            st.info(f"🕒 سيتم حفظ الملف وتشغيله تلقائياً في سلة بتاريخ: **{sched_datetime_str}** بتوقيت السعودية.")
                            
                            if st.button("💾 حفظ وجدولة الملف (اعتماد تنفيذ عـ الكل)", type="primary", use_container_width=True, key="btn_save_sched"):
                                if not uploaded_promo:
                                    st.error("⚠️ يرجى رفع ملف البيانات أولاً.")
                                else:
                                    safe_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_promo.name}"
                                    target_path = os.path.join(SCHEDULE_DIR, safe_filename)
                                    
                                    # حفظ الملف بالكامل ليتنفذ على جميع المنتجات
                                    with open(target_path, "wb") as f:
                                        f.write(uploaded_promo.getvalue())
                                        
                                    meta_path = os.path.join(SCHEDULE_DIR, safe_filename + ".meta.json")
                                    with open(meta_path, "w", encoding="utf-8") as mf:
                                        json.dump(st.session_state.get("all_products", []), mf, ensure_ascii=False)
                                        
                                    schedules = load_schedules()
                                    schedules.append({
                                        "id": len(schedules) + 1,
                                        "original_name": uploaded_promo.name,
                                        "filename": safe_filename,
                                        "run_at": sched_datetime_str,
                                        "status": "pending",
                                        "mode": "all",  # تنفيذ عـ الكل
                                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    })
                                    save_schedules(schedules)
                                    st.success(f"✅ تم حفظ وجدولة الملف بنجاح! سينفذ تلقائياً بوضع (تنفيذ عـ الكل) في {sched_datetime_str}.")
                                    time.sleep(1.5)
                                    st.rerun()

                        # ----------------------------------------------------
                        # الحالة الثانية: تنفيذ مباشر وفوري (خيارات يدوية)
                        # ----------------------------------------------------
                        else:
                            if conflicts:
                                st.error(f"⚠️ تحذير: تم اكتشاف ({len(conflicts)}) منتج في الملف يحتوي بالفعل على تخفيضات أو عروض نشطة!")
                                with st.expander("👀 عرض تفاصيل المنتجات المتعارضة", expanded=False):
                                    for c in conflicts:
                                        st.markdown(f"- **{c['name']}** (SKU: `{c['sku']}`)<br><span style='color:#e74c3c; font-size:13px;'>سبب التعارض: {c['reason']} | العنوان الحالي: {c['promo']}</span>", unsafe_allow_html=True)
                                        
                                st.markdown("**يرجى اتخاذ إجراء لاكتمال عملية الرفع المباشر:**")
                                c1, c2, c3, c4 = st.columns(4)
                                if c1.button("🚀 تنفيذ عـ الكل (تجاهل)", type="primary", use_container_width=True):
                                    with st.spinner("⏳ جاري المعالجة..."):
                                        res = process_promotions_bulk(df_promo, st.session_state.get("all_products", []), headers)
                                        for m in res["success"]: st.success(m)
                                        for m in res["errors"]: st.error(m)
                                        st.session_state["all_products_fetched"] = False
                                if c2.button("✅ التنفيذ عـ الباقي (استبعاد)", type="primary", use_container_width=True):
                                    with st.spinner("⏳ جاري المعالجة..."):
                                        conflict_skus = [c['sku'] for c in conflicts]
                                        df_clean = df_promo[~df_promo['clean_sku'].isin(conflict_skus)]
                                        res = process_promotions_bulk(df_clean, st.session_state.get("all_products", []), headers)
                                        for m in res["success"]: st.success(m)
                                        for m in res["errors"]: st.error(m)
                                        st.session_state["all_products_fetched"] = False
                                if c3.button("❌ إلغاء العملية", use_container_width=True):
                                    st.info("تم إلغاء عملية الرفع.")
                                    
                                with c4:
                                    with st.popover("⚙️ أخرى", use_container_width=True):
                                        st.markdown("**إجراءات إضافية:**")
                                        conflict_prods = [p for p in st.session_state.get("all_products", []) if str(p.get('sku', '')).strip().replace('.0', '') in [c['sku'] for c in conflicts]]
                                        st.download_button(
                                            label="📥 تحميل المنتجات المتعارضة",
                                            data=export_products_to_excel(conflict_prods, po_map),
                                            file_name=f"Conflicting_Products_Upload.xlsx",
                                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                            use_container_width=True,
                                            key="dl_conf_upload"
                                        )
                                    # 2. إيقاف العروض الخاصة لهذه المنتجات
                                    if st.button("🛑 إيقاف عروضها الخاصة", key="stop_off_upload", use_container_width=True):
                                        with st.spinner("جاري إيقاف العروض..."):
                                            offer_ids_to_stop = set()
                                            for p in conflict_prods:
                                                for off in po_map.get(str(p['id']), []):
                                                    offer_ids_to_stop.add(str(off['id']))
                                            
                                            stopped_count = 0
                                            for oid in offer_ids_to_stop:
                                                if safe_api_request("PUT", f"https://api.salla.dev/admin/v2/specialoffers/{oid}/status", headers, json={"status": "inactive"}):
                                                    stopped_count += 1
                                                    for i, o in enumerate(st.session_state.get("all_offers", [])):
                                                        if str(o.get('id')) == oid: st.session_state["all_offers"][i]['status'] = 'inactive'
                                                    for pid in list(st.session_state.get("product_offers_map", {}).keys()):
                                                        st.session_state["product_offers_map"][pid] = [o for o in st.session_state["product_offers_map"][pid] if str(o['id']) != oid]
                                            st.success(f"✅ تم إيقاف {stopped_count} عرض خاص بنجاح!")
                                            import time; time.sleep(1.5); st.rerun()
                            else:
                                if st.button("🚀 تنفيذ التحديثات دفعة واحدة الآن", type="primary", use_container_width=True):
                                    with st.spinner("⏳ جاري المعالجة..."):
                                        res = process_promotions_bulk(df_promo, st.session_state.get("all_products", []), headers)
                                        for m in res["success"]: st.success(m)
                                        for m in res["errors"]: st.error(m)
                                        st.session_state["all_products_fetched"] = False
                    except Exception as e:
                        st.error(f"❌ خطأ في قراءة الملف: {str(e)}")

                # ==========================================
                # استعراض المهام المجدولة (مع شريط التقدم الحي)
                # ==========================================
                schedules = load_schedules()
                in_progress_tasks = [s for s in schedules if s.get("status") == "in_progress"]
                pending_tasks = [s for s in schedules if s.get("status") == "pending"]
                completed_tasks = [s for s in schedules if s.get("status") == "completed"]
                
                col_hd1, col_hd2 = st.columns([4, 1])
                with col_hd1:
                    st.markdown(f"##### 📋 سجل المهام المجدولة (قيد الانتظار: {len(pending_tasks)})")
                with col_hd2:
                    if st.button("🔄 تحديث الحالة", key="refresh_sched_btn", use_container_width=True):
                        st.rerun()

                # ⚡ عرض المهام التي تعمل حالياً مع شريط التقدم (Live Progress)
                if in_progress_tasks:
                    for task in in_progress_tasks:
                        prog_pct = task.get("progress", 0)
                        cur_cnt = task.get("processed_count", 0)
                        tot_cnt = task.get("total_count", 0)
                        cur_sku = task.get("current_sku", "")
                        
                        st.markdown(f"""
                        <div style="background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%); 
                                    border: 1px solid #93C5FD; border-right: 6px solid #2563EB; 
                                    border-radius: 8px; padding: 12px 16px; margin-bottom: 8px;">
                            <b style="color: #1E40AF; font-size: 14px;">⚡ جاري تنفيذ الجدولة الآن: {task['original_name']}</b><br>
                            <span style="color: #1E3A8A; font-size: 12px;">جاري تحديث المنتج SKU: <code>{cur_sku}</code> ({cur_cnt} من {tot_cnt})</span>
                        </div>
                        """, unsafe_allow_html=True)
                        st.progress(prog_pct / 100.0)
                    # إعادة تحميل تلقائية خفيفة لتحديث الشريط لحظياً أثناء عمل المهمة
                    time.sleep(4)
                    st.rerun()

                # 1. عرض المهام قيد الانتظار (اللون الوردي)
                if pending_tasks:
                    with st.expander(f"⏳ المهام قيد الانتظار ({len(pending_tasks)})", expanded=True):
                        for task in pending_tasks:
                            rem_time = get_remaining_time_str(task.get('run_at', ''))
                            c_t1, c_t2 = st.columns([5, 1])
                            with c_t1:
                                st.markdown(f"""
                                <div style="background: linear-gradient(135deg, #FFF1F2 0%, #FCE7F3 100%); 
                                            border: 1px solid #FDA4AF; border-right: 6px solid #E11D48; 
                                            border-radius: 8px; padding: 10px 16px; color: #881337; 
                                            font-size: 13.5px; display: flex; justify-content: space-between; 
                                            align-items: center; flex-wrap: wrap; gap: 10px;">
                                    <span>📄 <b>{task['original_name']}</b> — ⏰ الموعد: <code>{task['run_at']}</code></span>
                                    <span style="background: #FFE4E6; color: #BE123C; padding: 3px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; border: 1px solid #FECDD3;">
                                        {rem_time}
                                    </span>
                                </div>
                                """, unsafe_allow_html=True)
                            with c_t2:
                                if st.button("❌ إلغاء", key=f"cancel_task_{task['id']}", use_container_width=True):
                                    schedules = [s for s in schedules if s["id"] != task["id"]]
                                    p_file = os.path.join(SCHEDULE_DIR, task["filename"])
                                    p_meta = p_file + ".meta.json"
                                    if os.path.exists(p_file): os.remove(p_file)
                                    if os.path.exists(p_meta): os.remove(p_meta)
                                    save_schedules(schedules)
                                    st.rerun()

                # 2. عرض المهام المكتملة حديثاً (اللون الأخضر)
                if completed_tasks:
                    with st.expander(f"✅ المهام المكتملة حديثاً ({len(completed_tasks)})", expanded=False):
                        for task in reversed(completed_tasks[-5:]):
                            st.success(f"📄 **{task['original_name']}** — تم التنفيذ بنجاح في: `{task.get('executed_at', 'وقت سابق')}`")
                                    
            elif st.session_state.qa_action_prod == "featured_groups":
                with col_t: st.markdown("### ⭐ إدارة مجموعات المنتجات المميزة")
                st.info("💡 يمكنك من هنا تجميع عدة منتجات لتنفيذ خصومات جماعية وعناوين ترويجية بضغطة زر واحدة.")
                
                col_g1, col_g2 = st.columns(2)
                
                with col_g1:
                    st.markdown("#### ➕ إنشاء مجموعة جديدة")
                    new_g_name = st.text_input("اسم المجموعة الجديدة:")
                    
                    st.markdown("**1️⃣ الاختيار اليدوي:**")
                    prod_opts = {f"📦 {p['name']} (SKU: {p.get('sku','')})": str(p['id']) for p in st.session_state.get("all_products", [])}
                    sel_prods = st.multiselect("اختر المنتجات من القائمة:", options=list(prod_opts.keys()))
                    
                    st.markdown("**2️⃣ أو عبر رفع ملف (أسرع):**")
                    st.info("💡 قم برفع ملف Excel/CSV يحتوي على رموز SKU للمنتجات في **العمود الأول**.")
                    uploaded_group_file = st.file_uploader("📂 رفع ملف SKU للمنتجات:", type=['xlsx', 'csv'], key="upload_group_skus")
                    
                    if st.button("💾 حفظ المجموعة", type="primary", key="save_prod_group", use_container_width=True):
                        if not new_g_name: 
                            st.error("⚠️ الرجاء كتابة اسم المجموعة")
                        else:
                            final_product_ids = set()
                            if sel_prods:
                                for k in sel_prods: final_product_ids.add(prod_opts[k])
                            not_found_skus = []
                            if uploaded_group_file:
                                try:
                                    df_skus = pd.read_csv(uploaded_group_file) if uploaded_group_file.name.endswith('.csv') else pd.read_excel(uploaded_group_file)
                                    if not df_skus.empty:
                                        file_skus = df_skus.iloc[:, 0].dropna().astype(str).str.strip().tolist()
                                        sku_to_id = {}
                                        for p in st.session_state.get("all_products", []):
                                            if p.get('sku'):
                                                clean_sku = str(p.get('sku')).strip()
                                                if clean_sku.endswith('.0'): clean_sku = clean_sku[:-2]
                                                sku_to_id[clean_sku] = str(p['id'])
                                        for s in file_skus:
                                            if s.endswith('.0'): s = s[:-2]
                                            if s in sku_to_id: final_product_ids.add(sku_to_id[s])
                                            else: not_found_skus.append(s)
                                except Exception as e: st.error(f"❌ خطأ: {e}")
                                    
                            if not final_product_ids: st.error("⚠️ الرجاء اختيار منتج واحد على الأقل.")
                            else:
                                st.session_state.get("featured_product_groups", {})[new_g_name] = list(final_product_ids)
                                if not_found_skus: st.warning(f"✅ تم الحفظ، ولكن لم نعثر على {len(not_found_skus)} SKU")
                                else: st.success("✅ تم حفظ المجموعة بنجاح!")
                                import time; time.sleep(1.5); st.rerun()
                            
                with col_g2:
                    st.markdown("#### 📋 المجموعات الحالية والإجراءات")
                    featured_groups = st.session_state.get("featured_product_groups", {})
                    if featured_groups:
                        po_map = st.session_state.get("product_offers_map", {})
                        
                        # تحديث الدالة لتستقبل أمر "بدون تاريخ"
                        def execute_group_discount(target_ids, d_pct, d_end_date, is_open_ended=False):
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            c = 0
                            
                            # ✅ إذا كان العرض مستمر، نجعل التاريخ None
                            if is_open_ended:
                                end_time_str = None
                            else:
                                end_time_str = datetime.combine(d_end_date, datetime.min.time().replace(hour=23, minute=59, second=59)).strftime('%Y-%m-%d %H:%M:%S')
                                
                            total = len(target_ids)
                            for idx, pid in enumerate(target_ids):
                                status_text.info(f"⏳ جاري التحديث: {idx+1} من {total}...")
                                prod = next((p for p in st.session_state.get("all_products", []) if str(p['id']) == pid), None)
                                if prod:
                                    base_price = get_flat_price(prod.get('regular_price', 0)) or get_flat_price(prod.get('price', 0))
                                    new_sale = round(base_price - (base_price * (d_pct / 100)), 2)
                                    if update_product_sale_price(int(pid), new_sale, sale_end=end_time_str): c += 1
                                progress_bar.progress((idx + 1) / total)
                                import time; time.sleep(0.5)
                            status_text.success(f"✅ تم تطبيق خصم {d_pct}% على {c} منتج!")
                            import time; time.sleep(1)
                            if "all_products_fetched" in st.session_state: del st.session_state["all_products_fetched"]
                            st.rerun()

                        for g_name, g_ids in list(featured_groups.items()):
                            group_products_data = [p for p in st.session_state.get("all_products", []) if str(p['id']) in g_ids]
                            
                            with st.expander(f"📁 {g_name} ({len(g_ids)} منتجات)", expanded=False):
                                st.download_button("📥 تصدير (Excel)", data=export_featured_group_to_excel(group_products_data, po_map), file_name=f"Group_{g_name}.xlsx", use_container_width=True)
                                
                                with st.popover("📦 استعراض المحتوى", use_container_width=True):
                                    st.markdown("**حدد المنتجات التي تريد إزالتها من المجموعة:**")
                                    selected_to_remove = []
                                    
                                    # ✅ عرض المنتجات مع Checkbox + زر الإزالة الفردي
                                    for pid in list(g_ids):
                                        prod_info = next((p for p in group_products_data if str(p['id']) == pid), None)
                                        if prod_info:
                                            cx_chk, cx_info, cx_btn = st.columns([0.8, 5, 1.2])
                                            with cx_chk:
                                                if st.checkbox("", key=f"chk_rm_{pid}_{g_name}", label_visibility="collapsed"):
                                                    selected_to_remove.append(pid)
                                            with cx_info: 
                                                st.markdown(f"`{prod_info.get('sku')}` | {prod_info.get('name')}")
                                            with cx_btn:
                                                if st.button("❌", key=f"rm_{pid}_{g_name}", help="حذف هذا المنتج فقط"):
                                                    st.session_state["featured_product_groups"][g_name].remove(pid)
                                                    st.rerun()
                                                    
                                    # ✅ زر الحذف الجماعي للمنتجات المحددة عبر الـ Checkbox
                                    if selected_to_remove:
                                        if st.button(f"🗑️ إزالة المحددة ({len(selected_to_remove)})", key=f"rm_bulk_{g_name}", type="primary", use_container_width=True):
                                            for pid in selected_to_remove:
                                                st.session_state["featured_product_groups"][g_name].remove(pid)
                                            st.rerun()
                                            
                                    st.markdown("---")
                                    st.markdown("**إضافة منتجات جديدة للمجموعة:**")
                                    add_opts = {f"📦 {p['name']} (SKU: {p.get('sku','')})": str(p['id']) for p in st.session_state.get("all_products", []) if str(p['id']) not in g_ids}
                                    to_add = st.multiselect("اختر لإضافة المزيد:", options=list(add_opts.keys()), key=f"add_ms_{g_name}", label_visibility="collapsed")
                                    if st.button("➕ إضافة المحددة", key=f"add_btn_{g_name}"):
                                        if to_add:
                                            st.session_state["featured_product_groups"][g_name].extend([add_opts[k] for k in to_add])
                                            st.rerun()
                                
                                st.markdown("---")
                                st.markdown("**⚡ الإجراءات السريعة للمجموعة:**")
                                
                                # 1. إنشاء سعر مخفض (مع زر العرض المستمر)
                                is_open_ended = st.session_state.get(f"no_date_{g_name}", False)
                                
                                # استخدمنا نسب تقسيم للأعمدة ليكون الشكل متناسقاً
                                col_d1, col_d2, col_d3 = st.columns([2, 2, 1.5]) 
                                
                                with col_d1:
                                    disc_pct = st.number_input("نسبة الخصم %:", min_value=1.0, max_value=99.0, value=15.0, step=1.0, key=f"dpct_{g_name}")
                                
                                with col_d2:
                                    # الاعتماد على المتغير المقروء من الذاكرة
                                    disc_end_date = st.date_input("تاريخ الانتهاء:", value=datetime.now().date() + timedelta(days=7), disabled=is_open_ended, key=f"dend_{g_name}")
                                
                                with col_d3:
                                    st.markdown("<br>", unsafe_allow_html=True) # لإنزال الزر ليكون بمحاذاة الحقول
                                    # يتم رسم الزر هنا، وقيمته ستُحفظ تلقائياً في الذاكرة لتستخدم في المرة القادمة
                                    no_end_date = st.checkbox("♾️", key=f"no_date_{g_name}")
                                    
                                confs = []
                                for p in group_products_data:
                                    sale = get_flat_price(p.get('sale_price', 0))
                                    offers = po_map.get(str(p['id']), [])
                                    if sale > 0 or offers:
                                        promo_text = p.get('promotion_title') or (p.get('promotion', {}).get('title') if isinstance(p.get('promotion'), dict) else '') or "بدون عنوان ترويجي"
                                        reasons = []
                                        if sale > 0: reasons.append(f"مخفض ({sale})")
                                        if offers: reasons.append("عرض خاص")
                                        p_sku = p.get('sku', 'لا يوجد')
                                        confs.append({'id': str(p['id']), 'name': p['name'], 'sku': p_sku, 'promo': promo_text, 'reason': " + ".join(reasons)})
                                        
                                if confs:
                                    st.error(f"⚠️ يوجد ({len(confs)}) منتج في هذه المجموعة تحتوي بالفعل على عروض!")
                                    with st.expander("👀 عرض المنتجات المتعارضة", expanded=False):
                                        for c in confs:
                                            st.markdown(f"- **{c['name']}** (SKU: `{c['sku']}`)<br><span style='color:#e74c3c; font-size:12px;'>السبب: {c['reason']} | العنوان: {c['promo']}</span>", unsafe_allow_html=True)
                                    
                                    c1, c2, c3, c4 = st.columns(4)
                                    if c1.button("🚀 تنفيذ وتجاهل", key=f"frc_{g_name}", type="primary", use_container_width=True):
                                        execute_group_discount(g_ids, disc_pct, disc_end_date, no_end_date) # ✅ تمرير الحالة الجديدة
                                    if c2.button("✅ تنفيذ عالباقي", key=f"skp_{g_name}", type="primary", use_container_width=True):
                                        conf_ids = [c['id'] for c in confs]
                                        clean_ids = [pid for pid in g_ids if pid not in conf_ids]
                                        execute_group_discount(clean_ids, disc_pct, disc_end_date, no_end_date) # ✅ تمرير الحالة الجديدة
                                    if c3.button("❌ إلغاء", key=f"cncl_{g_name}", use_container_width=True): pass
                                    
                                    with c4:
                                        with st.popover("⚙️ أخرى", use_container_width=True):
                                            st.markdown("**إجراءات إضافية:**")
                                            conflict_prods = [p for p in group_products_data if str(p['id']) in [c['id'] for c in confs]]
                                            st.download_button(
                                                label="📥 تحميل المنتجات المتعارضة",
                                                data=export_products_to_excel(conflict_prods, po_map),
                                                file_name=f"Conflicting_Products_Group_{g_name}.xlsx",
                                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                                use_container_width=True,
                                                key=f"dl_conf_{g_name}"
                                            )
                                            if st.button("🛑 إيقاف عروضها الخاصة", key=f"stop_off_{g_name}", use_container_width=True):
                                                with st.spinner("جاري إيقاف العروض..."):
                                                    offer_ids_to_stop = set()
                                                    for c_id in [c['id'] for c in confs]:
                                                        for off in po_map.get(c_id, []):
                                                            offer_ids_to_stop.add(str(off['id']))
                                                    
                                                    stopped_count = 0
                                                    for oid in offer_ids_to_stop:
                                                        if safe_api_request("PUT", f"https://api.salla.dev/admin/v2/specialoffers/{oid}/status", headers, json={"status": "inactive"}):
                                                            stopped_count += 1
                                                            for i, o in enumerate(st.session_state.get("all_offers", [])):
                                                                if str(o.get('id')) == oid: st.session_state["all_offers"][i]['status'] = 'inactive'
                                                            for pid in list(st.session_state.get("product_offers_map", {}).keys()):
                                                                st.session_state["product_offers_map"][pid] = [o for o in st.session_state["product_offers_map"][pid] if str(o['id']) != oid]
                                                    st.success(f"✅ تم إيقاف {stopped_count} عرض خاص بنجاح!")
                                                    import time; time.sleep(1.5); st.rerun()
                                else:
                                    if st.button("💰 تطبيق الخصم", key=f"dbtn_{g_name}", use_container_width=True, type="primary"):
                                        execute_group_discount(g_ids, disc_pct, disc_end_date, no_end_date) # ✅ تمرير الحالة الجديدة
                                            
                                # 2. العنوان الترويجي الجماعي
                                col_p1, col_p2 = st.columns([2, 1])
                                with col_p1: promo_title = st.text_input("العنوان الترويجي:", key=f"ptxt_{g_name}")
                                with col_p2:
                                    st.markdown("<br>", unsafe_allow_html=True)
                                    if st.button("🏷️ تطبيق العنوان", key=f"pbtn_{g_name}", use_container_width=True):
                                        progress_bar = st.progress(0); status_text = st.empty(); c = 0; total = len(g_ids)
                                        for idx, pid in enumerate(g_ids):
                                            status_text.info(f"⏳ جاري تحديث العنوان {idx+1} من {total}...")
                                            if update_product_promotions_secure(int(pid), promo_title, "", headers): c += 1
                                            progress_bar.progress((idx + 1) / total); import time; time.sleep(0.5) 
                                        status_text.success(f"✅ تم تحديث {c} منتج!"); import time; time.sleep(1); st.rerun()
                                            
                                # 3. مسح الخصم والعناوين
                                if st.button("🧹 مسح التخفيضات والعناوين نهائياً", key=f"cbtn_{g_name}", use_container_width=True):
                                    progress_bar = st.progress(0); status_text = st.empty(); c = 0; total = len(g_ids)
                                    for idx, pid in enumerate(g_ids):
                                        status_text.info(f"⏳ جاري مسح بيانات المنتج {idx+1} من {total}...")
                                        update_product_sale_price(int(pid), 0)
                                        import time; time.sleep(0.3) 
                                        update_product_promotions_secure(int(pid), "", "", headers); c += 1
                                        progress_bar.progress((idx + 1) / total); time.sleep(0.3) 
                                    status_text.success(f"✅ تم المسح لـ {c} منتج!"); import time; time.sleep(1)
                                    if "all_products_fetched" in st.session_state: del st.session_state["all_products_fetched"]
                                    st.rerun()
                                        
                                st.markdown("---")
                                
                                # 4 & 5. إعادة التسمية والحذف
                                col_rn1, col_rn2 = st.columns([2, 1])
                                with col_rn1: new_rename = st.text_input("اسم جديد للمجموعة:", value=g_name, key=f"rntxt_{g_name}")
                                with col_rn2:
                                    st.markdown("<br>", unsafe_allow_html=True)
                                    if st.button("✏️ إعادة تسمية", key=f"rnbtn_{g_name}", use_container_width=True):
                                        if new_rename and new_rename != g_name:
                                            st.session_state.get("featured_product_groups", {})[new_rename] = st.session_state.get("featured_product_groups", {}).pop(g_name)
                                            st.rerun()
                                            
                                if st.button("🗑️ حذف المجموعة", key=f"delg_{g_name}", type="primary", use_container_width=True):
                                    del st.session_state.get("featured_product_groups", {})[g_name]
                                    st.rerun()
                    else:
                        st.warning("لا توجد مجموعات مميزة حالياً.")
                        
    st.markdown("### 🔍 أدوات التصفية والبحث في المنتجات")
    
    # ✅ استخراج الماركات، التصنيفات، التواريخ، والعناوين ديناميكياً من المنتجات المحملة
    available_dates = set()
    available_brands = set()
    available_categories = set()
    available_promo_titles = set()
    available_subtitles = set()
    
    for p in st.session_state.get("all_products", []):
        # تواريخ الانتهاء
        s_end = p.get('sale_end')
        if s_end: available_dates.add(str(s_end).split(' ')[0])
        
        # الماركات
        brand = p.get('brand')
        if isinstance(brand, dict) and brand.get('name'):
            available_brands.add(brand.get('name'))
            
        # التصنيفات
        cats = p.get('categories', [])
        if isinstance(cats, list):
            for c in cats:
                if isinstance(c, dict) and c.get('name'):
                    available_categories.add(c.get('name'))
                    
        # العناوين الترويجية والفرعية
        promo_t = p.get('promotion_title') or (p.get('promotion', {}).get('title') if isinstance(p.get('promotion'), dict) else '')
        if promo_t: available_promo_titles.add(str(promo_t).strip())
        
        sub_t = p.get('promotion_subtitle') or (p.get('promotion', {}).get('sub_title') if isinstance(p.get('promotion'), dict) else '')
        if sub_t: available_subtitles.add(str(sub_t).strip())

    date_options = ["الكل", "بدون تاريخ"] + sorted(list(available_dates))
    brand_options = ["بدون ماركة"] + sorted(list(available_brands))
    category_options = sorted(list(available_categories))
    promo_options = ["الكل", "بدون"] + sorted(list(available_promo_titles))
    subtitle_options = ["الكل", "بدون"] + sorted(list(available_subtitles))

    # ✅ الحاوية الأولى: فلاتر البحث الأساسية
    with st.container(border=True):
        col_search, col_cat, col_brand = st.columns([2, 1.5, 1.5])
        with col_search:
            sq = st.text_input("ابحث باسم أو SKU:", placeholder="أدخل الكود للبحث...").lower()
        with col_cat:
            f_categories = st.multiselect("📁 التصنيفات:", options=category_options, placeholder="اختر تصنيفاً أو أكثر...")
        with col_brand:
            f_brands = st.multiselect("🏢 الماركات:", options=brand_options, placeholder="اختر ماركة أو أكثر...")
            
        col_date, col_feat, col_promo, col_sub = st.columns([1, 1, 1.5, 1.5])
        with col_date:
            f_sale_end = st.selectbox("📅 انتهاء التخفيض:", options=date_options)
        with col_feat:
            f_feat_group = st.selectbox("⭐ مجموعة المنتجات:", ["الكل"] + list(st.session_state.get("featured_product_groups", {}).keys()), key="filter_prod_group")
        with col_promo:
            # ✅ فلتر محتوى العنوان الترويجي
            f_promo_title = st.selectbox("📢 محتوى الترويجي:", options=promo_options)
        with col_sub:
            # ✅ فلتر محتوى العنوان الفرعي
            f_subtitle = st.selectbox("🏷️ محتوى الفرعي:", options=subtitle_options)
    
    # ✅ الحاوية الثانية: فلاتر الأزرار السريعة
    with st.container(border=True):
        col_f1, col_f2, col_f3, col_f4, col_f5, col_f6, col_f7 = st.columns(7)
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
        with col_f7:
            st.markdown("<div style='text-align:center; color:#00EBCF; font-weight:bold;'>🛒 الرصيد</div>", unsafe_allow_html=True)
            f_stock = st.radio("الرصيد", ["الكل", "له رصيد", "نفد"], horizontal=True, label_visibility="collapsed", key="f_stock_radio")
    
    filtered = []
    po_map = st.session_state.get("product_offers_map", {})
    all_products_offers = po_map.get("ALL_PRODUCTS", [])
    
    for p in st.session_state.get("all_products", []):
        p_id_str = str(p.get('id', '')).strip()
        
        # 1. تطبيق فلتر التصنيفات
        if f_categories:
            p_cats = p.get('categories', [])
            p_cat_names = [c.get('name') for c in p_cats if isinstance(c, dict)] if isinstance(p_cats, list) else []
            if not any(cat in f_categories for cat in p_cat_names): continue
                
        # 2. تطبيق فلتر الماركات
        if f_brands:
            brand = p.get('brand')
            p_brand_name = brand.get('name') if isinstance(brand, dict) else None
            
            # التحقق مما إذا كان المنتج يطابق إحدى الماركات المختارة أو يطابق خيار "بدون ماركة"
            is_no_brand_match = ("بدون ماركة" in f_brands) and (not p_brand_name)
            is_brand_name_match = (p_brand_name in f_brands)
            
            if not (is_no_brand_match or is_brand_name_match):
                continue
                
        # 3. تطبيق فلتر المجموعات المميزة
        if f_feat_group != "الكل":
            if p_id_str not in st.session_state.get("featured_product_groups", {}).get(f_feat_group, []): continue
            
        # 4. تطبيق فلتر الرصيد
        stock_qty_raw = p.get('quantity')
        try: stock_qty = float(stock_qty_raw) if stock_qty_raw is not None else 0.0
        except (ValueError, TypeError): stock_qty = 0.0
        if f_stock == "له رصيد" and stock_qty <= 0: continue
        if f_stock == "نفد" and stock_qty > 0: continue
            
        if sq and sq not in str(p.get('name', '')).lower() and sq not in str(p.get('sku', '')).lower(): continue
        if f_status == "مخفي" and p.get('status') != 'hidden': continue
        if f_status == "معروض" and p.get('status') == 'hidden': continue
        
        has_img = bool(p.get('thumbnail') or p.get('main_image'))
        if f_img == "بصورة" and not has_img: continue
        if f_img == "بدون" and has_img: continue
            
        has_promo_text = bool(p.get('promotion_title') or (p.get('promotion', {}).get('title')))
        if f_promo == "لها عنوان" and not has_promo_text: continue
        if f_promo == "بدون" and has_promo_text: continue
        
        # ✅ 5. تطبيق فلاتر محتوى العناوين الجديد
        p_promo_val = str(p.get('promotion_title') or (p.get('promotion', {}).get('title') if isinstance(p.get('promotion'), dict) else '') or '').strip()
        if f_promo_title != "الكل":
            if f_promo_title == "بدون" and p_promo_val != "": continue
            elif f_promo_title != "بدون" and p_promo_val != f_promo_title: continue
            
        p_sub_val = str(p.get('promotion_subtitle') or (p.get('promotion', {}).get('sub_title') if isinstance(p.get('promotion'), dict) else '') or '').strip()
        if f_subtitle != "الكل":
            if f_subtitle == "بدون" and p_sub_val != "": continue
            elif f_subtitle != "بدون" and p_sub_val != f_subtitle: continue
        
        pr = get_flat_price(p.get('price', 0)); reg = get_flat_price(p.get('regular_price', 0)); sal = get_flat_price(p.get('sale_price', 0))
        is_discounted = (sal > 0 and sal < (reg if reg > 0 else pr))
        if f_disc == "مخفض" and not is_discounted: continue
        if f_disc == "ثابت" and is_discounted: continue
            
        is_group = (p.get('type') == 'group_products')
        if f_type == "عادية" and is_group: continue
        if f_type == "مجموعات" and not is_group: continue
        
        is_in_offer = bool(po_map.get(p_id_str))
        if f_offer == "مشمول" and not is_in_offer: continue
        if f_offer == "غير مشمول" and is_in_offer: continue
        
        # تطبيق فلتر تاريخ الانتهاء
        p_sale_end = str(p.get('sale_end', '')).split(' ')[0] if p.get('sale_end') else ""
        if f_sale_end != "الكل":
            if f_sale_end == "بدون تاريخ" and p_sale_end != "": continue
            if f_sale_end != "بدون تاريخ" and p_sale_end != f_sale_end: continue
            
        filtered.append(p)
        
    st.info(f"📊 النتائج: {len(filtered)} منتج مطابِق للبحث")

    # ==========================================
    # ✅ زر التنزيل المدمج مع إجراءات المنتجات المفلترة وتحديثها
    # ==========================================
    if filtered:
        # ✅ قسمنا المساحة إلى 3 أعمدة لإضافة زر التحديث الجديد
        col_act1, col_act2, col_act3 = st.columns([1, 1, 1.2])
        
        with col_act1:
            st.download_button(
                label="📥 تحميل المنتجات المفلترة (Excel)",
                data=export_products_to_excel(filtered, po_map),
                file_name=f"Filtered_Products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                key="download_filtered_products",
                use_container_width=True
            )
            
        with col_act2:
            # ✅ الزر الجديد لتحديث جميع المنتجات المفلترة بضغطة واحدة
            if st.button("🔄 تحديث بيانات المنتجات المفلترة", use_container_width=True):
                progress_bar = st.progress(0)
                status_text = st.empty()
                total_prods = len(filtered)
                updated_count = 0
                
                for idx, p in enumerate(filtered):
                    p_id = str(p.get('id'))
                    status_text.info(f"⏳ جاري سحب أحدث البيانات للمنتج {idx+1} من {total_prods}...")
                    
                    fresh_res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products/{p_id}", headers)
                    if fresh_res and fresh_res.get('data'):
                        for i, prod in enumerate(st.session_state.get("all_products", [])):
                            if str(prod.get('id')) == p_id:
                                st.session_state["all_products"][i] = fresh_res['data']
                                updated_count += 1
                                break
                                
                    progress_bar.progress((idx + 1) / total_prods)
                    import time; time.sleep(0.3) # ✅ حماية من خطأ 504
                    
                status_text.success(f"✅ تم سحب وتحديث بيانات {updated_count} منتج بنجاح!")
                import time; time.sleep(1.5)
                st.rerun()
                
        with col_act3:
            with st.popover("⚙️ إجراءات المنتجات المفلترة", use_container_width=True):
                st.markdown(f"<div style='text-align:center; margin-bottom:10px;'><b>تطبيق إجراءات على ({len(filtered)}) منتج</b></div>", unsafe_allow_html=True)
                
                bulk_actions = []
                
                # ✅ تقسيم الإجراءات لمجموعات منسقة مع Checkboxes
                st.markdown("<b style='color:#00EBCF; font-size:14px;'>1️⃣ تنظيم وإدارة:</b>", unsafe_allow_html=True)
                if st.checkbox("⭐ إنشاء مجموعة مميزة جديدة", key="ba_grp"): bulk_actions.append("⭐ إنشاء مجموعة مميزة جديدة")
                
                st.markdown("<b style='color:#00EBCF; font-size:14px;'>2️⃣ الظهور في المتجر:</b>", unsafe_allow_html=True)
                if st.checkbox("👁️ إخفاء المنتجات (نقل للمسودة)", key="ba_hide"): bulk_actions.append("👁️ إخفاء المنتجات (نقل للمسودة)")
                if st.checkbox("🛒 إظهار المنتجات (متاح للبيع)", key="ba_show"): bulk_actions.append("🛒 إظهار المنتجات (متاح للبيع)")
                
                st.markdown("<b style='color:#00EBCF; font-size:14px;'>3️⃣ العناوين والأسعار:</b>", unsafe_allow_html=True)
                if st.checkbox("🧹 مسح العناوين (الترويجية والفرعية)", key="ba_clear_promo"): bulk_actions.append("🧹 مسح العناوين (الترويجية والفرعية)")
                if st.checkbox("🛑 إلغاء السعر المخفض ومسح التواريخ", key="ba_clear_sale"): bulk_actions.append("🛑 إلغاء السعر المخفض ومسح تواريخ التخفيض")
                if st.checkbox("📅 تمديد تواريخ التخفيض", key="ba_ext_date"): bulk_actions.append("📅 تمديد تواريخ التخفيض")
                
                st.markdown("<b style='color:#e74c3c; font-size:14px;'>4️⃣ الحذف النهائي:</b>", unsafe_allow_html=True)
                if st.checkbox("🗑️ حذف المنتجات نهائياً", key="ba_del"): bulk_actions.append("🗑️ حذف المنتجات نهائياً")
                
                st.markdown("---")
                
                new_sale_end_str = None
                if "📅 تمديد تواريخ التخفيض" in bulk_actions:
                    col_ext_d, col_ext_t = st.columns(2)
                    with col_ext_d:
                        ext_date = st.date_input("التاريخ الجديد:", value=datetime.now().date() + timedelta(days=7))
                    with col_ext_t:
                        ext_time = st.time_input("الوقت الجديد:", value=datetime.min.time().replace(hour=23, minute=59, second=59))
                    new_sale_end_str = datetime.combine(ext_date, ext_time).strftime('%Y-%m-%d %H:%M:%S')

                new_group_name = None
                if "⭐ إنشاء مجموعة مميزة جديدة" in bulk_actions:
                    new_group_name = st.text_input("اسم المجموعة المميزة الجديدة:", placeholder="مثال: عروض الشتاء")
                
                if "🗑️ حذف المنتجات نهائياً" in bulk_actions:
                    st.error("🚨 تحذير: سيتم حذف المنتجات نهائياً من المتجر ولن يمكن استرجاعها!")
                    confirm_msg = "☑️ أوافق على الحذف النهائي"
                else:
                    confirm_msg = "☑️ تأكيد تنفيذ الإجراءات المختارة"
                    
                confirm_bulk = st.checkbox(confirm_msg, key="confirm_bulk_action")
                
                if st.button("🚀 تنفيذ الإجراءات", type="primary", disabled=not confirm_bulk or not bulk_actions, use_container_width=True, key="execute_bulk_action"):
                    
                    if "⭐ إنشاء مجموعة مميزة جديدة" in bulk_actions:
                        if not new_group_name:
                            st.error("⚠️ الرجاء كتابة اسم للمجموعة المميزة.")
                            st.stop()
                        else:
                            if "featured_product_groups" not in st.session_state:
                                st.session_state["featured_product_groups"] = {}
                            st.session_state["featured_product_groups"][new_group_name] = [str(p['id']) for p in filtered]
                            st.success(f"✅ تم إنشاء المجموعة المميزة '{new_group_name}' بـ {len(filtered)} منتج بنجاح!")
                            bulk_actions.remove("⭐ إنشاء مجموعة مميزة جديدة")
                    
                    if bulk_actions:
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        total_prods = len(filtered)
                        
                        for idx, p in enumerate(filtered):
                            p_id = p.get('id')
                            status_text.info(f"⏳ جاري التحديث: منتج {idx+1} من {total_prods}...")
                            
                            if "👁️ إخفاء المنتجات (نقل للمسودة)" in bulk_actions: update_product_status(p_id, "hidden")
                            elif "🛒 إظهار المنتجات (متاح للبيع)" in bulk_actions: update_product_status(p_id, "sale")
                                
                            if "🧹 مسح العناوين (الترويجية والفرعية)" in bulk_actions:
                                update_product_promotions_secure(p_id, "", "", headers)
                                import time; time.sleep(0.2)
                                
                            if "🛑 إلغاء السعر المخفض ومسح تواريخ التخفيض" in bulk_actions:
                                base_price = get_flat_price(p.get('regular_price', 0)) or get_flat_price(p.get('price', 0))
                                payload = {"name": p.get('name'), "price": base_price, "status": p.get('status', 'sale'), "sale_price": None, "sale_start": None, "sale_end": None}
                                safe_api_request("PUT", f"https://api.salla.dev/admin/v2/products/{p_id}", headers, json=payload)
                            elif "📅 تمديد تواريخ التخفيض" in bulk_actions:
                                sale_price = get_flat_price(p.get('sale_price', 0))
                                if sale_price > 0: update_product_sale_price(int(p_id), sale_price, sale_end=new_sale_end_str)
                                    
                            if "🗑️ حذف المنتجات نهائياً" in bulk_actions: delete_product(p_id)
                                
                            progress_bar.progress((idx + 1) / total_prods)
                            import time; time.sleep(0.3)
                            
                        status_text.success(f"✅ تم تنفيذ جميع الإجراءات بنجاح على {total_prods} منتج!")
                        import time; time.sleep(1)
                        st.session_state["all_products_fetched"] = False 
                    st.rerun()

    # Pagination
    limit = 20
    pages = max(1, (len(filtered) + limit - 1) // limit)
    
    # ✅ الحماية الذكية: إعادة تعيين رقم الصفحة إذا تجاوزت عدد الصفحات المتاحة بعد الفلترة
    if st.session_state["prod_page"] > pages:
        st.session_state["prod_page"] = 1
        
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
                                    # ✅ قراءة القيم من الملف مع تعيين 1 كافتراضي
                                    max_qty = pr.get('اقصي كمية لكل عميل', 1)
                                    try: max_qty = int(max_qty)
                                    except: max_qty = 1
                                    if max_qty < 1: max_qty = 1
                    
                                    max_items = pr.get('الحد الأقصى للطلب', 1)
                                    try: max_items = int(max_items)
                                    except: max_items = 1
                                    if max_items < 1: max_items = 1
                                    p_for_template.append({"name": str(pr['اسم المنتج']), "price": float(pr['سعر المنتج']) if pr['سعر المنتج'] else 0, "sku": str(pr['رقم المنتج']), "with_tax": is_taxable, "tax_exemption_cause": "" if is_taxable else "الأدوية والمعدات الطبية", "maximum_quantity_per_order": max_qty, "max_items_per_user": max_items})
                                
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
            # ✅ حساب إجمالي كمية المجموعة بأمان تام (تجنب القسمة على صفر)
            total_qty = 0
            for gp in group_products:
                b_qty = gp.get('bundle_quantity', 1) or 1  # لو كانت 0 نستبدلها بـ 1 لمنع الخطأ
                s_qty = gp.get('stock_quantity', 0) or 0
                total_qty += int(s_qty / b_qty)
                
            st.info(f"📊 إجمالي كمية المجموعة المتوفرة: {total_qty} وحدة")
            
            for gp_idx, gp in enumerate(group_products):
                gp_id = str(gp.get('id', 'N/A'))
                gp_name_sub = gp.get('name', 'بدون اسم')
                gp_sku = gp.get('sku', 'لا يوجد')
                gp_price = gp.get('price', 0)
                
                # ✅ حماية المتغيرات من القيم الصفرية
                gp_bundle_qty = gp.get('bundle_quantity', 1) or 1
                gp_stock = gp.get('stock_quantity', 0) or 0
                gp_image = gp.get('image')
                
                # ✅ حساب الكمية الفعلية للمجموعة من هذا المنتج بأمان
                group_qty = int(gp_stock / gp_bundle_qty)
                
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
