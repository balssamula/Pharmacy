import pandas as pd
import numpy as np
import sqlite3
import uuid
import re
from datetime import datetime, timedelta
from utils.helpers import (
    normalize_order_number, normalize_sku, normalize_text,
    determine_branch, get_branch_number, is_gift_or_promotion, now_str
)
from utils.database import DB_PATH

def find_column(df, possible_names):
    """البحث عن عمود في DataFrame بأسماء محتملة"""
    for name in possible_names:
        if name in df.columns:
            return name
        clean_name = str(name).strip()
        for col in df.columns:
            if str(col).strip() == clean_name:
                return col
    return None

def prepare_salla_frame(df_salla: pd.DataFrame) -> pd.DataFrame:
    """معالجة شيت سلة - تجميع كميات نفس SKU لنفس رقم الطلب"""
    df = df_salla.copy()
    
    order_col = find_column(df, ['رقم الطلب', 'Order Number', 'order_number'])
    sku_col = find_column(df, ['SKU', 'Sku', 'sku'])
    product_col = find_column(df, ['اسم المنتج', 'Product Name', 'product_name'])
    qty_col = find_column(df, ['الكمية', 'Quantity', 'qty'])
    customer_col = find_column(df, ['اسم العميل', 'Customer Name', 'customer_name'])
    phone_col = find_column(df, ['رقم الجوال', 'Phone', 'phone'])
    city_col = find_column(df, ['المدينة', 'City', 'city'])
    status_col = find_column(df, ['حالة الطلب', 'Order Status', 'order_status'])
    date_col = find_column(df, ['تاريخ الطلب', 'Order Date', 'order_date'])
    total_col = find_column(df, ['إجمالي الطلب', 'Total', 'total'])
    discount_col = find_column(df, ['الخصم', 'Discount', 'discount'])
    shipping_col = find_column(df, ['تكلفة الشحن', 'Shipping Cost', 'shipping_cost'])
    payment_col = find_column(df, ['طريقة الدفع', 'Payment Method', 'payment_method'])
    tax_col = find_column(df, ['الضريبة', 'Tax', 'tax'])
    coupon_col = find_column(df, ['قيمة خصم الكوبون', 'Coupon Discount', 'coupon_discount'])
    offer_col = find_column(df, ['قيمة خصم العروض الخاصة', 'Offer Discount', 'offer_discount'])
    
    df["order_number"] = df[order_col].apply(normalize_order_number) if order_col else ""
    df["sku"] = df[sku_col].apply(normalize_sku) if sku_col else ""
    df["product_name"] = df[product_col].apply(normalize_text) if product_col else ""
    df["quantity"] = pd.to_numeric(df[qty_col], errors="coerce").fillna(0) if qty_col else 0
    df["customer_name"] = df[customer_col].apply(normalize_text) if customer_col else ""
    df["customer_phone"] = df[phone_col].apply(normalize_text) if phone_col else ""
    df["city"] = df[city_col].apply(normalize_text) if city_col else ""
    df["order_status"] = df[status_col].apply(normalize_text) if status_col else ""
    df["order_date"] = df[date_col].apply(normalize_text) if date_col else ""
    df["total_amount"] = pd.to_numeric(df[total_col], errors="coerce").fillna(0) if total_col else 0
    df["discount"] = pd.to_numeric(df[discount_col], errors="coerce").fillna(0) if discount_col else 0
    df["shipping_cost"] = pd.to_numeric(df[shipping_col], errors="coerce").fillna(0) if shipping_col else 0
    df["payment_method"] = df[payment_col].apply(normalize_text) if payment_col else ""
    df["tax"] = pd.to_numeric(df[tax_col], errors="coerce").fillna(0) if tax_col else 0
    df["coupon_discount"] = pd.to_numeric(df[coupon_col], errors="coerce").fillna(0) if coupon_col else 0
    df["offer_discount"] = pd.to_numeric(df[offer_col], errors="coerce").fillna(0) if offer_col else 0
    
    df = df[~df["customer_name"].apply(is_gift_or_promotion)]
    df = df[(df["order_number"] != "") & (df["sku"] != "") & (df["quantity"] != 0) & (df["order_status"] != "محذوف")].copy()
    
    branch_info = df.apply(lambda row: determine_branch(row["order_status"], row["city"]), axis=1)
    df["pharmacy_name"] = branch_info.apply(lambda x: x[0])
    df["branch_number"] = branch_info.apply(lambda x: x[1])
    
    grouped = df.groupby(["order_number", "sku"], as_index=False).agg({
        "product_name": "first", "quantity": "sum", "customer_name": "first", "customer_phone": "first",
        "city": "first", "order_status": "first", "order_date": "first", "total_amount": "first",
        "pharmacy_name": "first", "branch_number": "first", "discount": "first", "shipping_cost": "first",
        "payment_method": "first", "tax": "first", "coupon_discount": "first", "offer_discount": "first"
    }).rename(columns={"product_name": "salla_product_name", "quantity": "salla_qty", "pharmacy_name": "salla_pharmacy_name", "branch_number": "salla_branch_number"})
    return grouped

def prepare_abc_frame(df_abc: pd.DataFrame) -> pd.DataFrame:
    """معالجة شيت ABC - الحفاظ على كل فرع كسطر منفصل"""
    df = df_abc.copy()
    df = df[~df.iloc[:, 0].astype(str).str.contains('SUBTOTAL', na=False, case=False)]
    
    order_col = find_column(df, ['رقم الطلب', 'Order Number', 'order_number'])
    sku_col = find_column(df, ['رقم الصنف', 'Item No.', 'Item Number', 'item_number'])
    product_col = find_column(df, ['اسم الصنف', 'Product', 'product'])
    qty_col = find_column(df, ['Net Sold Qty', 'Net Qty.', 'Net Sold Quantity'])
    invoice_col = find_column(df, ['رقم الفاتورة', 'Receipt No.', 'receipt_no', 'invoice_number'])
    date_col = find_column(df, ['التاريخ', 'Date', 'date', 'Sales Date'])
    pharmacy_col = find_column(df, ['رقم الصيدلية', 'Branch', 'branch'])
    pharmacist_col = find_column(df, ['الصيدلي', 'Username', 'username'])
    profile_col = find_column(df, ['نوع البروفايل', 'Profile', 'profile'])
    
    if order_col is None and len(df.columns) > 30:
        order_col, invoice_col, date_col, profile_col, sku_col, product_col = df.columns[30], df.columns[28], df.columns[29], df.columns[0], df.columns[1], df.columns[2]
        qty_col = df.columns[9] if len(df.columns) > 9 else None
        pharmacy_col = df.columns[37] if len(df.columns) > 37 else None
        pharmacist_col = df.columns[44] if len(df.columns) > 44 else None
    
    if order_col is None: raise ValueError("لم يتم العثور على عمود رقم الطلب في شيت ABC")
    
    df["order_number"] = df[order_col].apply(normalize_order_number)
    df["sku"] = df[sku_col].apply(normalize_sku) if sku_col else ""
    df["abc_product_name"] = df[product_col].apply(normalize_text) if product_col else ""
    df["abc_qty"] = pd.to_numeric(df[qty_col], errors="coerce").fillna(0) if qty_col else 0
    df["invoice_number"] = df[invoice_col].apply(normalize_text) if invoice_col else ""
    df["invoice_date"] = df[date_col].apply(normalize_text) if date_col else ""
    df["abc_pharmacy_name"] = df[pharmacy_col].apply(normalize_text) if pharmacy_col else ""
    df["abc_pharmacist_name"] = df[pharmacist_col].apply(normalize_text) if pharmacist_col else ""
    df["profile_type"] = df[profile_col].apply(normalize_text) if profile_col else ""
    df["all_abc_pharmacies"] = df["abc_pharmacy_name"]
    df["receipt_classification"] = ""
    
    df = df[df["profile_type"] != "FREE GIFTS FOR CUSTOMERS"].copy() if "profile_type" in df.columns else df
    df = df[~df["abc_product_name"].str.upper().str.contains("DELIVERY FEE", na=False)] if "abc_product_name" in df.columns else df
    df = df[~df["sku"].isin(["", "0", "1", "200", "16133"])].copy()
    df = df[(df["sku"] != "") & (df["order_number"] != "")].copy()
    
    if df.empty: return pd.DataFrame()
    
    grouped = df.groupby(["order_number", "sku", "abc_pharmacy_name"], as_index=False).agg({
        "abc_qty": "sum",
        "invoice_number": lambda x: " | ".join(sorted(set(str(v) for v in x if v))),
        "invoice_date": "first", "abc_product_name": "first", "abc_pharmacist_name": "first",
        "profile_type": lambda x: " | ".join(sorted({normalize_text(v) for v in x if normalize_text(v)})),
        "receipt_classification": lambda x: " | ".join(sorted({normalize_text(v) for v in x if normalize_text(v)})),
        "all_abc_pharmacies": lambda x: " | ".join(sorted({normalize_text(v) for v in x if normalize_text(v)}))
    })
    return grouped

def classify_cases(df_salla: pd.DataFrame, df_abc: pd.DataFrame) -> pd.DataFrame:
    """تصنيف وفلترة الحالات بالفروع بناءً على الشروط الدقيقة والمطورة للمكررات والتداخلات"""
    if "order_status" in df_salla.columns:
        df_salla['order_status_clean'] = df_salla['order_status'].astype(str).str.strip()
        invalid_status_mask = df_salla['order_status_clean'].str.contains("ملغي|مسترجع|cancelled|returned|refunded", na=False, case=False)
        df_salla = df_salla[~invalid_status_mask].copy()

    salla_grouped = prepare_salla_frame(df_salla)
    abc_grouped = prepare_abc_frame(df_abc)
    
    if salla_grouped.empty and abc_grouped.empty: return pd.DataFrame()
        
    abc_total_qty = abc_grouped.groupby(["order_number", "sku"])["abc_qty"].sum().reset_index()
    abc_total_qty.rename(columns={"abc_qty": "abc_total_qty"}, inplace=True)
    
    salla_with_total = pd.merge(salla_grouped, abc_total_qty, on=["order_number", "sku"], how="left")
    salla_with_total["abc_total_qty"] = salla_with_total["abc_total_qty"].fillna(0)
    salla_with_total["total_matched"] = salla_with_total["salla_qty"] == salla_with_total["abc_total_qty"]
    
    merged = pd.merge(salla_with_total, abc_grouped, on=["order_number", "sku"], how="outer", indicator=True)
    
    for col in ["salla_qty", "abc_qty", "total_amount", "abc_total_qty"]:
        if col in merged.columns: merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0)
            
    merged["total_matched"] = merged["total_matched"].fillna(False)
    
    text_cols = ["salla_product_name", "abc_product_name", "customer_name", "customer_phone", "city", "order_status", "order_date", "invoice_number", "invoice_date", "salla_pharmacy_name", "abc_pharmacy_name", "abc_pharmacist_name", "profile_type", "receipt_classification"]
    for col in text_cols:
        if col not in merged.columns: merged[col] = ""
        merged[col] = merged[col].fillna("").astype(str)
        
    merged["product_name"] = merged["salla_product_name"].where(merged["salla_product_name"].str.strip() != "", merged["abc_product_name"])
    merged["pharmacy_name"] = merged["abc_pharmacy_name"].where(merged["abc_pharmacy_name"].str.strip() != "", merged["salla_pharmacy_name"])
    
    # ضبط وإدراج المحاذاة لسطر حساب الفروقات لمنع الـ IndentationError
    merged["difference"] = merged["salla_qty"] - merged["abc_qty"]
    merged["case_type"] = ""
    merged["case_reason"] = ""
    merged["is_duplicate_warning"] = 0
    
    max_salla_date = None
    salla_order_numbers = set()
    if not salla_grouped.empty:
        if "order_date" in salla_grouped.columns:
            salla_dates = pd.to_datetime(salla_grouped["order_date"], errors="coerce")
            if not salla_dates.isna().all(): max_salla_date = salla_dates.max()
        if "order_number" in salla_grouped.columns:
            salla_order_numbers = set(salla_grouped["order_number"].astype(str).str.strip().unique())
    
    # -------------------------------------------------------------------------
    # 🧠 حلقة الفرز الصارمة والمحدثة لاصطياد مكررات الفروع الموزعة
    # -------------------------------------------------------------------------
    for idx, row in merged.iterrows():
        salla_q = row['salla_qty']
        abc_q = row['abc_qty']
        abc_total = row['abc_total_qty']
        order_num = row['order_number']
        item_sku = row['sku']
        current_pharmacy = row['abc_pharmacy_name']
        diff_calc = salla_q - abc_q
        
        # 💡 [تحديث احترافي]: التحقق الفوري من وجود فواتير موازية في فروع أخرى وعزلها كفواتير معلقة
        other_branches_df = abc_grouped[
            (abc_grouped['order_number'] == order_num) & 
            (abc_grouped['sku'] == item_sku) & 
            (abc_grouped['abc_qty'] > 0) & 
            (abc_grouped['abc_pharmacy_name'] != current_pharmacy)
        ]
        
        if not other_branches_df.empty and abc_q > 0:
            other_branch_names = ", ".join(other_branches_df['abc_pharmacy_name'].unique())
            
            # تغيير تصنيف الحالة إلى نوع مخصص معزول ومحمي من فلاتر الفروقات الصفرية بالواجهات
            merged.at[idx, "case_type"] = "branch_conflict"
            merged.at[idx, "is_duplicate_warning"] = 1
            merged.at[idx, "case_reason"] = (
                f"⚠️ فواتير معلقة (تداخل ضرب الفواتير بين الفروع): هذا الصنف تم عمل فاتورة له في فرعك بكمية {int(abc_q)}، "
                f"وتم تكرار ضربه في فروع أخرى وهي ({other_branch_names}). إجمالي المضروب بكافة الفروع ({int(abc_total)}) "
                f"مقارنة بكمية سلة الأصلية المدفوعة ({int(salla_q)})."
            )
            continue

        # ب. استبعاد وحجب الفروع الصفرية المتطابقة إجمالياً
        if row['total_matched'] and abc_q == 0: continue
        if row['total_matched'] and salla_q == abc_q: continue

        # ج. الشرط الأول للإضافات: كمية الصنف في سلة أعلى من كمية نفس الصنف بالفرع الحالي
        if diff_calc > 0 and salla_q > 0 and abc_q > 0:
            merged.at[idx, "case_type"] = "addition"
            merged.at[idx, "case_reason"] = f"كمية طلب سلة المدفوعة ({int(salla_q)}) أعلى من كمية الفاتورة بالفرع ({int(abc_q)}). العجز يتطلب إضافة مخزنية حقيقية."
            continue

        # د. الشرط الثاني للإضافات الحتمية: الصنف موجود في سلة وليس له فاتورة نهائياً على ABC
        if (row['_merge'] == "left_only" or abc_total == 0) and salla_q > 0:
            merged.at[idx, "case_type"] = "orphan_salla"
            merged.at[idx, "case_reason"] = f"🛒 نقص مستندي كامل: صنف الطلب موجود في سلة بكمية {int(salla_q)} ولكن مستند الفاتورة مفقود بالكامل من نظام ABC."
            continue

        # هـ. حالات الإرجاع الصافية المستقرة (الكمية في ABC أكبر من سلة لطلب مطابق قائم بالفعل)
        if diff_calc < 0 and salla_q > 0 and abc_q > 0:
            merged.at[idx, "case_type"] = "return"
            merged.at[idx, "case_reason"] = f"كمية الفاتورة الموردة بالفرع ({int(abc_q)}) أكبر من كمية طلب سلة ({int(salla_q)}). الزيادة تتطلب إرجاع مخزني."
            continue

        # و. التوجيه الذكي والصارم للفواتير المجهولة
        if row['_merge'] == "right_only" and abc_q > 0:
            inv_date = pd.to_datetime(row['invoice_date'], errors='coerce')
            order_num_str = str(order_num).strip()
            
            if order_num_str not in salla_order_numbers and max_salla_date is not None and pd.notna(inv_date) and inv_date > max_salla_date:
                merged.at[idx, "case_type"] = "post_cutoff_abc"
                merged.at[idx, "case_reason"] = f"⏰ فاتورة بعد آخر طلب: رقم الطلب ({order_num}) غير موجود في شيت سلة، وتاريخ الفاتورة جاء متأخراً."
            else:
                merged.at[idx, "case_type"] = "orphan_abc"
                merged.at[idx, "case_reason"] = f"🔄 إرجاع حتمي (زيادة صنف): رقم الطلب ({order_num}) موجود في سلة ولكن هذا الصنف مضاف بزيادة في فواتير ABC بكمية {int(abc_q)}."
            continue

    result = merged[merged["case_type"] != ""].copy()
    if result.empty: return pd.DataFrame()
        
    result["case_label"] = result["case_type"]
    result["duplicate_warning"] = result["is_duplicate_warning"].apply(lambda x: "⚠️ منتج متداخل بين الفروع" if x == 1 else "")
    result["item_key"] = result.apply(lambda r: f"{r['pharmacy_name']}||{r['order_number']}||{r['sku']}||{r['case_type']}||{uuid.uuid4().hex[:4]}", axis=1)
    
    ordered_columns = ["item_key", "upload_batch_id", "order_number", "invoice_number", "sku", "product_name", "salla_product_name", "abc_product_name", "pharmacy_name", "salla_pharmacy_name", "abc_pharmacy_name", "abc_pharmacist_name", "branch_number", "salla_qty", "abc_qty", "difference", "case_type", "case_label", "case_reason", "status", "customer_name", "customer_phone", "city", "order_status", "order_date", "invoice_date", "profile_type", "receipt_classification", "all_abc_pharmacies", "other_branch_details", "pharmacist_note", "total_amount", "first_seen_at", "last_seen_at", "active", "hidden_from_pharmacy", "is_item_locked"]
    available_cols = [c for c in ordered_columns if c in result.columns]
    return result[available_cols]

# =========================================================================
# 📥 [الخطوة الأولى]: الدوال المطورة للربط الآلي والمطابقة عبر الـ API
# =========================================================================

def process_automated_sync(df_salla_raw: pd.DataFrame, df_abc_raw: pd.DataFrame, username: str = "نظام المزامنة الآلي"):
    """
    دالة معالجة ومطابقة البيانات تلقائياً القادمة مباشرة من الـ API (سلة + ABC)
    وتخزينها في قاعدة البيانات بدون الحاجة لرفع ملفات يدوية.
    """
    if df_salla_raw.empty or df_abc_raw.empty:
        print("⚠️ تحذير المزامنة: أحد الجداول المجلوبة من الـ API فارغ تماماً.")
        return None, None

    # تمرير البيانات مباشرة إلى دالة الفرز الصارم واصطياد الحالات والمكررات بين الفروع
    results = classify_cases(df_salla_raw, df_abc_raw)
    
    # إنشاء رقم دفعة مميز يحمل وسم آلي (Auto Sync Batch)
    upload_batch_id = f"auto_{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%m%d%H%M')}"
    timestamp = now_str()
    
    conn = sqlite3.connect(DB_PATH, timeout=60.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    cur = conn.cursor()
    
    try:
        # 1. تسجيل إحصائيات المزامنة الآلية في جدول المرفوعات
        cur.execute("""
            INSERT INTO uploads (upload_batch_id, file_name, uploaded_by, uploaded_at, total_cases,
                                 total_additions, total_returns, total_orphan_salla, total_orphan_abc, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (upload_batch_id, "مزامنة تلقائية (Live API)", username, timestamp, len(results),
              int((results["case_type"] == "addition").sum()) if not results.empty else 0,
              int((results["case_type"] == "return").sum()) if not results.empty else 0,
              int((results["case_type"] == "orphan_salla").sum()) if not results.empty else 0,
              int((results["case_type"] == "orphan_abc").sum()) if not results.empty else 0))
        
        # 2. حقن الحالات المستخرجة والمكررات في جدول التسويات
        if not results.empty:
            insert_df = results.copy()
            insert_df['upload_batch_id'] = upload_batch_id
            insert_df['status'] = 'قيد المتابعة'
            insert_df['pharmacist_note'] = ''
            insert_df['first_seen_at'] = timestamp
            insert_df['last_seen_at'] = timestamp
            insert_df['active'] = 1
            insert_df['hidden_from_pharmacy'] = 0
            insert_df['is_item_locked'] = 0
            insert_df['item_locked_by'] = ''
            insert_df['item_locked_at'] = ''
            insert_df['performed_by'] = ''
            insert_df['performed_at'] = ''
            
            valid_columns = [
                'item_key', 'upload_batch_id', 'order_number', 'invoice_number', 'sku',
                'product_name', 'salla_product_name', 'abc_product_name', 'pharmacy_name',
                'salla_pharmacy_name', 'abc_pharmacy_name', 'abc_pharmacist_name',
                'branch_number', 'salla_branch_number', 'salla_qty', 'abc_qty', 'difference',
                'case_type', 'case_label', 'case_reason', 'status', 'performed_by', 'performed_at',
                'customer_name', 'customer_phone', 'city', 'order_status', 'order_date',
                'invoice_date', 'profile_type', 'receipt_classification', 'all_abc_pharmacies',
                'other_branch_details', 'pharmacist_note', 'total_amount', 'first_seen_at',
                'last_seen_at', 'active', 'hidden_from_pharmacy', 'payment_method',
                'discount', 'shipping_cost', 'tax', 'coupon_discount', 'offer_discount',
                'is_item_locked', 'item_locked_by', 'item_locked_at'
            ]
            
            # تنظيف وتجهيز الأعمدة لـ SQLite
            cols_to_drop = [col for col in insert_df.columns if col not in valid_columns]
            if cols_to_drop: insert_df = insert_df.drop(columns=cols_to_drop)
                
            for col in valid_columns:
                if col not in insert_df.columns:
                    if col in ['salla_qty', 'abc_qty', 'difference', 'total_amount', 'discount', 'shipping_cost', 'tax', 'coupon_discount', 'offer_discount']:
                        insert_df[col] = 0.0
                    elif col in ['is_item_locked']:
                        insert_df[col] = 0
                    else:
                        insert_df[col] = ''
                        
            insert_df = insert_df[valid_columns]
            
            columns = list(insert_df.columns)
            placeholders = ", ".join(["?"] * len(columns))
            sql_query = f"INSERT OR REPLACE INTO reconciliation_items ({', '.join(columns)}) VALUES ({placeholders})"
            cur.executemany(sql_query, insert_df.values.tolist())
            
        # 3. أرشفة وتحديث الجلسات لتفعيل التحديث اللحظي المباشر
        cur.execute("UPDATE reconciliation_items SET active = CASE WHEN upload_batch_id = ? THEN 1 ELSE 0 END", (upload_batch_id,))
        cur.execute("UPDATE uploads SET is_active = 0")
        cur.execute("UPDATE uploads SET is_active = 1 WHERE upload_batch_id = ?", (upload_batch_id,))
        
        session_name = f"🔄 مزامنة آلية {datetime.now().strftime('%H:%M')}"
        cur.execute("UPDATE uploads SET session_name = ? WHERE upload_batch_id = ?", (session_name, upload_batch_id))
        
        conn.commit()
        print(f"🚀 تم نجاح المزامنة الآلية بنجاح تحت الـ Batch ID: {upload_batch_id}")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ خطأ أثناء معالجة وحقن بيانات المزامنة: {e}")
        raise e
    finally:
        cur.close()
        conn.close()
        
    return results, upload_batch_id
    
    
def process_excel(uploaded_file, username):
    df_salla = pd.read_excel(uploaded_file, sheet_name="سلة")
    df_abc = pd.read_excel(uploaded_file, sheet_name="abc")
    results = classify_cases(df_salla, df_abc)
    
    upload_batch_id = f"batch_{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%m%d%H%M')}"
    timestamp = now_str()
    
    conn = sqlite3.connect(DB_PATH, timeout=60.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    cur = conn.cursor()
    
    try:
        cur.execute("""
            INSERT INTO uploads (upload_batch_id, file_name, uploaded_by, uploaded_at, total_cases,
                                 total_additions, total_returns, total_orphan_salla, total_orphan_abc, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (upload_batch_id, uploaded_file.name, username, timestamp, len(results),
              int((results["case_type"] == "addition").sum()) if not results.empty else 0,
              int((results["case_type"] == "return").sum()) if not results.empty else 0,
              int((results["case_type"] == "orphan_salla").sum()) if not results.empty else 0,
              int((results["case_type"] == "orphan_abc").sum()) if not results.empty else 0))
        
        if not results.empty:
            insert_df = results.copy()
            insert_df['upload_batch_id'] = upload_batch_id
            insert_df['status'] = 'قيد المتابعة'
            insert_df['pharmacist_note'] = ''
            insert_df['first_seen_at'] = timestamp
            insert_df['last_seen_at'] = timestamp
            insert_df['active'] = 1
            insert_df['hidden_from_pharmacy'] = 0
            insert_df['is_item_locked'] = 0
            insert_df['item_locked_by'] = ''
            insert_df['item_locked_at'] = ''
            insert_df['performed_by'] = ''
            insert_df['performed_at'] = ''
            
            valid_columns = ['item_key', 'upload_batch_id', 'order_number', 'invoice_number', 'sku', 'product_name', 'salla_product_name', 'abc_product_name', 'pharmacy_name', 'salla_pharmacy_name', 'abc_pharmacy_name', 'abc_pharmacist_name', 'branch_number', 'salla_branch_number', 'salla_qty', 'abc_qty', 'difference', 'case_type', 'case_label', 'case_reason', 'status', 'performed_by', 'performed_at', 'customer_name', 'customer_phone', 'city', 'order_status', 'order_date', 'invoice_date', 'profile_type', 'receipt_classification', 'all_abc_pharmacies', 'other_branch_details', 'pharmacist_note', 'total_amount', 'first_seen_at', 'last_seen_at', 'active', 'hidden_from_pharmacy', 'payment_method', 'discount', 'shipping_cost', 'tax', 'coupon_discount', 'offer_discount', 'is_item_locked', 'item_locked_by', 'item_locked_at']
            
            cols_to_drop = [col for col in insert_df.columns if col not in valid_columns]
            if cols_to_drop: insert_df = insert_df.drop(columns=cols_to_drop)
                
            for col in valid_columns:
                if col not in insert_df.columns:
                    if col in ['performed_by', 'performed_at', 'item_locked_by', 'item_locked_at', 'branch_number', 'salla_branch_number']: insert_df[col] = ''
                    elif col in ['is_item_locked']: insert_df[col] = 0
                    elif col in ['salla_qty', 'abc_qty', 'difference', 'total_amount', 'discount', 'shipping_cost', 'tax', 'coupon_discount', 'offer_discount']: insert_df[col] = 0.0
                    else: insert_df[col] = ''
                        
            insert_df = insert_df[valid_columns]
            sqlite3.register_adapter(int, lambda x: int(x))
            sqlite3.register_adapter(float, lambda x: float(x))
            
            columns = list(insert_df.columns)
            placeholders = ", ".join(["?"] * len(columns))
            sql_query = f"INSERT OR REPLACE INTO reconciliation_items ({', '.join(columns)}) VALUES ({placeholders})"
            cur.executemany(sql_query, insert_df.values.tolist())
            
        cur.execute("UPDATE reconciliation_items SET active = CASE WHEN upload_batch_id = ? THEN 1 ELSE 0 END", (upload_batch_id,))
        cur.execute("UPDATE uploads SET is_active = 0")
        cur.execute("UPDATE uploads SET is_active = 1 WHERE upload_batch_id = ?", (upload_batch_id,))
        
        session_name = datetime.now().strftime("%Y-%m-%d %H:%M")
        cur.execute("UPDATE uploads SET session_name = ? WHERE upload_batch_id = ?", (session_name, upload_batch_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()
    # تمرير الجداول بعد قراءتها يدوياً لنفس آلية التخزين
    return process_automated_sync(df_salla, df_abc, username)
    
def update_balances(abc_file, salla_file):
    try:
        df_abc = pd.read_excel(abc_file, skiprows=4)
        df_salla = pd.read_excel(salla_file)
        def get_abc_col(branch_num): return pd.to_numeric(df_abc.iloc[:, branch_num + 1], errors='coerce').fillna(0)
        item_key = df_abc.iloc[:, 0]
        tabuk_calc = np.floor(((get_abc_col(8) + get_abc_col(10) + get_abc_col(11) + get_abc_col(12) + get_abc_col(14) + get_abc_col(15) + get_abc_col(16) + get_abc_col(17)) / 2) + get_abc_col(13))
        f9_calc = np.floor(((get_abc_col(1) + get_abc_col(3)) / 2) + get_abc_col(9))
        def create_map(values): return dict(zip(item_key, values.astype(int)))
        
        maps = {
            'tabuk': create_map(tabuk_calc), 'f9': create_map(f9_calc),
            'f1': create_map(get_abc_col(1)), 'f2': create_map(get_abc_col(2)), 'f3': create_map(get_abc_col(3)), 'f4': create_map(get_abc_col(4)), 'f5': create_map(get_abc_col(5)), 'f6': create_map(get_abc_col(6)), 'f7': create_map(get_abc_col(7)), 'f8': create_map(get_abc_col(8)), 'f10': create_map(get_abc_col(10)), 'f11': create_map(get_abc_col(11)), 'f12': create_map(get_abc_col(12)), 'f14': create_map(get_abc_col(14)), 'f15': create_map(get_abc_col(15)), 'f16': create_map(get_abc_col(16)), 'f17': create_map(get_abc_col(17))
        }
        df_updated = df_salla.copy()
        salla_id_col = 3
        col_mapping = {5: 'tabuk', 7: 'f8', 9: 'f9', 11: 'f11', 13: 'f15', 15: 'f16', 17: 'f10', 21: 'f12', 23: 'f14', 25: 'f1', 27: 'f2', 29: 'f3', 31: 'f4', 33: 'f5', 35: 'f6', 37: 'f7', 39: 'f17'}
        
        for col_idx, map_name in col_mapping.items(): df_updated.iloc[:, col_idx] = df_updated.iloc[:, salla_id_col].map(maps[map_name]).fillna(0).astype(int)
        cols_to_check = list(col_mapping.keys())
        old_data = df_salla.iloc[:, cols_to_check].apply(pd.to_numeric, errors='coerce').fillna(0).astype(int)
        new_data = df_updated.iloc[:, cols_to_check]
        is_different = (new_data.values != old_data.values).any(axis=1)
        has_balance = new_data.sum(axis=1) > 0
        df_final = df_updated[is_different & has_balance]
        return df_final, len(df_final)
    except Exception as e: return None, str(e)
