import streamlit as st
import pandas as pd
import io
import time
from datetime import datetime, timedelta
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from utils import get_headers, safe_api_request, SALLA_API_URL

def get_orders_list(from_date, to_date, headers):
    """سحب قائمة الطلبات المبدئية من سلة"""
    orders = []
    page = 1
    total_pages = 1
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    while page <= total_pages:
        status_text.info(f"📥 جاري حصر الطلبات (صفحة {page} من {total_pages if page > 1 else '...'})...")
        url = f"https://api.salla.dev/admin/v2/orders?from_date={from_date}&to_date={to_date}&per_page=50&page={page}"
        res = safe_api_request("GET", url, headers)
        
        if not res or not res.get("data"): break
        if page == 1: total_pages = res.get("pagination", {}).get("totalPages", 1)
        
        orders.extend(res["data"])
        progress_bar.progress(min(page / total_pages, 1.0))
        page += 1
        
    progress_bar.empty()
    status_text.empty()
    return orders

def get_detailed_orders(orders_summary, headers):
    """سحب التفاصيل الدقيقة لكل طلب لاستخراج الـ SKUs والضرائب الدقيقة"""
    detailed_orders = []
    status_text = st.empty()
    progress_bar = st.progress(0)
    total = len(orders_summary)
    
    for i, o_sum in enumerate(orders_summary):
        status_text.info(f"🔍 جاري سحب التفاصيل الدقيقة للطلب {o_sum.get('reference_id')} ({i+1} من {total})...")
        order_id = o_sum.get("id")
        
        res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/orders/{order_id}", headers)
        if res and res.get("data"):
            detailed_orders.append(res["data"])
            
        progress_bar.progress((i + 1) / total)
        time.sleep(0.15) # حماية من حظر سلة
        
    status_text.success(f"✅ تم سحب التفاصيل الدقيقة لـ {total} طلب بنجاح!")
    progress_bar.empty()
    return detailed_orders

def generate_short_export(orders):
    """بناء التصدير المختصر الاحترافي"""
    rows = []
    for order in orders:
        discounts = order.get('amounts', {}).get('discounts', [])
        
        # توزيع الخصومات (كوبون vs عرض خاص)
        coupon_disc = sum(float(d.get('discount', 0)) for d in discounts if d.get('type') != 'special_offer' and 'عرض' not in str(d.get('title', '')))
        special_disc = sum(float(d.get('discount', 0)) for d in discounts if d.get('type') == 'special_offer' or 'عرض' in str(d.get('title', '')))
        total_discount = coupon_disc + special_disc
        
        subtotal = float(order.get('amounts', {}).get('sub_total', {}).get('amount', 0))
        shipping = float(order.get('amounts', {}).get('shipping_cost', {}).get('amount', 0))
        tax = float(order.get('amounts', {}).get('tax', {}).get('amount', {}).get('amount', 0))
        refund = float(order.get('payment_actions', {}).get('refund_action', {}).get('refund_amount', {}).get('amount', 0))
        
        total_after_disc = subtotal - total_discount
        net_sales = total_after_disc # صافي المبيعات بدون الشحن والضريبة
        
        shipments = order.get('shipments', [])
        shipping_company = shipments[0].get('courier_name', '') if shipments else order.get('shipping', {}).get('company', '')
        
        branch = ""
        if shipments and shipments[0].get('ship_from', {}).get('name'):
            branch = shipments[0].get('ship_from', {}).get('name')
        elif order.get('shipping', {}).get('shipper', {}).get('company_name'):
            branch = order.get('shipping', {}).get('shipper', {}).get('company_name')

        rows.append({
            "الفرع": branch,
            "تاريخ الطلب": str(order.get('date', {}).get('date', ''))[:10],
            "رقم الطلب": order.get('reference_id', ''),
            "حالة الطلب": order.get('status', {}).get('name', ''),
            "اسم العميل": f"{order.get('customer', {}).get('first_name', '')} {order.get('customer', {}).get('last_name', '')}".strip(),
            "رقم الجوال": f"{order.get('customer', {}).get('mobile_code', '')}{order.get('customer', {}).get('mobile', '')}",
            "بريد العميل": order.get('customer', {}).get('email', ''),
            "المدينة": order.get('customer', {}).get('city', ''),
            "شركة الشحن": shipping_company,
            "طريقة الدفع": order.get('payment_method', ''),
            "utm_source": order.get('source_details', {}).get('utm_source', '') or order.get('campaign', {}).get('source', ''),
            "مجموع السلة": subtotal,
            "الخصم الإجمالي": total_discount,
            "قيمة خصم الكوبون": coupon_disc,
            "قيمة خصم العروض الخاصة": special_disc,
            "الاجمالي بعد الخصم": total_after_disc,
            "تكلفة الشحن": shipping,
            "الضريبة": tax,
            "صافي المبيعات": net_sales,
            "المبلغ المسترجع": refund
        })
        
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "التصدير المختصر"
    ws.sheet_view.rightToLeft = True
    
    headers = list(df.columns)
    ws.append(headers)
    for row in df.itertuples(index=False, name=None):
        ws.append(row)
        
    # تنسيق رأس الجدول
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(color="00EBCF", bold=True, size=12)
    center_align = Alignment(horizontal="center", vertical="center")
    
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 18
        
    ws.auto_filter.ref = ws.dimensions
    wb.save(buf)
    return buf.getvalue()

def generate_detailed_export(orders):
    """بناء التصدير التفصيلي الاحترافي مع المعادلات المحاسبية"""
    detailed_rows = []
    taxable_stats = {'sales': 0.0, 'qty': 0, 'tax': 0.0}
    nontaxable_stats = {'sales': 0.0, 'qty': 0, 'tax': 0.0}
    
    for order in orders:
        subtotal = float(order.get('amounts', {}).get('sub_total', {}).get('amount', 0))
        shipping_cost = float(order.get('amounts', {}).get('shipping_cost', {}).get('amount', 0))
        discounts = order.get('amounts', {}).get('discounts', [])
        
        total_coupon = sum(float(d.get('discount', 0)) for d in discounts if d.get('type') != 'special_offer' and 'عرض' not in str(d.get('title', '')))
        special_offers = [d for d in discounts if d.get('type') == 'special_offer' or 'عرض' in str(d.get('title', ''))]
        
        shipments = order.get('shipments', [])
        shipping_company = shipments[0].get('courier_name', '') if shipments else order.get('shipping', {}).get('company', '')
        branch = ""
        if shipments and shipments[0].get('ship_from', {}).get('name'):
            branch = shipments[0].get('ship_from', {}).get('name')
        elif order.get('shipping', {}).get('shipper', {}).get('company_name'):
            branch = order.get('shipping', {}).get('shipper', {}).get('company_name')

        items = order.get('items', [])
        for item in items:
            sku = str(item.get('sku', '')).strip()
            qty = int(item.get('quantity', 1))
            price_without_tax = float(item.get('amounts', {}).get('price_without_tax', {}).get('amount') or item.get('price', {}).get('amount', 0))
            item_subtotal = price_without_tax * qty
            
            # ✅ 1. توزيع خصم الكوبون تناسبياً
            item_coupon_share = (item_subtotal / subtotal) * total_coupon if subtotal > 0 else 0
            
            # ✅ 2. فحص العروض الخاصة المطابقة لـ SKU
            item_special_share = 0
            for sp in special_offers:
                sp_title = str(sp.get('title', ''))
                sp_discount = float(sp.get('discount', 0))
                if sku and sku in sp_title:
                    item_special_share += sp_discount
                    
            item_total_after_disc = item_subtotal - item_coupon_share - item_special_share
            if item_total_after_disc < 0: item_total_after_disc = 0
            
            # ✅ 3. حساب الضريبة
            tax_percent = float(item.get('amounts', {}).get('tax', {}).get('percent', 15.0))
            is_taxable = tax_percent > 0
            calculated_tax = item_total_after_disc * (tax_percent / 100) if is_taxable else 0.0
            
            # تحديث الإحصائيات
            if is_taxable:
                taxable_stats['sales'] += item_total_after_disc
                taxable_stats['qty'] += qty
                taxable_stats['tax'] += calculated_tax
            else:
                nontaxable_stats['sales'] += item_total_after_disc
                nontaxable_stats['qty'] += qty
                nontaxable_stats['tax'] += 0.0
            
            detailed_rows.append({
                "الفرع": branch,
                "تاريخ الطلب": str(order.get('date', {}).get('date', ''))[:10],
                "رقم الطلب": order.get('reference_id', ''),
                "حالة الطلب": order.get('status', {}).get('name', ''),
                "اسم العميل": f"{order.get('customer', {}).get('first_name', '')} {order.get('customer', {}).get('last_name', '')}".strip(),
                "المدينة": order.get('customer', {}).get('city', ''),
                "شركة الشحن": shipping_company,
                "رقم الصنف (SKU)": sku,
                "اسم الصنف": item.get('name', ''),
                "خاضع للضريبة": "نعم" if is_taxable else "لا",
                "الكمية": qty,
                "سعر الصنف (بدون ضريبة)": price_without_tax,
                "قيمة خصم الكوبون": round(item_coupon_share, 2),
                "قيمة خصم العرض الخاص": round(item_special_share, 2),
                "الاجمالي بعد الخصم": round(item_total_after_disc, 2),
                "تكلفة الشحن": shipping_cost,
                "الضريبة": round(calculated_tax, 2),
                "صافي المبيعات": round(item_total_after_disc, 2)
            })

    df = pd.DataFrame(detailed_rows)
    buf = io.BytesIO()
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "التصدير التفصيلي"
    ws.sheet_view.rightToLeft = True
    
    # 🌟 إضافة جدول الإحصائيات العلوي
    ws.merge_cells('A1:D1')
    ws['A1'] = "📊 إحصائيات المنتجات الخاضعة والغير خاضعة للضريبة"
    ws['A1'].font = Font(bold=True, size=13, color="FFFFFF")
    ws['A1'].fill = PatternFill(start_color="8E44AD", end_color="8E44AD", fill_type="solid")
    ws['A1'].alignment = Alignment(horizontal="center", vertical="center")
    
    stat_headers = ["النوع", "اجمالي قيمة المنتجات بعد الخصم", "الكمية المباعة", "قيمة الضريبة"]
    ws.append(stat_headers)
    for cell in ws[2]: cell.font = Font(bold=True); cell.fill = PatternFill(start_color="ECF0F1", fill_type="solid")
        
    ws.append(["خاضعة للضريبة", round(taxable_stats['sales'], 2), taxable_stats['qty'], round(taxable_stats['tax'], 2)])
    ws.append(["غير خاضعة للضريبة", round(nontaxable_stats['sales'], 2), nontaxable_stats['qty'], round(nontaxable_stats['tax'], 2)])
    ws.append([]) # سطر فارغ
    
    # 🌟 كتابة بيانات المنتجات والطلبات
    headers = list(df.columns)
    ws.append(headers)
    header_row_idx = ws.max_row
    
    for row in df.itertuples(index=False, name=None):
        ws.append(row)
        
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(color="00EBCF", bold=True)
    center_align = Alignment(horizontal="center", vertical="center")
    
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=header_row_idx, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 18
        
    ws.auto_filter.ref = f"A{header_row_idx}:{openpyxl.utils.get_column_letter(len(headers))}{ws.max_row}"
    wb.save(buf)
    return buf.getvalue()


def render_orders_page():
    st.markdown("""
    <div style="background: linear-gradient(135deg, #0F1C2E 0%, #8E44AD 100%); padding: 15px 25px; border-radius: 12px; color: white; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        <h2 style="color: white; margin: 0;">📦 تفاصيل طلبات المتجر (التصدير المحاسبي)</h2>
    </div>
    """, unsafe_allow_html=True)
    
    headers = get_headers()
    if not headers: return
    
    with st.container(border=True):
        st.markdown("#### 📅 حدد فترة استخراج الطلبات")
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            from_date = st.date_input("من تاريخ:", value=datetime.now().date() - timedelta(days=7))
        with col2:
            to_date = st.date_input("إلى تاريخ:", value=datetime.now().date())
        with col3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🚀 سحب الطلبات", use_container_width=True, type="primary"):
                st.session_state['from_date_orders'] = from_date.strftime('%Y-%m-%d')
                st.session_state['to_date_orders'] = to_date.strftime('%Y-%m-%d')
                
                with st.spinner("جاري سحب ملخص الطلبات..."):
                    orders_summary = get_orders_list(st.session_state['from_date_orders'], st.session_state['to_date_orders'], headers)
                    
                if not orders_summary:
                    st.warning("⚠️ لا توجد طلبات في هذه الفترة.")
                    st.session_state['detailed_fetched_orders'] = []
                else:
                    st.success(f"تم العثور على {len(orders_summary)} طلب. جاري جلب التفاصيل الدقيقة (SKU)...")
                    detailed_orders = get_detailed_orders(orders_summary, headers)
                    st.session_state['detailed_fetched_orders'] = detailed_orders

    # قسم التصدير يظهر فقط إذا تم السحب بنجاح
    if st.session_state.get('detailed_fetched_orders'):
        orders_data = st.session_state['detailed_fetched_orders']
        st.markdown("---")
        st.markdown("### 📥 خيارات التصدير")
        
        col_short, col_detailed = st.columns(2)
        with col_short:
            st.info("📌 **تصدير مختصر:** يعرض سطر واحد لكل طلب (شامل التحليلات، الخصومات المجمعة، والتصنيفات الأساسية).")
            excel_short = generate_short_export(orders_data)
            st.download_button(
                label="📥 تحميل تصدير إكسيل المختصر",
                data=excel_short,
                file_name=f"Orders_Short_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary"
            )
            
        with col_detailed:
            st.success("📊 **تصدير تفصيلي:** يفكك الطلب لعدة سطور حسب المنتجات لتوضيح (SKU، توزيع الخصومات، والضريبة لكل منتج).")
            excel_detailed = generate_detailed_export(orders_data)
            st.download_button(
                label="📥 تحميل تصدير إكسيل التفصيلي",
                data=excel_detailed,
                file_name=f"Orders_Detailed_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary"
            )
