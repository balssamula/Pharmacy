import streamlit as st
import pandas as pd
import json
import re
from io import BytesIO
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

def extract_single_sku(combined_sku):
    """استخراج SKU الفردي من SKU المجمع"""
    if pd.isna(combined_sku) or combined_sku == "":
        return ""
    
    sku_str = str(combined_sku).strip()
    
    if '*' in sku_str:
        sku_str = sku_str.split('*')[0].strip()
    if '-' in sku_str:
        sku_str = sku_str.split('-')[0].strip()
    if '+' in sku_str:
        sku_str = sku_str.split('+')[0].strip()
    
    # إزالة أي أحرف غير رقمية
    if sku_str.replace('.', '').isdigit():
        sku_str = re.sub(r'[^0-9]', '', sku_str)
    
    return sku_str

def safe_float_convert(value):
    """تحويل آمن إلى float"""
    if pd.isna(value):
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0

def show():
    st.markdown("""
    <div class="hero">
        <h1>📦 تفصيلي المنتجات وتحليلات متقدمة</h1>
        <p>تحليل تفاصيل المنتجات من ملف الطلبات مع إحصائيات متقدمة ورسوم بيانية تفاعلية</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.info("""
    **📌 تعليمات استخدام هذه الصفحة:**
    1. قم برفع ملف `orders.xlsx` (يحتوي على أعمدة: رقم الطلب، skus_json، الخصم، تكلفة الشحن، طريقة الدفع، الضريبة، تاريخ الطلب)
    2. قم برفع ملف `products.xlsx` (يحتوي على عمودي 'SKU' و 'ProductName')
    3. سيتم معالجة البيانات واستخراج تفاصيل المنتجات
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        orders_file = st.file_uploader("📊 رفع ملف الطلبات (orders.xlsx)", type=["xlsx"], key="orders_file")
        if orders_file:
            st.success("✅ تم رفع ملف الطلبات")
    
    with col2:
        products_file = st.file_uploader("📦 رفع ملف المنتجات (products.xlsx)", type=["xlsx"], key="products_file")
        if products_file:
            st.success("✅ تم رفع ملف المنتجات")
    
    if orders_file and products_file:
        if st.button("🔄 معالجة البيانات", use_container_width=True, type="primary"):
            with st.spinner("جاري معالجة البيانات..."):
                try:
                    # قراءة الملفات
                    df_orders = pd.read_excel(orders_file)
                    df_products = pd.read_excel(products_file)
                    
                    # تنظيف أسماء الأعمدة
                    df_orders.columns = df_orders.columns.str.strip()
                    df_products.columns = df_products.columns.str.strip()
                    
                    st.info(f"📊 تم قراءة {len(df_orders)} طلب و {len(df_products)} منتج")
                    
                    # التحقق من وجود الأعمدة المطلوبة
                    required_order_cols = ['رقم الطلب', 'skus_json']
                    required_product_cols = ['SKU', 'ProductName']
                    
                    missing_order = [col for col in required_order_cols if col not in df_orders.columns]
                    missing_product = [col for col in required_product_cols if col not in df_products.columns]
                    
                    if missing_order:
                        st.error(f"❌ الأعمدة المفقودة في ملف الطلبات: {missing_order}")
                        st.stop()
                    if missing_product:
                        st.error(f"❌ الأعمدة المفقودة في ملف المنتجات: {missing_product}")
                        st.stop()
                    
                    # إنشاء قاموس المنتجات
                    product_map = {}
                    for _, row in df_products.iterrows():
                        sku = str(row['SKU']).strip()
                        if sku.endswith('.0'):
                            sku = sku[:-2]
                        name = str(row['ProductName']).strip()
                        product_map[sku] = name
                    
                    # إنشاء قاموس لبيانات الطلبات مع تحويل الأرقام
                    order_info_map = {}
                    for _, row in df_orders.iterrows():
                        order_id = row['رقم الطلب']
                        order_info_map[order_id] = {
                            'الخصم': safe_float_convert(row.get('الخصم', 0)),
                            'تكلفة الشحن': safe_float_convert(row.get('تكلفة الشحن', 0)),
                            'طريقة الدفع': str(row.get('طريقة الدفع', 'غير محدد')),
                            'الضريبة': safe_float_convert(row.get('الضريبة', 0)),
                            'تاريخ الطلب': row.get('تاريخ الطلب', ''),
                            'قيمة خصم الكوبون': safe_float_convert(row.get('قيمة خصم الكوبون', 0)),
                            'قيمة خصم العروض الخاصة': safe_float_convert(row.get('قيمة خصم العروض الخاصة', 0))
                        }
                    
                    final_rows = []
                    processed_orders = 0
                    failed_orders = 0
                    
                    for _, row in df_orders.iterrows():
                        order_id = row['رقم الطلب']
                        order_info = order_info_map.get(order_id, {})
                        
                        try:
                            skus_json = row['skus_json']
                            if isinstance(skus_json, str):
                                json_data = json.loads(skus_json)
                            else:
                                json_data = skus_json
                            
                            for item in json_data:
                                combined_sku = ""
                                quantity = 0
                                unit_price = 0
                                product_name = ""
                                
                                # البحث عن SKU
                                for pos in range(len(item)):
                                    val = str(item[pos]) if item[pos] is not None else ""
                                    if re.match(r'^[\d\*\-]+$', val) and len(val) > 2:
                                        combined_sku = val
                                        break
                                
                                if not combined_sku and len(item) > 2:
                                    combined_sku = str(item[2]) if item[2] else ""
                                
                                # البحث عن الكمية
                                for pos in range(len(item)):
                                    val = item[pos]
                                    if isinstance(val, (int, float)) and val > 0 and val < 10000:
                                        if quantity == 0:
                                            quantity = float(val)
                                        elif unit_price == 0 and val != quantity:
                                            unit_price = float(val)
                                
                                if quantity == 0 and len(item) > 3 and isinstance(item[3], (int, float)):
                                    quantity = float(item[3])
                                
                                # البحث عن اسم المنتج
                                if len(item) > 0 and isinstance(item[0], str) and not re.match(r'^[\d\*\-]+$', item[0]):
                                    product_name = item[0]
                                
                                single_sku = extract_single_sku(combined_sku)
                                
                                if single_sku and single_sku in product_map:
                                    product_name = product_map[single_sku]
                                
                                total = quantity * unit_price if quantity and unit_price else 0
                                
                                if combined_sku:
                                    final_rows.append({
                                        'رقم الطلب': order_id,
                                        'المنتج': product_name if product_name else combined_sku,
                                        'الكمية': quantity,
                                        'SKU فردي': single_sku,
                                        'SKU مجمع (للمراجعة)': combined_sku,
                                        'سعر الوحدة': unit_price,
                                        'الإجمالي': total,
                                        'النوع': 'أساسي',
                                        'الخصم': order_info.get('الخصم', 0),
                                        'تكلفة الشحن': order_info.get('تكلفة الشحن', 0),
                                        'طريقة الدفع': order_info.get('طريقة الدفع', 'غير محدد'),
                                        'الضريبة': order_info.get('الضريبة', 0),
                                        'تاريخ الطلب': order_info.get('تاريخ الطلب', ''),
                                        'قيمة خصم الكوبون': order_info.get('قيمة خصم الكوبون', 0),
                                        'قيمة خصم العروض الخاصة': order_info.get('قيمة خصم العروض الخاصة', 0)
                                    })
                                
                                # معالجة المنتجات الفرعية
                                if len(item) > 5 and isinstance(item[5], list):
                                    sub_items_list = item[5]
                                    
                                    for sub_idx, sub in enumerate(sub_items_list):
                                        if not isinstance(sub, list) or len(sub) < 3:
                                            continue
                                        
                                        sub_combined_sku = str(sub[2]) if len(sub) > 2 else ""
                                        sub_quantity = sub[1] if len(sub) > 1 and isinstance(sub[1], (int, float)) else 0
                                        sub_unit_price = sub[3] if len(sub) > 3 and isinstance(sub[3], (int, float)) else 0
                                        sub_total = sub[4] if len(sub) > 4 and isinstance(sub[4], (int, float)) else (sub_quantity * sub_unit_price)
                                        
                                        sub_name = sub[0] if len(sub) > 0 and isinstance(sub[0], str) else ""
                                        sub_single_sku = extract_single_sku(sub_combined_sku)
                                        
                                        if sub_single_sku and sub_single_sku in product_map:
                                            sub_name = product_map[sub_single_sku]
                                        
                                        if sub_combined_sku and sub_quantity > 0:
                                            final_rows.append({
                                                'رقم الطلب': order_id,
                                                'المنتج': sub_name if sub_name else sub_combined_sku,
                                                'الكمية': sub_quantity,
                                                'SKU فردي': sub_single_sku,
                                                'SKU مجمع (للمراجعة)': sub_combined_sku,
                                                'سعر الوحدة': sub_unit_price,
                                                'الإجمالي': sub_total,
                                                'النوع': 'فرعي',
                                                'الخصم': order_info.get('الخصم', 0),
                                                'تكلفة الشحن': order_info.get('تكلفة الشحن', 0),
                                                'طريقة الدفع': order_info.get('طريقة الدفع', 'غير محدد'),
                                                'الضريبة': order_info.get('الضريبة', 0),
                                                'تاريخ الطلب': order_info.get('تاريخ الطلب', ''),
                                                'قيمة خصم الكوبون': order_info.get('قيمة خصم الكوبون', 0),
                                                'قيمة خصم العروض الخاصة': order_info.get('قيمة خصم العروض الخاصة', 0)
                                            })
                            
                            processed_orders += 1
                            
                        except Exception as e:
                            failed_orders += 1
                            continue
                    
                    # إنشاء DataFrame النهائي
                    result_df = pd.DataFrame(final_rows)
                    
                    # تنظيف البيانات وتحويل الأعمدة الرقمية
                    numeric_cols = ['الكمية', 'سعر الوحدة', 'الإجمالي', 'الخصم', 'تكلفة الشحن', 'الضريبة', 'قيمة خصم الكوبون', 'قيمة خصم العروض الخاصة']
                    for col in numeric_cols:
                        if col in result_df.columns:
                            result_df[col] = result_df[col].apply(safe_float_convert)
                    
                    result_df = result_df[result_df['المنتج'].notna()]
                    result_df = result_df[result_df['المنتج'] != ""]
                    result_df = result_df[result_df['الكمية'] > 0]
                    
                    # 💡 الإصلاح الجذري: تجميع الكميات والإجماليات للأصناف المتطابقة بدلاً من حذفها وتضييع الكميات الفرعية
                    group_cols = [
                        'رقم الطلب', 'المنتج', 'SKU فردي', 'SKU مجمع (للمراجعة)', 'النوع', 
                        'سعر الوحدة', 'الخصم', 'تكلفة الشحن', 'طريقة الدفع', 'الضريبة', 
                        'تاريخ الطلب', 'قيمة خصم الكوبون', 'قيمة خصم العروض الخاصة'
                    ]
                    # تأمين إضافي لضمان وجود الأعمدة في الفريم قبل التجميع
                    group_cols = [col for col in group_cols if col in result_df.columns]
                    
                    result_df = result_df.groupby(group_cols, as_index=False).agg({
                        'الكمية': 'sum',
                        'الإجمالي': 'sum'
                    })
                    
                    if 'تاريخ الطلب' in result_df.columns:
                        result_df['تاريخ الطلب'] = pd.to_datetime(result_df['تاريخ الطلب'], errors='coerce')
                    
                    st.success(f"✅ تمت المعالجة بنجاح!")
                    st.info(f"📊 الإحصائيات: {processed_orders} طلب تمت معالجتها، {failed_orders} طلب فشل")
                    st.info(f"📦 عدد الصفوف المنتجة: {len(result_df)} (أساسي: {len(result_df[result_df['النوع'] == 'أساسي'])}, فرعي: {len(result_df[result_df['النوع'] == 'فرعي'])})")
                    
                    # ========== التبويبات المتقدمة ==========
                    tab1, tab2, tab3, tab4, tab5 = st.tabs([
                        "📋 جدول البيانات التفصيلي",
                        "📊 إحصائيات وتحليلات",
                        "📈 رسوم بيانية تفاعلية",
                        "💰 تحليل المبيعات",
                        "🏷️ تحليل طرق الدفع"
                    ])
                    
                    with tab1:
                        st.subheader("📋 جدول البيانات التفصيلي")
                        st.dataframe(result_df, use_container_width=True)
                        
                        output = BytesIO()
                        result_df.to_excel(output, index=False)
                        output.seek(0)
                        st.download_button(
                            "📥 تحميل ملف النتائج (Excel)",
                            data=output,
                            file_name=f"product_details_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                        )
                    
                    with tab2:
                        st.subheader("📊 إحصائيات وتحليلات")
                        
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("عدد الطلبات الفريدة", result_df['رقم الطلب'].nunique())
                        with col2:
                            st.metric("عدد المنتجات الفريدة", result_df['SKU فردي'].nunique())
                        with col3:
                            total_qty = result_df['الكمية'].sum()
                            st.metric("إجمالي الكمية", f"{total_qty:,.2f}")
                        with col4:
                            total_amount = result_df['الإجمالي'].sum()
                            st.metric("إجمالي المبيعات", f"{total_amount:,.2f} ₴")
                        
                        st.markdown("---")
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            total_discount = result_df['الخصم'].sum() + result_df['قيمة خصم الكوبون'].sum() + result_df['قيمة خصم العروض الخاصة'].sum()
                            st.metric("إجمالي الخصومات", f"{total_discount:,.2f} ₴")
                        with col2:
                            avg_delivery = result_df['تكلفة الشحن'].mean()
                            st.metric("متوسط تكلفة الشحن", f"{avg_delivery:,.2f} ₴")
                        with col3:
                            avg_tax = result_df['الضريبة'].mean()
                            st.metric("متوسط الضريبة", f"{avg_tax:,.2f} ₴")
                        
                        st.markdown("---")
                        
                        st.subheader("🏆 أكثر 10 منتجات مبيعاً")
                        top_products = result_df.groupby(['SKU فردي', 'المنتج']).agg({
                            'الكمية': 'sum',
                            'الإجمالي': 'sum'
                        }).reset_index().sort_values('الكمية', ascending=False).head(10)
                        st.dataframe(top_products, use_container_width=True)
                        
                        st.subheader("📦 توزيع المنتجات حسب النوع")
                        type_stats = result_df.groupby('النوع').agg({
                            'الكمية': 'sum',
                            'الإجمالي': 'sum'
                        }).reset_index()
                        st.dataframe(type_stats, use_container_width=True)
                    
                    with tab3:
                        st.subheader("📈 الرسوم البيانية التفاعلية")
                        
                        if 'تاريخ الطلب' in result_df.columns and not result_df['تاريخ الطلب'].isna().all():
                            st.markdown("### 📅 المبيعات اليومية")
                            daily_sales = result_df.groupby(result_df['تاريخ الطلب'].dt.date).agg({
                                'الإجمالي': 'sum'
                            }).reset_index()
                            daily_sales = daily_sales.sort_values('تاريخ الطلب')
                            
                            fig1 = px.line(daily_sales, x='تاريخ الطلب', y='الإجمالي', 
                                          title='المبيعات اليومية',
                                          labels={'الإجمالي': 'المبيعات (₴)', 'تاريخ الطلب': 'التاريخ'})
                            st.plotly_chart(fig1, use_container_width=True)
                        
                        st.markdown("### 🏷️ أفضل 10 منتجات من حيث المبيعات")
                        top_10 = result_df.groupby('المنتج')['الإجمالي'].sum().sort_values(ascending=False).head(10).reset_index()
                        if not top_10.empty:
                            fig2 = px.bar(top_10, x='الإجمالي', y='المنتج', orientation='h',
                                         title='أفضل 10 منتجات من حيث المبيعات',
                                         labels={'الإجمالي': 'المبيعات (₴)', 'المنتج': 'المنتج'})
                            st.plotly_chart(fig2, use_container_width=True)
                        
                        st.markdown("### 📊 توزيع المبيعات (أساسي vs فرعي)")
                        type_sales = result_df.groupby('النوع')['الإجمالي'].sum().reset_index()
                        if not type_sales.empty:
                            fig3 = px.pie(type_sales, values='الإجمالي', names='النوع', 
                                         title='نسبة المبيعات حسب النوع',
                                         hole=0.4)
                            st.plotly_chart(fig3, use_container_width=True)
                    
                    with tab4:
                        st.subheader("💰 تحليل المبيعات")
                        
                        total_revenue = result_df['الإجمالي'].sum()
                        total_quantity = result_df['الكمية'].sum()
                        avg_unit_price = total_revenue / total_quantity if total_quantity > 0 else 0
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("إجمالي الإيرادات", f"{total_revenue:,.2f} ₴")
                        with col2:
                            st.metric("إجمالي الكمية", f"{total_quantity:,.0f}")
                        with col3:
                            st.metric("متوسط سعر الوحدة", f"{avg_unit_price:,.2f} ₴")
                        
                        st.markdown("---")
                        
                        st.markdown("### 📉 تحليل الخصومات")
                        discount_df = pd.DataFrame({
                            'نوع الخصم': ['خصم الطلب', 'خصم الكوبون', 'خصم العروض الخاصة'],
                            'القيمة': [
                                result_df['الخصم'].sum(),
                                result_df['قيمة خصم الكوبون'].sum(),
                                result_df['قيمة خصم العروض الخاصة'].sum()
                            ]
                        })
                        fig4 = px.bar(discount_df, x='نوع الخصم', y='القيمة',
                                     title='قيمة الخصومات حسب النوع',
                                     labels={'القيمة': 'القيمة (₴)', 'نوع الخصم': 'نوع الخصم'})
                        st.plotly_chart(fig4, use_container_width=True)
                        
                        st.markdown("### 🧾 تحليل الضرائب")
                        total_tax = result_df['الضريبة'].sum()
                        tax_percentage = (total_tax / total_revenue) * 100 if total_revenue > 0 else 0
                        st.metric("إجمالي الضرائب", f"{total_tax:,.2f} ₴", delta=f"{tax_percentage:.2f}% من الإيرادات")
                        
                        st.markdown("### 🚚 تحليل الشحن")
                        free_shipping = len(result_df[result_df['تكلفة الشحن'] == 0]['رقم الطلب'].unique())
                        total_orders = result_df['رقم الطلب'].nunique()
                        st.metric("طلبات بشحن مجاني", f"{free_shipping} من {total_orders}", delta=f"{(free_shipping/total_orders)*100:.1f}%")
                    
                    with tab5:
                        st.subheader("🏷️ تحليل طرق الدفع")
                        
                        payment_stats = result_df.groupby('طريقة الدفع').agg({
                            'الإجمالي': 'sum',
                            'رقم الطلب': 'nunique'
                        }).reset_index()
                        payment_stats.columns = ['طريقة الدفع', 'إجمالي المبيعات', 'عدد الطلبات']
                        payment_stats = payment_stats.sort_values('إجمالي المبيعات', ascending=False)
                        
                        st.dataframe(payment_stats, use_container_width=True)
                        
                        fig5 = px.pie(payment_stats, values='إجمالي المبيعات', names='طريقة الدفع',
                                     title='نسبة المبيعات حسب طريقة الدفع',
                                     hole=0.3)
                        st.plotly_chart(fig5, use_container_width=True)
                        
                        if 'تاريخ الطلب' in result_df.columns and not result_df['تاريخ الطلب'].isna().all():
                            st.markdown("### 📅 تطور طرق الدفع عبر الزمن")
                            payment_over_time = result_df.groupby([result_df['تاريخ الطلب'].dt.date, 'طريقة الدفع']).agg({
                                'الإجمالي': 'sum'
                            }).reset_index()
                            payment_over_time = payment_over_time.sort_values('تاريخ الطلب')
                            
                            fig6 = px.line(payment_over_time, x='تاريخ الطلب', y='الإجمالي', color='طريقة الدفع',
                                          title='تطور المبيعات حسب طريقة الدفع',
                                          labels={'الإجمالي': 'المبيعات (₴)', 'تاريخ الطلب': 'التاريخ'})
                            st.plotly_chart(fig6, use_container_width=True)
                
                except Exception as e:
                    st.error(f"❌ حدث خطأ أثناء المعالجة: {str(e)}")
                    st.exception(e)
    
    else:
        st.info("📂 الرجاء رفع ملفي الطلبات والمنتجات لبدء المعالجة")
