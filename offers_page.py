import streamlit as st
from datetime import datetime
import pandas as pd
from utils import (
    get_headers, safe_api_request, SALLA_API_URL, generate_salla_excel_template,
    process_excel_import, export_offers_to_excel, safe_parse_date, parse_products_cleanly
)

def render_offers_page():
    st.markdown("<h2 style='color:#0f1c2e;'>📊 لوحة إدارة وتصفية العروض الحالية</h2>", unsafe_allow_html=True)
    
    headers = get_headers()
    if not headers: return

    col_dl, col_ex = st.columns([1, 1])
    with col_dl:
        st.download_button(
            label="📥 تنزيل نموذج الاستيراد المنسق الاحترافي",
            data=generate_salla_excel_template(),
            file_name="Salla_Offers_Template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
    with st.spinner("جاري مزامنة بيانات العروض الحالية..."):
        res_all = safe_api_request("GET", SALLA_API_URL, headers)
        raw_offers = res_all.get("data", []) if res_all else []
        
    with col_ex:
        if raw_offers:
            st.download_button(
                label="📥 تصدير قائمة العروض المنسقة الحالية",
                data=export_offers_to_excel(raw_offers),
                file_name=f"offers_export_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

    uploaded_file = st.file_uploader("📂 تحميل ملف عروض جماعي (XLSX) للاستيراد المباشر:", type=["xlsx"])
    if uploaded_file:
        try:
            df_user = pd.read_excel(uploaded_file)
            st.dataframe(df_user, use_container_width=True)
            if st.button("🚀 تأكيد معالجة ونشر الملف الجماعي المرفوع", use_container_width=True):
                res = process_excel_import(df_user)
                for m in res["success"]: st.success(m)
                for m in res["errors"]: st.error(m)
                st.rerun()
        except Exception as e:
            st.error(f"خطأ في قراءة ملف الإكسيل: {str(e)}")

    st.divider()

    # --- استرجاع وتعديل حقول الإنشاء لتصبح الخلايا متغيرة ديناميكياً حسب نوع العرض المختار ---
    with st.expander("➕ إنشاء عرض ترويجي جديد متكامل", expanded=False):
        st.markdown("### 📝 تفاصيل العرض الأساسية")
        c1, c2 = st.columns(2)
        with c1:
            new_offer_name = st.text_input("اسم العرض الحصري الجديد:")
            new_offer_type = st.selectbox("نوع وهيكل العرض المعتمد لدى سلة:", ["buy_x_get_y", "percentage", "fixed_amount"], key="creation_type_box")
            new_applied_to = st.selectbox("تطبيق نطاق وبث العرض على:", ["product", "category", "order"])
            new_with_coupon = st.selectbox("هل يتطلب هذا العرض استخدام كوبون؟", ["لا", "نعم"])
        with c2:
            new_message = st.text_input("الرسالة التسويقية الترويجية (تظهر للعميل في السلة):")
            new_offer_status = st.selectbox("حالة تشغيل وبث العرض التلقائية:", ["active", "inactive"], format_func=lambda x: "مفعل فوراً بالمتجر" if x == "active" else "حفظ كمسودة غير نشطة")
            new_start_date = st.text_input("توقيت بدء العرض الفعلي:", value=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            new_expiry_date = st.text_input("توقيت انتهاء العرض التلقائي:", value="2026-12-31 23:59:59")
            
        st.markdown("#### 🛒 شروط ومجموعات حقول العرض المتغيرة")
        
        # خلايا متغيرة وذكية تتكيف ديناميكياً لتطابق وثائق سلة المرفقة
        if new_offer_type == "buy_x_get_y":
            col_bx, col_by = st.columns(2)
            with col_bx:
                new_buy_type = st.selectbox("نوع مادة الشراء X:", ["product", "category"])
                new_buy_qty = st.number_input("الكمية المطلوب شراؤها من العميل (X):", min_value=1, value=1)
                new_buy_products = st.text_input("قائمة معرفات الـ IDs لمنتجات الشراء المشمولة (مفصولة بفاصلة ,):")
            with col_by:
                new_get_type = st.selectbox("نوع صنف الهدية الممنوحة Y:", ["product", "category"])
                new_get_qty = st.number_input("كمية القطع الممنوحة مجاناً للعميل (Y):", min_value=1, value=1)
                new_get_products = st.text_input("قائمة معرفات الـ IDs لمنتجات الهدية الممنوحة (مفصولة بفاصلة ,):")
            new_discount_type = "free-product"
            new_discount_amount = 0.0
        else:
            # عروض التخفيض المباشر للنسبة أو المبلغ المقطوع
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                new_discount_amount = st.number_input("قيمة أو نسبة التخفيض المالي للعرض:", min_value=0.5, value=10.0)
                new_buy_products = st.text_input("قائمة الـ IDs للمنتجات الخاضعة للتخفيض المباشر (مفصولة بفاصلة ,):")
            with col_p2:
                st.markdown("<br><p style='color:#777; font-size:12px;'>عروض النسبة والمبالغ المقطوعة تطبق بشكل فوري ومباشر على أصناف المستودع المحددة دون اشتراط هدايا معها.</p>", unsafe_allow_html=True)
            new_buy_type = "product"
            new_buy_qty = 1
            new_get_type = "product"
            new_get_qty = 1
            new_discount_type = "percentage" if new_offer_type == "percentage" else "fixed_amount"
        
        if st.button("🚀 اعتماد وتدوين العرض الجديد ونشره فوراً", type="primary", use_container_width=True, key="save_new_offer_green"):
            try:
                b_ids = [int(i.strip()) for i in new_buy_products.split(",") if i.strip().isdigit()]
                payload = {
                    "name": new_offer_name, "offer_type": new_offer_type, "message": new_message,
                    "applied_channel": "browser_and_application", "applied_to": new_applied_to,
                    "start_date": new_start_date, "expiry_date": new_expiry_date, "status": new_offer_status,
                    "applied_with_coupon": new_with_coupon == "نعم",
                    "buy": {"type": new_buy_type, "quantity": int(new_buy_qty), "products": b_ids},
                    "get": {"type": new_get_type, "quantity": int(new_get_qty), "discount_type": new_discount_type}
                }
                if new_offer_type == "buy_x_get_y":
                    g_ids = [int(i.strip()) for i in new_get_products.split(",") if i.strip().isdigit()]
                    payload["get"]["products"] = g_ids
                elif new_discount_amount > 0:
                    payload["get"]["discount_amount"] = float(new_discount_amount)
                    
                if safe_api_request("POST", SALLA_API_URL, headers, json=payload):
                    st.success("✅ تم تدوين وإنشاء العرض الترويجي المتكامل بنجاح!")
                    st.rerun()
            except Exception as e:
                st.error(f"فشل في تدوين العرض الجديد: {str(e)}")

    st.divider()

    # --- أدوات التصفية وتحديث فلتر تاريخ الانتهاء ليطابق اليوم المدخل حصراً ---
    st.markdown("#### 🔍 أدوات التصفية والبحث المتقدمة عن العروض")
    f1, f2, f3 = st.columns(3)
    with f1: search_offer = st.text_input("🔎 ابحث باسم العرض أو بالمعرف الرقمي:")
    with f2: status_filter = st.selectbox("📌 حالة نشاط وظهور العرض بالمتجر:", ["الكل", "نشط فقط", "غير نشط فقط"])
    with f3: filter_date_str = st.text_input("📅 ابحث عن تاريخ انتهاء مطابق تماماً وحصراً (YYYY-MM-DD):", placeholder="مثال: 2026-06-24")

    now = datetime.now()

    for idx, offer in enumerate(raw_offers):
        offer_id = offer.get('id', 'N/A')
        offer_name = offer.get('name', 'عرض بدون اسم')
        status = offer.get('status', 'inactive')
        exp_date = safe_parse_date(offer.get('expiry_date'))
        
        if search_offer and (search_offer.lower() not in offer_name.lower() and search_offer not in str(offer_id)): continue
        if status_filter == "نشط فقط" and status != "active": continue
        if status_filter == "غير نشط فقط" and status == "active": continue
        
        # التصفية والمطابقة الدقيقة للتاريخ المكتوب بالكامل (وليس قبله أو بعده)
        if filter_date_str.strip():
            try:
                target_date = datetime.strptime(filter_date_str.strip(), "%Y-%m-%d").date()
                if not exp_date or exp_date.date() != target_date: continue
            except ValueError:
                st.warning("⚠️ يرجى كتابة صيغة التاريخ بشكل سليم المطابق تماماً: YYYY-MM-DD")
                st.stop()
        
        is_expired = exp_date and exp_date < now
        badge = "🟢 نشط بالمتجر" if status == "active" else "🔴 متوقف حالياً"
        exp_badge = "⚠️ منتهي الصلاحية" if is_expired else "⏳ ساري الصلاحية"
        
        st.markdown(f"""
            <div style="background: linear-gradient(135deg, #0f1c2e 0%, #1a365d 100%); 
                        padding: 14px 20px; border-radius: 12px 12px 0px 0px; 
                        margin-top: 25px; display: flex; justify-content: space-between; align-items: center; 
                        flex-wrap: wrap; gap: 10px; border-bottom: 3px solid #00b4d8;">
                <span style="color: #ffffff; font-weight: bold; font-size: 16px;">🎯 {offer_name} (ID: {offer_id})</span>
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                    <span style="background: rgba(255,255,255,0.2); color: #fff; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;">{badge}</span>
                    <span style="background: rgba(255,193,7,0.25); color: #ffca28; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;">{exp_badge}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        with st.container():
            st.markdown("""
                <div style="background-color: #ffffff; padding: 20px; border-radius: 0px 0px 12px 12px; 
                            border: 1px solid #e8edf2; border-top: none; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 25px;">
            """, unsafe_allow_html=True)
            
            cx, cy = st.columns(2)
            with cx:
                st.markdown(f"**📅 توقيت بدء النشر المعتمد:** `{offer.get('start_date', 'غير محدد')}`")
                st.markdown(f"**📅 توقيت انتهاء الصلاحية:** `{offer.get('expiry_date', 'بدون تاريخ (مستمر)')}`")
            with cy:
                st.markdown(f"**🔖 متوافق ومربوط مع كوبونات؟** `{'نعم بالتأكيد' if offer.get('applied_with_coupon') else 'لا (تلقائي المفعول)'}`")
                st.markdown(f"**📢 نص الرسالة الترويجية للزبائن:** *{offer.get('message', 'لا توجد رسالة مرفقة')}*")
                
            st.markdown("<hr style='margin: 15px 0; border-top: 1px dashed #e2e8f0;'>", unsafe_allow_html=True)
            
            col_x, col_y = st.columns(2)
            with col_x:
                st.markdown("<b style='color:#0f1c2e;'>🛒 مجموعة الشراء (X) [تشمل الأسماء والمعرفات والـ SKU]:</b>", unsafe_allow_html=True)
                st.text(parse_products_cleanly(offer.get('buy', {})))
                st.caption(f"الكمية المطلوبة: {offer.get('buy', {}).get('quantity', 1)} قطعة")
            with col_y:
                st.markdown("<b style='color:#0f1c2e;'>🎁 مجموعة المنح والهدية (Y) [تشمل الأسماء والمعرفات والـ SKU]:</b>", unsafe_allow_html=True)
                st.text(parse_products_cleanly(offer.get('get', {})))
                st.caption(f"كمية المنح/الخصم: {offer.get('get', {}).get('quantity', 1)} قطعة")

            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2, b3 = st.columns(3)
            with b1:
                t_status = "inactive" if status == "active" else "active"
                lbl = "⏸️ إيقاف مفعول العرض" if status == "active" else "▶️ إعادة تفعيل وبث العرض"
                if st.button(lbl, key=f"t_st_{offer_id}_{idx}", use_container_width=True):
                    safe_api_request("PUT", f"{SALLA_API_URL}/{offer_id}/status", headers, json={"status": t_status})
                    st.rerun()
            with b2:
                if st.button("🔖 عكس التوافق مع الكوبون", key=f"t_cp_{offer_id}_{idx}", use_container_width=True):
                    safe_api_request("PUT", f"{SALLA_API_URL}/{offer_id}", headers, json={"applied_with_coupon": not offer.get('applied_with_coupon', False)})
                    st.rerun()
            with b3:
                if st.button("🗑️ حذف هذا العرض بالكامل", key=f"t_dl_{offer_id}_{idx}", use_container_width=True):
                    safe_api_request("DELETE", f"{SALLA_API_URL}/{offer_id}", headers)
                    st.rerun()

            # --- جعل خلايا ونموذج تعديل العروض تتغير وتتكيف ديناميكياً لتطابق وثائق سلة بالكامل ---
            with st.expander("✏️ تعديل ومراجعة كافة خلايا وحقول هذا العرض الترويجي", expanded=False):
                st.markdown("##### ✏️ تعديل البيانات والخيارات الأساسية")
                ed_name = st.text_input("تحديث مسمى العرض الحصري:", value=offer_name, key=f"ed_n_{offer_id}_{idx}")
                ed_msg = st.text_input("تحديث الرسالة المعروضة في السلة للزبائن:", value=offer.get('message', ''), key=f"ed_m_{offer_id}_{idx}")
                
                ec1, ec2 = st.columns(2)
                with ec1:
                    ed_type = st.selectbox("تعديل هيكل ونوع العرض المعتمد:", ["buy_x_get_y", "percentage", "fixed_amount"], index=["buy_x_get_y", "percentage", "fixed_amount"].index(offer.get('offer_type', 'buy_x_get_y')) if offer.get('offer_type', 'buy_x_get_y') in ["buy_x_get_y", "percentage", "fixed_amount"] else 0, key=f"ed_t_{offer_id}_{idx}")
                with ec2:
                    ed_coupon = st.selectbox("تعديل اشتراط الكوبون للتفعيل؟", ["لا", "نعم"], index=1 if offer.get('applied_with_coupon') else 0, key=f"ed_c_{offer_id}_{idx}")

                st.markdown("##### 🛒 تعديل مجموعات الصنف والكميات بشكل ديناميكي")
                buy_obj = offer.get('buy', {})
                get_obj = offer.get('get', {})
                
                buy_p_ids = ",".join([str(p.get('id', p)) if isinstance(p, dict) else str(p) for p in buy_obj.get('products', [])])
                get_p_ids = ",".join([str(p.get('id', p)) if isinstance(p, dict) else str(p) for p in get_obj.get('products', [])])
                
                # إظهار وتغيير الحقول حسب البناء الشرطي لنوع العرض
                if ed_type == "buy_x_get_y":
                    eq1, eq2 = st.columns(2)
                    with eq1:
                        ed_buy_type = st.selectbox("تعديل نوع شراء X:", ["product", "category"], index=0 if buy_obj.get('type') == 'product' else 1, key=f"ed_bt_{offer_id}_{idx}")
                        ed_buy_qty = st.number_input("تعديل كمية الشراء (X):", min_value=1, value=int(buy_obj.get('quantity', 1)), key=f"ed_bq_{offer_id}_{idx}")
                        ed_buy_products = st.text_input("تعديل الـ IDs لمنتجات الشراء المشمولة:", value=buy_p_ids, key=f"ed_bp_ids_{offer_id}_{idx}")
                    with eq2:
                        ed_get_type = st.selectbox("تعديل نوع هدية Y:", ["product", "category"], index=0 if get_obj.get('type') == 'product' else 1, key=f"ed_gt_{offer_id}_{idx}")
                        ed_get_qty = st.number_input("تعديل كمية الهدية (Y):", min_value=1, value=int(get_obj.get('quantity', 1)), key=f"ed_gq_{offer_id}_{idx}")
                        ed_get_products = st.text_input("تعديل الـ IDs لمنتجات الهدية المشمولة:", value=get_p_ids, key=f"ed_gp_ids_{offer_id}_{idx}")
                    ed_disc_type = "free-product"
                    ed_disc_amt = 0.0
                else:
                    eq1, eq2 = st.columns(2)
                    with eq1:
                        ed_disc_amt = st.number_input("تعديل قيمة أو نسبة الخصم المالي المباشر:", min_value=0.5, value=float(get_obj.get('discount_amount', 10.0)), key=f"ed_da_{offer_id}_{idx}")
                        ed_buy_products = st.text_input("تعديل الـ IDs للمنتجات المشمولة بالتخفيض الفوري:", value=buy_p_ids, key=f"ed_bp_direct_{offer_id}_{idx}")
                    with eq2:
                        st.caption("ملاحظة: هذا العرض مالي مباشر ولا يتطلب منتجات هدايا تابعة.")
                    ed_buy_type = "product"
                    ed_buy_qty = 1
                    ed_get_type = "product"
                    ed_get_qty = 1
                    ed_get_products = ""
                    ed_disc_type = "percentage" if ed_type == "percentage" else "fixed_amount"

                et1, et2 = st.columns(2)
                with et1: ed_start = st.text_input("تحديث تاريخ بدء العرض الترويجي:", value=offer.get('start_date', ''), key=f"ed_s_dt_{offer_id}_{idx}")
                with et2: ed_end = st.text_input("تحديث تاريخ انتهاء العرض الترويجي:", value=offer.get('expiry_date', ''), key=f"ed_e_dt_{offer_id}_{idx}")
                
                if st.button("💾 اعتماد وحفظ تفاصيل هذا العرض المحدث حالياً", key=f"sv_of_{offer_id}_{idx}", type="primary", use_container_width=True):
                    try:
                        b_p_list = [int(i.strip()) for i in ed_buy_products.split(",") if i.strip().isdigit()]
                        update_payload = {
                            "name": ed_name, "message": ed_msg, "start_date": ed_start, "expiry_date": ed_end,
                            "status": status, "offer_type": ed_type, "applied_with_coupon": ed_coupon == "نعم",
                            "buy": {"type": ed_buy_type, "quantity": int(ed_buy_qty), "products": b_p_list},
                            "get": {"type": ed_get_type, "quantity": int(ed_get_qty), "discount_type": ed_disc_type}
                        }
                        if ed_type == "buy_x_get_y":
                            g_p_list = [int(i.strip()) for i in ed_get_products.split(",") if i.strip().isdigit()]
                            update_payload["get"]["products"] = g_p_list
                        elif ed_disc_amt > 0:
                            update_payload["get"]["discount_amount"] = float(ed_disc_amt)
                            
                        if safe_api_request("PUT", f"{SALLA_API_URL}/{offer_id}", headers, json=update_payload):
                            st.success("✅ تم تحديث ونشر بيانات العرض الترويجي ديناميكياً!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"خطأ أثناء حفظ التحديثات: {str(e)}")
            
            st.markdown("</div>", unsafe_allow_html=True)
