# ==========================================
# 🏢 دوال إدارة الفروع وتحديث الكميات الجماعي
# ==========================================

def get_branches_list() -> List[Dict]:
    headers = get_headers()
    if not headers: return []
    res = safe_api_request("GET", "https://api.salla.dev/admin/v2/branches", headers)
    return res.get("data", []) if res else []

def get_product_quantities_by_branch(product_id: int = None, branch_id: int = None, headers: dict = None) -> List[Dict]:
    """جلب كميات المنتجات في الفروع مع أسماء الفروع"""
    if not headers:
        headers = get_headers()
        if not headers: return []
    
    branches = get_branches_list()
    branch_names = {b.get('id'): b.get('name', 'فرع غير معروف') for b in branches}
    
    url = "https://api.salla.dev/admin/v2/products/quantities"
    params = {}
    if product_id: params["product_id"] = product_id
    if branch_id: params["branch"] = branch_id
    
    res = safe_api_request("GET", url, headers, params=params)
    data = res.get("data", []) if res else []
    
    seen = {}
    unique_data = []
    for item in data:
        item['branch_name'] = branch_names.get(item.get('branch_id'), 'فرع غير معروف')
        branch_id_key = item.get('branch_id')
        if branch_id_key not in seen:
            seen[branch_id_key] = True
            unique_data.append(item)
    
    if not unique_data and branches:
        for b in branches:
            unique_data.append({'branch_id': b.get('id'), 'branch_name': b.get('name', 'فرع غير معروف'), 'quantity': 0, 'sku': None})
            
    return unique_data

def generate_quantities_template() -> bytes:
    from openpyxl import Workbook
    from openpyxl.worksheet.datavalidation import DataValidation
    output = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "تحديث الكميات"
    ws.append(["💡 إرشادات: ادخل رقم الـ SKU للمنتج، ومعرف الفرع، والكمية، ثم اختر نوع العملية من القائمة المنسدلة (increment للزيادة، decrement للنقصان، overwrite للاستبدال)."])
    ws.merge_cells('A1:D1')
    ws.row_dimensions[1].height = 24
    ws.append(["Product_SKU", "Branch_ID", "Quantity", "Mode"])
    ws.append(["SKU-123", "12345", 50, "increment"])
    style_excel_file(ws, is_template=True, header_color="00EBCF")
    
    dv_mode = DataValidation(type="list", formula1='"increment,decrement,overwrite"', allow_blank=False)
    ws.add_data_validation(dv_mode); dv_mode.add("D3:D1000")
    wb.save(output)
    return output.getvalue()

def process_quantities_import(df: pd.DataFrame) -> Dict:
    results = {"success": [], "errors": []}
    headers = get_headers()
    if not headers: return results
    
    quantities_payload = []
    for idx, row in df.iterrows():
        if row.isna().all() or str(row.iloc[0]).strip().startswith("💡"): continue
        try:
            sku = str(row.get('Product_SKU', '')).strip()
            branch_id = row.get('Branch_ID')
            quantity = int(safe_float(row.get('Quantity', 0)))
            mode = str(row.get('Mode', 'increment')).strip()
            
            if sku and pd.notna(branch_id):
                quantities_payload.append({"sku": sku, "branch_id": int(float(branch_id)), "quantity": quantity, "mode": mode})
        except Exception as e:
            results["errors"].append(f"❌ خطأ في قراءة الصف {idx+1}: {str(e)}")
            
    if quantities_payload:
        res = safe_api_request("POST", "https://api.salla.dev/admin/v2/products/quantities/bulk", headers, json={"products": quantities_payload})
        if res: results["success"].append(f"✅ تم تحديث كميات {len(quantities_payload)} سجل بنجاح!")
        else: results["errors"].append("❌ فشل إرسال طلب تحديث الكميات الجماعي.")
    else:
        results["errors"].append("⚠️ لم يتم العثور على بيانات صالحة في الملف.")
    return results

def update_product_promotions_secure(product_id: int, new_promo: str, new_sub: str, headers: dict) -> bool:
    """تحديث العناوين الترويجية بشكل آمن مع حماية السعر الأصلي للمنتج من التلاعب"""
    current_res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products/{product_id}", headers)
    if not current_res or not current_res.get('data'): return False
    
    p_data = current_res['data']
    price_val = get_flat_price(p_data.get('price', 0))
    sale_val = get_flat_price(p_data.get('sale_price', 0))
    regular_val = get_flat_price(p_data.get('regular_price', 0))
    
    base_price = regular_val if regular_val > 0 else price_val
    
    payload = {
        "name": p_data.get('name'),
        "price": base_price,
        "promotion_title": new_promo,
        "promotion_subtitle": new_sub
    }
    if sale_val > 0: payload['sale_price'] = sale_val
        
    res = safe_api_request("PUT", f"https://api.salla.dev/admin/v2/products/{product_id}", headers, json=payload)
    return res is not None

def update_product_tax_secure(product_id: int, with_tax: bool, tax_cause: str, headers: dict) -> bool:
    """تحديث حالة خضوع المنتج للضريبة وسبب عدم الخضوع"""
    current_res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products/{product_id}", headers)
    if not current_res or not current_res.get('data'): return False
    
    p_data = current_res['data']
    price_val = get_flat_price(p_data.get('price', 0))
    sale_val = get_flat_price(p_data.get('sale_price', 0))
    regular_val = get_flat_price(p_data.get('regular_price', 0))
    
    base_price = regular_val if regular_val > 0 else price_val
    
    payload = {
        "name": p_data.get('name'),
        "price": base_price,
        "with_tax": with_tax
    }
    if sale_val > 0: payload['sale_price'] = sale_val
    if not with_tax and tax_cause: payload["tax_exemption_cause"] = tax_cause
        
    res = safe_api_request("PUT", f"https://api.salla.dev/admin/v2/products/{product_id}", headers, json=payload)
    return res is not None

# ==========================================
# 📦 دوال المنتجات المتقدمة (الصور، الضرائب، والاستيراد)
# ==========================================

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
        from openpyxl.styles import numbers
        
        wb = Workbook()
        ws = wb.active
        ws.title = "قائمة المنتجات"
        
        # ✅ تعريف الأعمدة باللغة العربية
        columns = [
            "معرف المنتج", "SKU", "اسم المنتج", "نوع المنتج", "حالة المنتج",
            "السعر (SAR)", "السعر المخفض (SAR)", "بداية التخفيض", "نهاية التخفيض",
            "كمية غير محدودة", "خاضع للضريبة", "سبب عدم الخضوع",
            "العنوان الترويجي", "العنوان الفرعي"
        ]
        
        # ✅ تنسيق الرأس
        header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
        header_font = Font(name="Segoe UI", size=12, bold=True, color="FFFFFF")
        header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        thin_border = Border(
            left=Side(style='thin', color='CCCCCC'),
            right=Side(style='thin', color='CCCCCC'),
            top=Side(style='thin', color='CCCCCC'),
            bottom=Side(style='thin', color='CCCCCC')
        )
        
        # إضافة الرأس
        for col_idx, col_name in enumerate(columns, 1):
            cell = ws.cell(row=1, column=col_idx, value=col_name)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_alignment
            cell.border = thin_border
        
        # ✅ إضافة بيانات المنتجات الحالية إذا وجدت
        if products:
            for row_idx, product in enumerate(products, 2):
                # معرف المنتج
                ws.cell(row=row_idx, column=1, value=product.get('id', ''))
                # SKU
                ws.cell(row=row_idx, column=2, value=product.get('sku', ''))
                # اسم المنتج
                ws.cell(row=row_idx, column=3, value=product.get('name', ''))
                # نوع المنتج
                product_type = product.get('type', 'product')
                type_text = "منتج جاهز" if product_type == "product" else "مجموعة منتجات"
                ws.cell(row=row_idx, column=4, value=type_text)
                # حالة المنتج
                status = product.get('status', 'sale')
                status_text = "معروض" if status == "sale" else "مخفي"
                ws.cell(row=row_idx, column=5, value=status_text)
                # السعر
                price = get_flat_price(product.get('price', 0))
                ws.cell(row=row_idx, column=6, value=price)
                # السعر المخفض
                sale_price = get_flat_price(product.get('sale_price', 0))
                ws.cell(row=row_idx, column=7, value=sale_price if sale_price > 0 else '')
                # بداية التخفيض
                ws.cell(row=row_idx, column=8, value=product.get('sale_start', ''))
                # نهاية التخفيض
                ws.cell(row=row_idx, column=9, value=product.get('sale_end', ''))
                # كمية غير محدودة
                unlimited = "نعم" if product.get('unlimited_quantity', False) else "لا"
                ws.cell(row=row_idx, column=10, value=unlimited)
                # خاضع للضريبة
                with_tax = "نعم" if product.get('with_tax', True) else "لا"
                ws.cell(row=row_idx, column=11, value=with_tax)
                # سبب عدم الخضوع
                ws.cell(row=row_idx, column=12, value=product.get('tax_reason_code', ''))
                # العنوان الترويجي
                ws.cell(row=row_idx, column=13, value=product.get('promotion_title', ''))
                # العنوان الفرعي
                ws.cell(row=row_idx, column=14, value=product.get('promotion_subtitle', ''))
        else:
            # ✅ بيانات نموذجية للتعليمات
            sample_data = [
                ["", "SKU-001", "منتج جديد", "منتج جاهز", "معروض", 
                 100, 80, "2026-07-01", "2026-07-31", 
                 "لا", "نعم", "", "عرض خاص", "خصم 20%"],
                ["", "SKU-002", "منتج آخر", "مجموعة منتجات", "مخفي", 
                 200, "", "", "", 
                 "نعم", "لا", "الأدوية والمعدات الطبية", "", ""]
            ]
            for row_idx, row_data in enumerate(sample_data, 2):
                for col_idx, value in enumerate(row_data, 1):
                    ws.cell(row=row_idx, column=col_idx, value=value)
        
        # ✅ تنسيق البيانات
        data_font = Font(name="Segoe UI", size=11)
        data_alignment = Alignment(horizontal="right", vertical="center", wrap_text=True)
        
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.font = data_font
                cell.alignment = data_alignment
                cell.border = thin_border
        
        # ✅ ضبط عرض الأعمدة
        column_widths = {
            'A': 18,  # معرف المنتج
            'B': 18,  # SKU
            'C': 25,  # اسم المنتج
            'D': 18,  # نوع المنتج
            'E': 18,  # حالة المنتج
            'F': 16,  # السعر
            'G': 18,  # السعر المخفض
            'H': 20,  # بداية التخفيض
            'I': 20,  # نهاية التخفيض
            'J': 18,  # كمية غير محدودة
            'K': 18,  # خاضع للضريبة
            'L': 25,  # سبب عدم الخضوع
            'M': 22,  # العنوان الترويجي
            'N': 22   # العنوان الفرعي
        }
        
        for col, width in column_widths.items():
            ws.column_dimensions[col].width = width
        
        # ✅ إضافة الفلترة التلقائية
        ws.auto_filter.ref = f"A2:N{ws.max_row}"
        
        # ✅ إضافة القوائم المنسدلة
        
        # قائمة نوع المنتج
        dv_product_type = DataValidation(
            type="list",
            formula1='"منتج جاهز,مجموعة منتجات"',
            allow_blank=True,
            showErrorMessage=True,
            errorTitle="نوع منتج غير صحيح",
            error="الرجاء اختيار: منتج جاهز أو مجموعة منتجات"
        )
        ws.add_data_validation(dv_product_type)
        dv_product_type.add(f"D3:D{ws.max_row}")
        
        # قائمة حالة المنتج
        dv_status = DataValidation(
            type="list",
            formula1='"معروض,مخفي"',
            allow_blank=True,
            showErrorMessage=True,
            errorTitle="حالة غير صحيحة",
            error="الرجاء اختيار: معروض أو مخفي"
        )
        ws.add_data_validation(dv_status)
        dv_status.add(f"E3:E{ws.max_row}")
        
        # ✅ قائمة كمية غير محدودة
        dv_unlimited = DataValidation(
            type="list",
            formula1='"نعم,لا"',
            allow_blank=True,
            showErrorMessage=True,
            errorTitle="قيمة غير صحيحة",
            error="الرجاء اختيار: نعم أو لا"
        )
        ws.add_data_validation(dv_unlimited)
        dv_unlimited.add(f"J3:J{ws.max_row}")
        
        # ✅ قائمة خاضع للضريبة
        dv_tax = DataValidation(
            type="list",
            formula1='"نعم,لا"',
            allow_blank=True,
            showErrorMessage=True,
            errorTitle="قيمة غير صحيحة",
            error="الرجاء اختيار: نعم أو لا"
        )
        ws.add_data_validation(dv_tax)
        dv_tax.add(f"K3:K{ws.max_row}")
        
        # ✅ قائمة أسباب عدم الخضوع للضريبة
        tax_reasons = [
            "الخدمات المالية",
            "عقد تأمين على الحياة",
            "التوريدات العقارية المعفاة من الضريبة المضافة",
            "صادرات السلع من المملكة",
            "صادرات الخدمات من المملكة",
            "النقل الدولي للسلع",
            "النقل الدولي للركاب",
            "توريد وسائل النقل المؤهلة",
            "الأدوية والمعدات الطبية"
        ]
        dv_tax_reason = DataValidation(
            type="list",
            formula1=f'"{",".join(tax_reasons)}"',
            allow_blank=True,
            showErrorMessage=True,
            errorTitle="سبب غير صحيح",
            error="الرجاء اختيار سبب مناسب"
        )
        ws.add_data_validation(dv_tax_reason)
        dv_tax_reason.add(f"L3:L{ws.max_row}")
        
        # ✅ تنسيق خانات التاريخ
        date_format = numbers.FORMAT_DATE_DATETIME
        for row in range(3, ws.max_row + 1):
            for col in ['H', 'I']:  # بداية ونهاية التخفيض
                cell = ws[f"{col}{row}"]
                cell.number_format = date_format
        
        # ✅ إضافة تعليمات
        ws.insert_rows(1)
        ws.merge_cells('A1:N1')
        instructions_cell = ws.cell(row=1, column=1)
        instructions_cell.value = """
📋 تعليمات التعبئة:
- معرف المنتج: اتركه فارغاً لإضافة منتج جديد، أو أدخل المعرف لتحديث منتج موجود
- SKU: رمز المنتج الفريد (اختياري)
- نوع المنتج: اختر من القائمة المنسدلة
- حالة المنتج: اختر من القائمة المنسدلة
- كمية غير محدودة: اختر "نعم" إذا كان المنتج غير محدود الكمية
- خاضع للضريبة: اختر من القائمة المنسدلة
- سبب عدم الخضوع: اختر من القائمة المنسدلة (يظهر فقط عند اختيار "لا" في خاضع للضريبة)
- التواريخ: استخدم الصيغة YYYY-MM-DD
"""
        instructions_cell.font = Font(name="Segoe UI", size=11, bold=True, color="1F497D")
        instructions_cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.row_dimensions[1].height = 100
        
        # حفظ الملف
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output.getvalue()
        
    except Exception as e:
        st.error(f"⚠️ خطأ في إنشاء النموذج: {str(e)}")
        return b""

def attach_product_image_api(product_id: int, image_bytes: bytes=None, filename: str=None, image_url: str=None) -> bool:
    """رفع وإرفاق صورة للمنتج (إما كملف File أو كرابط URL)"""
    token = st.session_state.get('access_token', '')
    if not token: 
        st.error("⚠️ الرجاء إدخال مفتاح الربط أولاً")
        return False
    
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://api.salla.dev/admin/v2/products/{product_id}/images"
    
    try:
        if image_url:
            # ✅ إصلاح: إرسال الرابط كـ JSON
            headers["Content-Type"] = "application/json"
            payload = {"original": image_url}  # استخدام original بدلاً من photo
            response = requests.post(url, headers=headers, json=payload, timeout=30)
        elif image_bytes and filename:
            # ✅ رفع ملف
            files = {'photo': (filename, image_bytes, 'image/jpeg')}
            response = requests.post(url, headers=headers, files=files, timeout=30)
        else:
            st.error("⚠️ يجب توفير إما صورة أو رابط")
            return False
            
        if response.status_code >= 400:
            try: err = response.json()
            except: err = response.text
            st.error(f"⚠️ خطأ في إرفاق الصورة: {err}")
            return False
        return True
    except Exception as e:
        st.error(f"⚠️ خطأ اتصال: {str(e)}")
        return False
        
