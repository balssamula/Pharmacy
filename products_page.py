import streamlit as st
from utils import get_headers, safe_api_request, get_product_price, export_products_to_excel

def render_products_page():
    st.markdown("<h2 style='color:#0f1c2e;'>📦 مركز جرد المنتجات والتحكم الذكي</h2>", unsafe_allow_html=True)
    
    headers = get_headers()
    if not headers: return

    with st.spinner("🔄 جاري تحديث بيانات المستودع الفعلي..."):
        prod_res = safe_api_request("GET", "https://api.salla.dev/admin/v2/products", headers)
    
    if prod_res and prod_res.get("data"):
        products = prod_res["data"]
        
        # زر تصدير للمستودع
        if st.button("📥 تصدير قائمة جرد المستودع الحالية إلى Excel"):
            ex_data = export_products_to_excel(products)
            st.download_button("اضغط لتحميل ملف الجرد", ex_data, "Inventory_Report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            
        search_query = st.text_input("🔍 ابحث عن منتج بالاسم، بالمعرف أو بالـ SKU:")
        
        for idx, p in enumerate(products):
            p_id = p.get('id', 'N/A')
            p_name = p.get('name', 'منتج بدون اسم')
            p_sku = p.get('sku', 'لا يوجد')
            status = p.get('status', 'sale')
            
            if search_query and (search_query.lower() not in p_name.lower() and search_query not in str(p_sku) and search_query not in str(p_id)):
                continue
                
            # حسابات الأسعار والخصومات الاحترافية
            price = get_product_price(p)
            sale_price_obj = p.get('sale_price', {})
            sale_price = sale_price_obj.get('amount', 0) if isinstance(sale_price_obj, dict) else float(sale_price_obj or 0)
            
            has_discount = 0 < sale_price < price
            discount_percent = int(((price - sale_price) / price) * 100) if has_discount and price > 0 else 0
            
            # --- تصميم ترويسة المنتج الداكنة وحاوية البيانات المنفصلة ---
            disp_status = "🟢 معروض للعملاء" if status == "sale" else "🔴 مخفي في المسودة"
            
            st.markdown(f"""
                <div style="background: linear-gradient(135deg, #1f2d3d 0%, #34495e 100%); 
                            padding: 12px 20px; border-radius: 12px 12px 0px 0px; 
                            margin-top: 25px; display: flex; justify-content: space-between; align-items: center; border-bottom: 3px solid #e67e22;">
                    <span style="color: #ffffff; font-weight: bold; font-size: 15px;">📦 {p_name}</span>
                    <span style="background: rgba(255,255,255,0.2); color: #fff; padding: 3px 10px; border-radius: 15px; font-size: 12px;">{disp_status}</span>
                </div>
            """, unsafe_allow_html=True)
            
            with st.container():
                st.markdown("""
                    <div style="background-color: #fafbfc; padding: 20px; border-radius: 0px 0px 12px 12px; 
                                border: 1px solid #e1e8ed; border-top: none; box-shadow: 0 4px 10px rgba(0,0,0,0.03); margin-bottom: 25px;">
                """, unsafe_allow_html=True)
                
                col_info, col_pricing, col_action = st.columns([3, 3, 2])
                
                with col_info:
                    st.markdown(f"🆔 **معرف المنتج الموحد:** `{p_id}`")
                    st.markdown(f"🔢 **رقم الرمز المخزني (SKU):** `{p_sku}`")
                    st.markdown(f"📦 **المخزون المتوفر:** `{p.get('quantity', 0)} حبة`")
                    st.markdown(f"📈 **إجمالي المبيعات المنجزة:** `{p.get('sold_quantity', 0)} حبة`")
                
                with col_pricing:
                    st.markdown("<b style='color:#2c3e50;'>💰 تفاصيل التسعير والخصم:</b>", unsafe_allow_html=True)
                    if has_discount:
                        st.markdown(f"""
                        <div style="background:#fff3cd; padding:10px; border-radius:8px; border-right:4px solid #ffc107;">
                            <span style="text-decoration: line-through; color: #888; font-size:13px;">السعر الأساسي: {price:,.2f} SAR</span><br>
                            <b style="color: #d9534f; font-size:16px;">السعر المخفض الحالي: {sale_price:,.2f} SAR</b><br>
                            <span style="background:#d9534f; color:#fff; padding:2px 6px; border-radius:4px; font-size:11px; font-weight:bold;">وفرت نسبة: {discount_percent}% 🔥</span>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div style="background:#e2e8f0; padding:10px; border-radius:8px; border-right:4px solid #4a5568;">
                            <b style="color:#2d3748;">السعر الثابت: {price:,.2f} SAR</b><br>
                            <span style="color:#718096; font-size:12px;">(لا يوجد خصم نشط حالياً على هذا المنتج)</span>
                        </div>
                        """, unsafe_allow_html=True)
                
                with col_action:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("📋 نسخ المعرف السريع", key=f"cp_{p_id}_{idx}", use_container_width=True):
                        st.toast(f"✅ تم نسخ الـ ID للمنتج: {p_id}")
                    
                    target_st = "hidden" if status == "sale" else "sale"
                    lbl_btn = "👁️ إخفاء من المتجر" if status == "sale" else "👁️ عرض بالمتجر"
                    if st.button(lbl_btn, key=f"stat_{p_id}_{idx}", use_container_width=True):
                        # تحديث الحالة مع تجنب خطأ 422 بإرسال السعر الحالي
                        safe_api_request("PUT", f"https://api.salla.dev/admin/v2/products/{p_id}", headers, json={"status": target_st, "price": price})
                        st.rerun()

                st.markdown("</div>", unsafe_allow_html=True)
