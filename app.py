def generate_salla_template():
    buffer = io.BytesIO()
    
    # 1. بناء البيانات الأساسية للنموذج
    columns = [
        "Action", "Offer_ID", "Offer_Name", "Offer_Type", "Applied_Channel", 
        "With_Coupon", "Start_Date", "Expiry_Date", "Buy_Type", "Buy_Quantity", 
        "Buy_Products_IDs", "Get_Type", "Get_Quantity", "Discount_Type", 
        "Discount_Amount", "Get_Products_IDs", "Offer_Message"
    ]
    
    # أسطر استرشادية كمثال للمستخدم
    sample_data = [
        ["create", None, "عرض قطعتين والثالثة مجاناً", "buy_x_get_y", "browser_and_application", "نعم", "2026-06-21", "2026-07-21", "product", 2, "1298176905", "product", 1, "free-product", 0, "1444615766", "اشتري قطعتين واحصل على الثالثة مجاناً"],
        ["update", 374680268, "تعديل العرض الحالي", "percentage", "browser_and_application", "لا", "2026-06-21", "2026-08-15", "product", 1, "1298176905", "product", 1, "percentage", 50, "1444615766", "خصم 50% على المنتج الثاني"]
    ]
    
    df = pd.DataFrame(sample_data, columns=columns)
    
    # 2. الكتابة والتنسيق باستخدام openpyxl
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='إدارة العروض الجماعية')
        
        workbook = writer.book
        worksheet = writer.sheets['إدارة العروض الجماعية']
        
        # استيراد أدوات التنسيق والتحقق من البيانات
        from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
        from openpyxl.worksheet.datavalidation import DataValidation
        
        # تنسيق صف العناوين (الأزرق الداكن والخط الأبيض العريض)
        header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        center_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        
        thin_side = Side(border_style="thin", color="D9D9D9")
        thin_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
        
        # تطبيق التنسيق على الصف الأول
        worksheet.row_dimensions[1].height = 28
        for cell in worksheet[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_alignment
            cell.border = thin_border
            
        # تنسيق صفوف البيانات وتوسيع الأعمدة تلقائياً
        for row in worksheet.iter_rows(min_row=2, max_row=100):
            for cell in row:
                cell.font = Font(name="Segoe UI", size=10)
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = thin_border
                
        for col in worksheet.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = col[0].column_letter
            worksheet.column_dimensions[col_letter].width = max(max_len + 3, 15)
            
        # 3. إضافة القوائم المنسدلة (Dropdown) لمنع أخطاء الإدخال
        dv_action = DataValidation(type="list", formula1='"create,update,active,inactive,delete"', allow_blank=True)
        dv_type = DataValidation(type="list", formula1='"buy_x_get_y,percentage,fixed_amount,discounts_table,special_price,cart_offer,tiered_offer"', allow_blank=True)
        dv_channel = DataValidation(type="list", formula1='"browser,browser_and_application"', allow_blank=True)
        dv_coupon = DataValidation(type="list", formula1='"نعم,لا"', allow_blank=True)
        
        # ربط القوائم المنسدلة بالأعمدة المخصصة لها حتى الصف 100
        worksheet.add_data_validation(dv_action)
        dv_action.add("A2:A100") # عمود الإجراء
        
        worksheet.add_data_validation(dv_type)
        dv_type.add("D2:D100")   # عمود نوع العرض
        
        worksheet.add_data_validation(dv_channel)
        dv_channel.add("E2:E100") # عمود القناة المطبقة
        
        worksheet.add_data_validation(dv_coupon)
        dv_coupon.add("F2:F100")   # عمود التطبيق مع كوبون
        
    return buffer.getvalue()
