import streamlit as st
from datetime import datetime
import pandas as pd
from utils import (
    get_headers, safe_api_request, SALLA_API_URL, generate_salla_excel_template,
    process_excel_import, export_offers_to_excel, safe_parse_date, parse_products_cleanly,
    OFFER_TYPES_MAP, CHANNELS_MAP
)

def render_offers_page():
    st.markdown("<h2 style='color:#0f1c2e;'>📊 لوحة إدارة وتصفية العروض الحالية</h2>", unsafe_allow_html=True)
    
    headers = get_headers()
    if not headers: return

    col_dl, col_ex = st.columns([1, 1])
    with col_dl:
        st.download_button(
            label="📥 تنزيل نموذج الاستيراد المنسق المطور (#00ebcf)",
            data=generate_salla_excel_template(),
            file_name="Salla_Offers_Template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
    with st.spinner("جاري جلب العروض الترويجية..."):
        res_all = safe_api_request("GET", SALLA_API_URL, headers)
        raw_offers = res_all.get("data", []) if res_all else []
        
    with col_ex:
        if raw_offers:
            st.download_button(
                label="📥 تصدير قائمة العروض المطابقة الحالية",
                data=export_offers_to_excel(raw_offers),
                file_name=f"offers_export_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

    uploaded_file = st.file_uploader("📂 تحميل واستيراد ملف عروض جماعي (XLSX):", type=["xlsx"])
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

    # --- حاوية إنشاء عرض جديد متكيف وتفاعلي 100% ---
    with st.expander("➕ إنشاء عرض ترويجي جديد متكامل", expanded=False):
        st.markdown("### 📝 تفاصيل العرض الأساسية")
        c1, c2 = st.columns(2)
        with c1:
            new_offer_name = st.text_input("اسم العرض الجديد:")
            # عرض الأسماء بالعربي بالكامل بناءً على طلبك ومطابقتها مع سلة
            new_offer_type_ar = st.selectbox("نوع وهيكل العرض المعتمد لدى سلة:", list(OFFER_TYPES_MAP.values()), key="creation_type_box_ar")
            new_applied_to = st.selectbox("تطبيق نطاق العرض على:", ["product", "category", "order"])
            new_with_coupon = st.selectbox("هل يتطلب هذا العرض استخدام كوبون؟", ["لا", "نعم"])
        with c2:
            new_message = st.text_input("الرسالة التسويقية للسلة:")
            new_channel_ar = st.selectbox("منصة عرض وبث العرض الحالي:", list(CHANNELS_MAP.values()))
            new_start_date = st.text_input("توقيت بدء العرض الفعلي:", value=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            new_expiry_date = st.text_input("توقيت انتهاء العرض التلقائي:", value="2026-12-31 23:59:59")
            
        st.markdown("#### 🛒 شروط ومجموعات حقول العرض التفاعلية")
        
        # استرجاع المفاتيح من القيم العربية المحددة
        selected_type_key = [k for k, v in OFFER_TYPES_MAP.items() if v == new_offer_type_ar][0]
        selected_channel_key = [k for k, v in CHANNELS_MAP.items() if v == new_channel_ar][0]
        
        # التحكم الشرطي الديناميكي الكامل لواجهة نظام التشغيل المباشر
        if selected_type_key == "buy_x_get_y":
            col_bx, col_by = st.columns(2)
            with col_bx:
                new_buy_type = st.selectbox("نوع شرط الشراء X:", ["product", "category"])
                new_buy_qty = st.number_input("الكمية المطلوب شراؤها من العميل (X):", min_value=1, value=1)
                new_buy_products = st.text_input("معرفات الـ IDs لمنتجات الشراء (مفصولة بفاصلة ,):")
            with col_by:
                new_get_type = st.selectbox("نوع صنف الهدية الممنوحة Y:", ["product", "category"])
                new_get_qty = st.number_input("كمية القطع الممنوحة مجاناً (Y):", min_value=1, value=1)
                new_get_products = st.text_input("معرفات الـ IDs لمنتجات الهدية الممنوحة (مفصولة بفاصلة ,):")
            
            new_discount_type_ar = st.selectbox("نوع التخفيض المطبق على Y:", ["منتج مجاني", "خصم بنسبة"])
            
            # إظهار خانة نسبة الخصم في حال اختيار خصم بنسبة لنوع العرض المذكور
            if new_discount_type_ar == "خصم بنسبة":
                new_discount_amount = st.number_input("نسبة الخصم المئوية المطبقة على الصنف الممنوح (%):", min_value=1.0, max_value=100.0, value=10.0)
                new_discount_type = "percentage"
            else:
                new_discount_amount = 0.0
                new_discount_type = "free-product"
        else:
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                new_discount_amount = st.number_input("قيمة أو نسبة التخفيض المالي المباشر للعرض:", min_value=0.5, value=10.0)
                new_buy_products = st.text_input("معرفات الـ IDs للمنتجات الخاضعة للتخفيض الفوري (مفصولة بفاصلة ,):")
            with col_p2:
                st.caption("ملاحظة: هذا العرض مالي مباشر وموحد ويطبق على السلة أو الأصناف بشكل مباشر وفقاً لهيكلية سلة المحددة.")
            new_buy_type = "product"
            new_buy_qty = 1
            new_get_type = "product"
            new_get_qty = 1
            new_get_products = ""
            new_discount_type = "percentage" if selected_type_key == "percentage" else "fixed_amount"
        
        if st.button("🚀 إنشاء العرض ونشره بالمتجر الآن", type="primary", use_container_width=True, key="save_new_offer_green"):
            try:
                b_ids = [int(i.strip()) for i in new_buy_products.split(",") if i.strip().isdigit()]
                payload = {
                    "name": new_offer_name, "offer_type": selected_type_key, "message": new_message,
                    "applied_channel": selected_channel_key, "applied_to": new_applied_to,
                    "start_date": new_start_date, "expiry_date": new_expiry_date, "status": "active",
                    "applied_with_coupon": new_with_coupon == "نعم",
                    "buy": {"type": new_buy_type, "quantity": int(new_buy_qty), "products": b_ids},
                    "get": {"type": new_get_type, "quantity": int(new_get_qty), "discount_type": new_discount_type}
                }
                if selected_type_key == "buy_x_get_y":
                    g_ids = [int(i.strip()) for i in new_get_products.split(",") if i.strip().isdigit()]
                    payload["get"]["products"] = g_ids
                if new_discount_amount > 0:
                    payload["get"]["discount_amount"] = float(new_discount_amount)
                    
                if safe_api_request("POST", SALLA_API_URL, headers, json=payload):
                    st.success("✅ تم تدوين وإنشاء العرض الترويجي المتكامل بنجاح!")
                    st.rerun()
            except Exception as e:
                st.error(f"خطأ أثناء إنشاء العرض: {str(e)}")

    st.divider()

    # --- التصفية والبحث المتقدم عن العروض ---
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
        o_type_raw = offer.get('offer_type', '')
        o_channel_raw = offer.get('applied_channel', 'browser_and_application')
        exp_date = safe_parse_date(offer.get('expiry_date'))
        
        if search_offer and (search_offer.lower() not in offer_name.lower() and search_offer not in str(offer_id)): continue
        if status_filter == "نشط فقط" and status != "active": continue
        if status_filter == "غير نشط فقط" and status == "active": continue
        
        if filter_date_str.strip():
            try:
                target_date = datetime.strptime(filter_date_str.strip(), "%Y-%m-%d").date()
                if not exp_date or exp_date.date() != target_date: continue
            except ValueError:
                st.warning("⚠️ صيغة تاريخ التصفية المطابق الصحيح هي YYYY-MM-DD")
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
                st.markdown(f"⚙️ **نوع العرض فنيًا:** `{OFFER_TYPES_MAP.get(o_type_raw, o_type_raw)}`")
                st.markdown(f"📺 **قناة وبث العرض الفعالة:** `{CHANNELS_MAP.get(o_channel_raw, o_channel_raw)}`")
                st.markdown(f"📅 **توقيت بدء النشر المعتمد:** `{offer.get('start_date', 'غير محدد')}`")
            with cy:
                st.markdown(f"📅 **توقيت انتهاء الصلاحية:** `{offer.get('expiry_date', 'بدون تاريخ (مستمر)')}`")
                st.markdown(f"**🔖 متوافق ومربوط مع كوبونات؟** `{'نعم بالتأكيد' if offer.get('applied_with_coupon') else 'لا (تلقائي المفعول)'}`")
                st.markdown(f"**📢 نص الرسالة الترويجية للزبائن:** *{offer.get('message', 'لا توجد رسالة مرفقة')}*")
                
            st.markdown("<hr style='margin: 15px 0; border-top: 1px dashed #e2e8f0;'>", unsafe_allow_html=True)
            
            col_x, col_y = st.columns(2)
            with col_x:
                st.markdown("<b style='color:#0f1c2e;'>🛒 مجموعة الشراء (X) [تشمل الأسماء والمعرفات ورقم الصنف SKU]:</b>", unsafe_allow_html=True)
                st.text(parse_products_cleanly(offer.get('buy', {})))
                st.caption(f"الكمية المطلوبة: {offer.get('buy', {}).get('quantity', 1)} قطعة")
            with col_y:
                st.markdown("<b style='color:#0f1c2e;'>🎁 مجموعة المنح والهدية (Y) [تشمل الأسماء والمعرفات ورقم الصنف SKU]:</b>", unsafe_allow_html=True)
                st.text(parse_products_cleanly(offer.get('get', {})))
                st.caption(f"كمية المنح/الخصم: {offer.get('get', {}).get('quantity', 1)} قطعة")
                if offer.get('get', {}).get('discount_amount'):
                    st.markdown(f"🔥 **قيمة/نسبة الخصم الممنوحة الحالية:** `{offer.get('get', {}).get('discount_amount')}`")

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

            # --- حاوية تعديل مشروطة وديناميكية لكل عرض منفرد لمنع الأخطاء البصرية والبرمجية ---
            with st.expander("✏️ تعديل ومراجعة كافة حقول هذا العرض الترويجي", expanded=False):
                st.markdown("##### ✏️ تعديل البيانات والخيارات الأساسية")
                ed_name = st.text_input("تحديث مسمى العرض الحصري:", value=offer_name, key=f"ed_n_{offer_id}_{idx}")
                ed_msg = st.text_input("تحديث الرسالة المعروضة في السلة للزبائن:", value=offer.get('message', ''), key=f"ed_m_{offer_id}_{idx}")
                
                ec1, ec2 = st.columns(2)
                with ec1:
                    current_type_idx = list(OFFER_TYPES_MAP.keys()).index(o_type_raw) if o_type_raw in OFFER_TYPES_MAP else 0
                    ed_type_ar = st.selectbox("تعديل هيكل ونوع العرض المعتمد:", list(OFFER_TYPES_MAP.values()), index=current_type_idx, key=f"ed_t_ar_{offer_id}_{idx}")
                with ec2:
                    current_chan_idx = list(CHANNELS_MAP.keys()).index(o_channel_raw) if o_channel_raw in CHANNELS_MAP else 0
                    ed_chan_ar = st.selectbox("تعديل منصة بث ونشر العرض الحالي:", list(CHANNELS_MAP.values()), index=current_chan_idx, key=f"ed_ch_ar_{offer_id}_{idx}")

                selected_ed_type_key = [k for k, v in OFFER_TYPES_MAP.items() if v == ed_type_ar][0]
                selected_ed_chan_key = [k for k, v in CHANNELS_MAP.items() if v == ed_chan_ar][0]

                st.markdown("##### 🛒 تعديل مجموعات الصنف والكميات بشكل ديناميكي")
                buy_obj = offer.get('buy', {})
                get_obj = offer.get('get', {})
                buy_p_ids = ",".join([str(p.get('id', p)) if isinstance(p, dict) else str(p) for p in buy_obj.get('products', [])])
                get_p_ids = ",".join([str(p.get('id', p)) if isinstance(p, dict) else str(p) for p in get_obj.get('products', [])])
                
                # تطبيق الظهور الديناميكي المشروط في حقول التعديل بالكامل
                if selected_ed_type_key == "buy_x_get_y":
                    eq1, eq2 = st.columns(2)
                    with eq1:
                        ed_buy_type = st.selectbox("تعديل نوع شراء X:", ["product", "category"], index=0 if buy_obj.get('type') == 'product' else 1, key=f"ed_bt_{offer_id}_{idx}")
                        ed_buy_qty = st.number_input("تعديل كمية الشراء (X):", min_value=1, value=int(buy_obj.get('quantity', 1)), key=f"ed_bq_{offer_id}_{idx}")
                        ed_buy_products = st.text_input("تعديل الـ IDs لمنتجات الشراء المشمولة:", value=buy_p_ids, key=f"ed_bp_ids_{offer_id}_{idx}")
                    with eq2:
                        ed_get_type = st.selectbox("تعديل نوع هدية Y:", ["product", "category"], index=0 if get_obj.get('type') == 'product' else 1, key=f"ed_gt_{offer_id}_{idx}")
                        ed_get_qty = st.number_input("تعديل كمية الهدية (Y):", min_value=1, value=int(get_obj.get('quantity', 1)), key=f"ed_gq_{offer_id}_{idx}")
                        ed_get_products = st.text_input("تعديل الـ IDs لمنتجات الهدية المشمولة:", value=get_p_ids, key=f"ed_gp_ids_{offer_id}_{idx}")
                    
                    current_disc_type_raw = "خصم بنسبة" if get_obj.get('discount_type') == 'percentage' else "منتج مجاني"
                    ed_discount_type_ar = st.selectbox("تعديل نوع تخفيض Y:", ["منتج مجاني", "خصم بنسبة"], index=1 if current_disc_type_raw == "خصم بنسبة" else 0, key=f"ed_dt_ar_{offer_id}_{idx}")
                    
                    if ed_discount_type_ar == "خصم بنسبة":
                        ed_disc_amt = st.number_input("تعديل نسبة الخصم المئوية المطبقة على Y (%):", min_value=1.0, max_value=100.0, value=float(get_obj.get('discount_amount', 10.0)), key=f"ed_da_{offer_id}_{idx}")
                        ed_disc_type = "percentage"
                    else:
                        ed_disc_amt = 0.0
                        ed_disc_type = "free-product"
                else:
                    eq1, eq2 = st.columns(2)
                    with eq1:
                        ed_disc_amt = st.number_input("تعديل قيمة أو نسبة الخصم المالي المباشر:", min_value=0.5, value=float(get_obj.get('discount_amount', 10.0)), key=f"ed_da_direct_{offer_id}_{idx}")
                        ed_buy_products = st.text_input("تعديل الـ IDs للمنتجات المشمولة بالتخفيض الفوري:", value=buy_p_ids, key=f"ed_bp_direct_{offer_id}_{idx}")
                    with eq2:
                        st.caption("ملاحظة: هذا النوع من العروض الترويجية يطبق بشكل فوري ومباشر.")
                    ed_buy_type = "product"
                    ed_buy_qty = 1
                    ed_get_type = "product"
                    ed_get_qty = 1
                    ed_get_products = ""
                    ed_disc_type = "percentage" if selected_ed_type_key == "percentage" else "fixed_amount"

                et1, et2 = st.columns(2)
                with et1: ed_start = st.text_input("تحديث تاريخ بدء العرض:", value=offer.get('start_date', ''), key=f"ed_s_dt_{offer_id}_{idx}")
                with et2: ed_end = st.text_input("تحديث تاريخ انتهاء الصلاحية:", value=offer.get('expiry_date', ''), key=f"ed_e_dt_{offer_id}_{idx}")
                
                if st.button("💾 اعتماد وحفظ تفاصيل هذا العرض المحدث حالياً", key=f"sv_of_{offer_id}_{idx}", type="primary", use_container_width=True):
                    try:
                        b_p_list = [int(i.strip()) for i in ed_buy_products.split(",") if i.strip().isdigit()]
                        update_payload = {
                            "name": ed_name, "message": ed_msg, "start_date": ed_start, "expiry_date": ed_end,
                            "status": status, "offer_type": selected_ed_type_key, "applied_channel": selected_ed_chan_key,
                            "applied_with_coupon": offer.get('applied_with_coupon', False),
                            "buy": {"type": ed_buy_type, "quantity": int(ed_buy_qty), "products": b_p_list},
                            "get": {"type": ed_get_type, "quantity": int(ed_get_qty), "discount_type": ed_disc_type}
                        }
                        if selected_ed_type_key == "buy_x_get_y":
                            g_p_list = [int(i.strip()) for i in ed_get_products.split(",") if i.strip().isdigit()]
                            update_payload["get"]["products"] = g_p_list
                        if ed_disc_amt > 0:
                            update_payload["get"]["discount_amount"] = float(ed_disc_amt)
                            
                        if safe_api_request("PUT", f"{SALLA_API_URL}/{offer_id}", headers, json=update_payload):
                            st.success("✅ تم تحديث ونشر بيانات العرض بنجاح!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"خطأ أثناء حفظ التحديثات: {str(e)}")
            
            st.markdown("</div>", unsafe_allow_html=True)
