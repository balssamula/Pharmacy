import streamlit as st
import pandas as pd
import io
import time
from datetime import datetime, timedelta
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from utils import get_headers, safe_api_request, SALLA_API_URL

def get_orders_list(from_date, to_date, headers, search_keyword=None, order_refs_list=None):
    """سحب الطلبات: يدعم التواريخ، كلمة بحث، أو قائمة أرقام طلبات من ملف"""
    orders = []
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    # ✅ حالة 1: السحب بناءً على ملف أرقام الطلبات المرفوع
    if order_refs_list and len(order_refs_list) > 0:
        total = len(order_refs_list)
        for idx, ref in enumerate(order_refs_list):
            status_text.info(f"📥 جاري سحب الطلب رقم {ref} ({idx+1} من {total})...")
            url = f"https://api.salla.dev/admin/v2/orders?keyword={ref}"
            res = safe_api_request("GET", url, headers)
            if res and res.get("data"):
                # قد يرجع عدة نتائج، نأخذ المطابق تماماً
                matched = [o for o in res["data"] if str(o.get('reference_id')) == str(ref)]
                orders.extend(matched if matched else res["data"])
            progress_bar.progress((idx + 1) / total)
            time.sleep(0.15)
            
    # ✅ حالة 2: السحب بالتواريخ أو كلمة البحث
    else:
        page = 1
        total_pages = 1
        while page <= total_pages:
            status_text.info(f"📥 جاري حصر الطلبات (صفحة {page} من {total_pages if page > 1 else '...'})...")
            url = f"https://api.salla.dev/admin/v2/orders?from_date={from_date}&to_date={to_date}&per_page=50&page={page}"
            if search_keyword: url += f"&keyword={search_keyword}"
                
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
    """سحب التفاصيل الدقيقة والفواتير للطلبات"""
    detailed_orders = []
    status_text = st.empty()
    progress_bar = st.progress(0)
    total = len(orders_summary)
    
    for i, o_sum in enumerate(orders_summary):
        status_text.info(f"🔍 جاري سحب التفاصيل والفواتير للطلب {o_sum.get('reference_id')} ({i+1} من {total})...")
        order_id = o_sum.get("id")
        
        res_order = safe_api_request("GET", f"https://api.salla.dev/admin/v2/orders/{order_id}", headers)
        order_data = res_order.get("data", {}) if res_order else {}
        
        items_data = []
        res_inv_list = safe_api_request("GET", f"https://api.salla.dev/admin/v2/orders/invoices?order_id={order_id}", headers)
        if res_inv_list and res_inv_list.get("data"):
            invoice_id = res_inv_list["data"][0]["id"]
            res_inv_det = safe_api_request("GET", f"https://api.salla.dev/admin/v2/orders/invoices/{invoice_id}", headers)
            if res_inv_det and res_inv_det.get("data"):
                items_data = res_inv_det["data"].get("items", [])
                
        if not items_data:
            summary_items = o_sum.get('items', [])
            for si in summary_items:
                items_data.append({
                    'name': si.get('name', ''), 'quantity': si.get('quantity', 1), 'sku': 'غير متوفر',
                    'price': {'amount': 0}, 'tax': {'percent': 0}, 'options': si.get('options', [])
                })
        else:
            # دمج الخيارات (Options) من الطلب الأصلي إلى الفاتورة إن وُجدت
            orig_items = order_data.get('items', [])
            for inv_item in items_data:
                match_orig = next((oi for oi in orig_items if str(oi.get('sku')) == str(inv_item.get('sku'))), None)
                if match_orig: inv_item['options'] = match_orig.get('options', [])
                
        order_data['items'] = items_data
        detailed_orders.append(order_data)
        progress_bar.progress((i + 1) / total)
        time.sleep(0.3)
        
    status_text.success(f"✅ تم سحب التفاصيل والفواتير لـ {total} طلب بنجاح!")
    progress_bar.empty()
    return detailed_orders


def generate_short_export(orders):
    """بناء التصدير المختصر الاحترافي"""
    rows = []
    columns_list = [
        "الفرع", "تاريخ الطلب", "رقم الطلب", "حالة الطلب", "اسم العميل",
        "رقم الجوال", "بريد العميل", "المدينة", "شركة الشحن", "طريقة الدفع",
        "utm_source", "مجموع السلة", "الخصم الإجمالي", "قيمة خصم الكوبون",
        "قيمة خصم العروض الخاصة", "الاجمالي بعد الخصم", "تكلفة الشحن",
        "الضريبة", "صافي المبيعات", "المبلغ المسترجع"
    ]
    
    for order in orders:
        discounts = order.get('amounts', {}).get('discounts', [])
        coupon_disc = sum(float(d.get('discount', 0)) for d in discounts if d.get('type') != 'special_offer' and 'عرض' not in str(d.get('title', '')))
        special_disc = sum(float(d.get('discount', 0)) for d in discounts if d.get('type') == 'special_offer' or 'عرض' in str(d.get('title', '')))
        total_discount = coupon_disc + special_disc
        
        subtotal = float(order.get('amounts', {}).get('sub_total', {}).get('amount', 0))
        shipping = float(order.get('amounts', {}).get('shipping_cost', {}).get('amount', 0))
        tax = float(order.get('amounts', {}).get('tax', {}).get('amount', {}).get('amount', 0))
        refund = float(order.get('payment_actions', {}).get('refund_action', {}).get('refund_amount', {}).get('amount', 0))
        
        total_after_disc = subtotal - total_discount
        order_branches = order.get('order_branches', [])
        branch = order_branches[0].get('name', 'الفرع الرئيسي') if order_branches else 'غير متوفر'

        rows.append({
            "الفرع": branch,
            "تاريخ الطلب": str(order.get('date', {}).get('date', ''))[:10],
            "رقم الطلب": order.get('reference_id', ''),
            "حالة الطلب": order.get('status', {}).get('name', ''),
            "اسم العميل": f"{order.get('customer', {}).get('first_name', '')} {order.get('customer', {}).get('last_name', '')}".strip(),
            "رقم الجوال": f"{order.get('customer', {}).get('mobile_code', '')}{order.get('customer', {}).get('mobile', '')}",
            "بريد العميل": order.get('customer', {}).get('email', ''),
            "المدينة": order.get('customer', {}).get('city', ''),
            "شركة الشحن": 'غير متوفر',
            "طريقة الدفع": order.get('payment_method', ''),
            "utm_source": order.get('source_details', {}).get('utm_source', '') or order.get('campaign', {}).get('source', ''),
            "مجموع السلة": subtotal,
            "الخصم الإجمالي": total_discount,
            "قيمة خصم الكوبون": coupon_disc,
            "قيمة خصم العروض الخاصة": special_disc,
            "الاجمالي بعد الخصم": total_after_disc,
            "تكلفة الشحن": shipping,
            "الضريبة": tax,
            "صافي المبيعات": total_after_disc,
            "المبلغ المسترجع": refund
        })
        
    df = pd.DataFrame(rows, columns=columns_list)
    buf = io.BytesIO()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "التصدير المختصر"
    ws.sheet_view.rightToLeft = True
    
    headers = list(df.columns)
    ws.append(headers)
    for row in df.itertuples(index=False, name=None): ws.append(row)
        
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(color="00EBCF", bold=True, size=12)
    center_align = Alignment(horizontal="center", vertical="center")
    
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.fill = header_fill; cell.font = header_font; cell.alignment = center_align
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 18
        
    ws.auto_filter.ref = f"A1:{openpyxl.utils.get_column_letter(len(headers))}{ws.max_row}"
    wb.save(buf)
    return buf.getvalue()


def generate_detailed_export(orders):
    """بناء التصدير التفصيلي مع الأصناف الفرعية وتوزيع الخصومات الذكي"""
    detailed_rows = []
    taxable_stats = {'sales': 0.0, 'qty': 0, 'tax': 0.0}
    nontaxable_stats = {'sales': 0.0, 'qty': 0, 'tax': 0.0}
    
    columns_list = [
        "الفرع", "تاريخ الطلب", "رقم الطلب", "حالة الطلب", "اسم العميل",
        "المدينة", "شركة الشحن", "رقم الصنف (SKU)", "اسم الصنف", "الأصناف الفرعية", "خاضع للضريبة",
        "الكمية", "سعر الصنف (بدون ضريبة)", "قيمة خصم الكوبون", "قيمة خصم العرض الخاص",
        "الاجمالي بعد الخصم", "تكلفة الشحن", "الضريبة", "صافي المبيعات"
    ]
    
    for order in orders:
        subtotal = float(order.get('amounts', {}).get('sub_total', {}).get('amount', 0))
        shipping_cost = float(order.get('amounts', {}).get('shipping_cost', {}).get('amount', 0))
        discounts = order.get('amounts', {}).get('discounts', [])
        
        # تصنيف الخصومات
        total_coupon = sum(float(d.get('discount', 0)) for d in discounts if d.get('type') != 'special_offer' and 'عرض' not in str(d.get('title', '')))
        all_special_offers = [d for d in discounts if d.get('type') == 'special_offer' or 'عرض' in str(d.get('title', ''))]
        
        # ✅ فصل العروض الخاصة (المطابقة لـ SKU مقابل العروض العامة للطلب)
        order_skus = [str(item.get('sku', '')).strip() for item in order.get('items', [])]
        specific_offers = []
        general_offers_total = 0.0
        
        for sp in all_special_offers:
            sp_title = str(sp.get('title', ''))
            matched = any(sku and sku in sp_title for sku in order_skus)
            if matched:
                specific_offers.append(sp)
            else:
                general_offers_total += float(sp.get('discount', 0))

        order_branches = order.get('order_branches', [])
        branch = order_branches[0].get('name', 'الفرع الرئيسي') if order_branches else 'غير متوفر'

        items = order.get('items', [])
        for item in items:
            sku = str(item.get('sku', 'غير متوفر')).strip()
            main_qty = int(item.get('quantity', 1))
            
            price_without_tax = float(item.get('amounts', {}).get('price_without_tax', {}).get('amount') or item.get('price', {}).get('amount', 0))
            tax_node = item.get('amounts', {}).get('tax', {}) if 'amounts' in item else item.get('tax', {})
            tax_percent = float(tax_node.get('percent', 15.0) if tax_node.get('percent') is not None else 15.0)
            
            item_subtotal = price_without_tax * main_qty
            
            # ✅ 1. توزيع الكوبون والعروض العامة (التي لا تحمل SKU) بشكل تناسبي
            ratio = (item_subtotal / subtotal) if subtotal > 0 else 0
            item_coupon_share = ratio * total_coupon
            item_general_special_share = ratio * general_offers_total
            
            # ✅ 2. خصم العروض المخصصة لـ SKU
            item_specific_special_share = sum(float(sp.get('discount', 0)) for sp in specific_offers if sku != 'غير متوفر' and sku in str(sp.get('title', '')))
            
            total_special_share = item_general_special_share + item_specific_special_share
            
            item_total_after_disc = item_subtotal - item_coupon_share - total_special_share
            if item_total_after_disc < 0: item_total_after_disc = 0
            
            is_taxable = tax_percent > 0
            calculated_tax = item_total_after_disc * (tax_percent / 100) if is_taxable else 0.0
            
            # ✅ استخراج الأصناف الفرعية (Options / Bundles)
            sub_items_extracted = []
            for opt in item.get('options', []):
                opt_name = opt.get('name', '')
                val = opt.get('value')
                if isinstance(val, list):
                    for v in val: sub_items_extracted.append({"name": f"{opt_name}: {v.get('name', '')}", "qty": main_qty})
                elif isinstance(val, dict):
                    sub_items_extracted.append({"name": f"{opt_name}: {val.get('name', '')}", "qty": main_qty})
                else:
                    sub_items_extracted.append({"name": f"{opt_name}: {val}", "qty": main_qty})
            
            if not sub_items_extracted:
                sub_items_extracted = [{"name": "بدون", "qty": main_qty}]
                
            # تحديث الإحصائيات (كمية الفرعي تطغى على الرئيسي)
            qty_for_stats = sum(si['qty'] for si in sub_items_extracted) if sub_items_extracted[0]['name'] != "بدون" else main_qty
            if is_taxable:
                taxable_stats['sales'] += item_total_after_disc
                taxable_stats['qty'] += qty_for_stats
                taxable_stats['tax'] += calculated_tax
            else:
                nontaxable_stats['sales'] += item_total_after_disc
                nontaxable_stats['qty'] += qty_for_stats
                nontaxable_stats['tax'] += 0.0
            
            # ✅ كتابة الأسطر (تقسيم الأموال على عدد المكونات الفرعية لضمان الدقة المحاسبية للإكسيل)
            splits = len(sub_items_extracted)
            for sub in sub_items_extracted:
                detailed_rows.append({
                    "الفرع": branch,
                    "تاريخ الطلب": str(order.get('date', {}).get('date', ''))[:10],
                    "رقم الطلب": order.get('reference_id', ''),
                    "حالة الطلب": order.get('status', {}).get('name', ''),
                    "اسم العميل": f"{order.get('customer', {}).get('first_name', '')} {order.get('customer', {}).get('last_name', '')}".strip(),
                    "المدينة": order.get('customer', {}).get('city', ''),
                    "شركة الشحن": 'غير متوفر',
                    "رقم الصنف (SKU)": sku,
                    "اسم الصنف": item.get('name', ''),
                    "الأصناف الفرعية": sub['name'],
                    "خاضع للضريبة": "نعم" if is_taxable else "لا",
                    "الكمية": sub['qty'],
                    "سعر الصنف (بدون ضريبة)": price_without_tax / splits,
                    "قيمة خصم الكوبون": round(item_coupon_share / splits, 2),
                    "قيمة خصم العرض الخاص": round(total_special_share / splits, 2),
                    "الاجمالي بعد الخصم": round(item_total_after_disc / splits, 2),
                    "تكلفة الشحن": shipping_cost / splits,
                    "الضريبة": round(calculated_tax / splits, 2),
                    "صافي المبيعات": round(item_total_after_disc / splits, 2)
                })

    df = pd.DataFrame(detailed_rows, columns=columns_list)
    buf = io.BytesIO()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "التصدير التفصيلي"
    ws.sheet_view.rightToLeft = True
    
    ws.merge_cells('A1:D1')
    ws['A1'] = "📊 إحصائيات المنتجات (باحتساب الأصناف الفرعية)"
    ws['A1'].font = Font(bold=True, size=13, color="FFFFFF")
    ws['A1'].fill = PatternFill(start_color="8E44AD", end_color="8E44AD", fill_type="solid")
    ws['A1'].alignment = Alignment(horizontal="center", vertical="center")
    
    stat_headers = ["النوع", "اجمالي قيمة المنتجات بعد الخصم", "الكمية المباعة", "قيمة الضريبة"]
    ws.append(stat_headers)
    for cell in ws[2]: cell.font = Font(bold=True); cell.fill = PatternFill(start_color="ECF0F1", fill_type="solid")
        
    ws.append(["خاضعة للضريبة", round(taxable_stats['sales'], 2), taxable_stats['qty'], round(taxable_stats['tax'], 2)])
    ws.append(["غير خاضعة للضريبة", round(nontaxable_stats['sales'], 2), nontaxable_stats['qty'], round(nontaxable_stats['tax'], 2)])
    ws.append([])
    
    headers = list(df.columns)
    ws.append(headers)
    header_row_idx = ws.max_row
    for row in df.itertuples(index=False, name=None): ws.append(row)
        
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(color="00EBCF", bold=True)
    center_align = Alignment(horizontal="center", vertical="center")
    
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=header_row_idx, column=col)
        cell.fill = header_fill; cell.font = header_font; cell.alignment = center_align
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
        st.markdown("#### 🔍 أدوات البحث واستخراج الطلبات")
        
        # رفع ملف أرقام الطلبات
        uploaded_orders_file = st.file_uploader("📂 رفع ملف أرقام الطلبات (اختياري - Excel/CSV):", type=["xlsx", "csv"], help="ضع أرقام الطلبات في العمود الأول للملف.")
        order_refs_from_file = []
        if uploaded_orders_file:
            try:
                df_refs = pd.read_excel(uploaded_orders_file) if uploaded_orders_file.name.endswith('.xlsx') else pd.read_csv(uploaded_orders_file)
                order_refs_from_file = df_refs.iloc[:, 0].dropna().astype(str).tolist()
                st.success(f"✅ تم قراءة {len(order_refs_from_file)} رقم طلب من الملف.")
            except Exception as e:
                st.error("خطأ في قراءة الملف.")
        
        search_query = st.text_input("🔎 ابحث برقم الطلب أو الجوال (اختياري):", placeholder="مثال: 41027662", disabled=bool(order_refs_from_file))
        
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1: from_date = st.date_input("من تاريخ:", value=datetime.now().date() - timedelta(days=7), disabled=bool(order_refs_from_file))
        with col2: to_date = st.date_input("إلى تاريخ:", value=datetime.now().date(), disabled=bool(order_refs_from_file))
        with col3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🚀 سحب الطلبات", use_container_width=True, type="primary"):
                with st.spinner("جاري السحب..."):
                    orders_summary = get_orders_list(
                        from_date.strftime('%Y-%m-%d'), to_date.strftime('%Y-%m-%d'), headers,
                        search_keyword=search_query.strip() if search_query else None,
                        order_refs_list=order_refs_from_file
                    )
                if not orders_summary:
                    st.warning("⚠️ لا توجد طلبات مطابقة.")
                    st.session_state['detailed_fetched_orders'] = []
                else:
                    detailed_orders = get_detailed_orders(orders_summary, headers)
                    st.session_state['detailed_fetched_orders'] = detailed_orders

    if st.session_state.get('detailed_fetched_orders'):
        orders_data = st.session_state['detailed_fetched_orders']
        
        st.markdown("---")
        st.markdown(f"### 📋 استعراض الطلبات المسحوبة ({len(orders_data)})")
        
        # ✅ عرض الطلبات في كروت إبداعية
        cols = st.columns(2)
        for i, o in enumerate(orders_data):
            col = cols[i % 2]
            c_name = f"{o.get('customer', {}).get('first_name', '')} {o.get('customer', {}).get('last_name', '')}".strip()
            o_date = str(o.get('date', {}).get('date', ''))[:16]
            o_total = o.get('amounts', {}).get('total', {}).get('amount', 0)
            status_name = o.get('status', {}).get('name', 'غير محدد')
            
            # تحديد لون الكارت بناء على الحالة
            border_color = "#2ecc71" if "تنفيذ" in status_name or "توصيل" in status_name else ("#e74c3c" if "لغي" in status_name else "#f39c12")
            
            with col:
                st.markdown(f"""
                <div style='background: #1a2639; border-radius: 10px; padding: 15px; margin-bottom: 15px; border-right: 4px solid {border_color}; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
                    <div style='display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #2d3a4a; padding-bottom: 10px; margin-bottom: 10px;'>
                        <span style='color: #00EBCF; font-size: 16px; font-weight: bold;'>📦 طلب #{o.get('reference_id')}</span>
                        <span style='background: rgba(255,255,255,0.1); padding: 4px 10px; border-radius: 12px; font-size: 12px; color: {border_color};'>{status_name}</span>
                    </div>
                    <div style='font-size: 14px; color: #cbd5e1; line-height: 1.8;'>
                        👤 <b>العميل:</b> {c_name}<br>
                        📅 <b>التاريخ:</b> {o_date}<br>
                        💰 <b>الإجمالي:</b> <span style='color:#f1c40f; font-weight:bold;'>{o_total} SAR</span><br>
                        💳 <b>الدفع:</b> {o.get('payment_method', 'غير محدد')}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                with st.expander("🛒 عرض المنتجات"):
                    for item in o.get('items', []):
                        st.markdown(f"- `{item.get('sku', 'بدون SKU')}` | {item.get('name')} (الكمية: **{item.get('quantity', 1)}**)")
                
        st.markdown("---")
        st.markdown("### 📥 خيارات التصدير")
        
        col_short, col_detailed = st.columns(2)
        with col_short:
            excel_short = generate_short_export(orders_data)
            st.download_button(label="📥 تحميل تصدير إكسيل المختصر", data=excel_short, file_name=f"Orders_Short_{datetime.now().strftime('%Y%m%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, type="primary")
            
        with col_detailed:
            excel_detailed = generate_detailed_export(orders_data)
            st.download_button(label="📥 تحميل تصدير إكسيل التفصيلي (شامل الفرعيات)", data=excel_detailed, file_name=f"Orders_Detailed_{datetime.now().strftime('%Y%m%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, type="primary")
