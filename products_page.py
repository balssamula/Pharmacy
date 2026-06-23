import streamlit as st
from utils import get_headers, safe_api_request, get_product_price, update_product_status

def render_products_page():
    st.markdown("<h2 style='color:#0f1c2e;'>📦 مركز جرد المستودع والمنتجات الذكي</h2>", unsafe_allow_html=True)
    
    headers = get_headers()
    if not headers: return

    with st.spinner("🔄 جاري تحميل جرد المنتجات الحالي من المتجر..."):
        prod_res = safe_api_request("GET", "https://api.salla.dev/admin/v2/products", headers)
    
    if prod_res and prod_res.get("data"):
        products = prod_res["data"]
        search_query = st.text_input("🔍 ابحث برقم الـ SKU، الاسم أو المعرف للمنتج:")
        
        for idx, p in enumerate(products):
            p_id = p.get('id', 'N/A')
            p_name = p.get('name', 'منتج بدون اسم')
            p_sku = p.get('sku', 'لا يوجد')
            status = p.get('status', 'sale')
            p_url = p.get('url', 'https://salla.sa')
            
            # استخراج عنوان التروييج بدقة من الكائن المدمج وفقاً لـ Product.md
            p_promotion = p.get('promotion_title', '')
            if not p_promotion and isinstance(p.get('promotion'), dict):
                p_promotion = p.get('promotion', {}).get('title', '')
            
            if search_query and (search_query.lower() not in p_name.lower() and search_query not in str(p_sku) and search_query not in str(p_id)):
                continue
                
            # حساب تفاصيل التسعير بدقة حسابية كاملة وموثوقة
            price = get_product_price(p)
            sale_price_obj = p.get('sale_price', {})
            sale_price = sale_price_obj.get('amount', 0) if isinstance(sale_price_obj, dict) else float(sale_price_obj or 0)
            
            has_discount = 0 < sale_price < price
            discount_percent = int(((price - sale_price) / price) * 100) if has_discount and price > 0 else 0
            
            # تصميم ترويسة حاوية المنتج الملونة والداكنة الفاخرة
            disp_status = "🟢 معروض بالكامل للعملاء" if status == "sale" else "🔴 مخفي ومؤرشف"
            st.markdown(f"""
                <div style="background: linear-gradient(135deg, #243b55 0%, #141e30 100%); 
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
                
                c_info, c_pricing, c_action = st.columns([3, 3, 2])
                
                with c_info:
                    st.markdown(f"🆔 **معرف المنتج الموحد:** `{p_id}`")
                    st.markdown(f"🔢 **الرمز المخزني SKU:** `{p_sku}`")
                    st.markdown(f"🏷️ **العنوان الترويجي:** `{(p_promotion if p_promotion else 'لا يوجد حالياً')}`")
                    st.markdown(f"🔗 [🌐 معاينة وتصفح رابط المنتج في المتجر]({p_url})")
                    st.markdown(f"📦 **المخزون:** `{p.get('quantity', 0)}` | 📈 **المبيعات:** `{p.get('sold_quantity', 0)}`")
                
                with c_pricing:
                    st.markdown("<b style='color:#2c3e50;'>💰 هيكل وحاوية بيانات التسعير الفعلي:</b>", unsafe_allow_html=True)
                    if has_discount:
                        st.markdown(f"""
                        <div style="background:#fff3cd; padding:12px; border-radius:8px; border-right:5px solid #ffc107;">
                            <span style="text-decoration: line-through; color: #7f8c8d; font-size:13px;">السعر الأصلي الأساسي: {price:,.2f} SAR</span><br>
                            <b style="color: #c0392b; font-size:16px;">السعر المخفض النشط: {sale_price:,.2f} SAR</b><br>
                            <span style="background:#c0392b; color:#fff; padding:2px 7px; border-radius:4px; font-size:11px; font-weight:bold;">نسبة التخفيض الحالية: {discount_percent}% خصم 🔥</span>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div style="background:#e2e8f0; padding:12px; border-radius:8px; border-right:5px solid #4a5568;">
                            <b style="color:#2d3748; font-size:15px;">السعر الأصلي الحالي: {price:,.2f} SAR</b><br>
                            <span style="color:#718096; font-size:12px;">(المنتج يباع بالقيمة الكاملة، لا توجد خصومات)</span>
                        </div>
                        """, unsafe_allow_html=True)
                        
                with c_action:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("📋 نسخ معرف المنتج", key=f"cp_{p_id}_{idx}", use_container_width=True):
                        st.toast(f"✅ تم نسخ المعرف بنجاح: {p_id}")
                        
                    # زر اخفاء وعرض من المتجر المطور بالربط الجديد والآمن
                    target_st = "hidden" if status == "sale" else "sale"
                    btn_lbl = "👁️ إخفاء الفوري من المتجر" if status == "sale" else "👁️ إظهار الفوري بالمتجر"
                    btn_type = "primary" if status == "sale" else "secondary"
                    
                    if st.button(btn_lbl, key=f"sh_{p_id}_{idx}", type=btn_type, use_container_width=True):
                        with st.spinner("جاري حفظ الربط مع سلة..."):
                            if update_product_status(p_id, target_st):
                                st.success("✅ تم تحديث ونشر ظهور المنتج بنجاح!")
                                st.rerun()
                            else:
                                st.error("❌ فشل عملية التحديث، تواصل مع الدعم الفني.")
                                
                    # تعديل العنوان الترويجي الفردي السريع
                    with st.popover("✏️ تعديل الترويج"):
                        new_promo = st.text_input("أدخل العنوان الترويجي للمنتج:", value=p_promotion)
                        if st.button("تأكيد وحفظ للعنوان الترويجي", key=f"p_pr_{p_id}_{idx}"):
                            safe_api_request("PUT", f"https://api.salla.dev/admin/v2/products/{p_id}", headers, json={"promotion_title": new_promo, "price": price})
                            st.rerun()

                st.markdown("</div>", unsafe_allow_html=True)
