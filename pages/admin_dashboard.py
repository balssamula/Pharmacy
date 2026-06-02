import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter
from utils.database import (
    get_latest_upload_summary, get_all_sessions, get_session_items, 
    lock_session, unlock_session, activate_session, delete_session,
    fetch_active_items, get_all_last_logins, get_completed_items,
    reopen_case_by_item_key, hide_item_from_pharmacy, unhide_item_from_pharmacy,
    lock_item, unlock_item
)
from utils.helpers import (
    is_cancelled_or_returned_status, is_pending_payment_status,
    get_tab_label, numeric_value
)
from utils.excel_processor import process_excel

def export_to_excel(dataframes_dict: dict) -> bytes:
    """تصدير البيانات إلى ملف Excel مع تنسيق احترافي"""
    output = BytesIO()
    
    tab_colors = {
        "الإضافات": "4472C4",
        "الإرجاعات": "ED7D31",
        "طلبات_بدون_فاتورة": "70AD47",
        "فواتير_بدون_طلب": "FFC000",
        "فواتير_بعد_آخر_طلب": "9B59B6",
        "بانتظار_الدفع": "3498DB",
        "ملغي_ومسترجع": "E74C3C",
        "تم_الانتهاء": "27AE60",
        "مقارنة_الجلسات": "2A5298"
    }
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name, df in dataframes_dict.items():
            if df is not None and not df.empty:
                df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
                
                worksheet = writer.sheets[sheet_name[:31]]
                
                header_fill = PatternFill(start_color=tab_colors.get(sheet_name, "2A5298"), 
                                         end_color=tab_colors.get(sheet_name, "2A5298"), 
                                         fill_type="solid")
                header_font = Font(color="FFFFFF", bold=True, size=12)
                
                for col in range(1, len(df.columns) + 1):
                    cell = worksheet.cell(row=1, column=col)
                    cell.fill = header_fill
                    cell.font = header_font
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                
                for col in range(1, len(df.columns) + 1):
                    column_letter = get_column_letter(col)
                    max_length = 0
                    for row in range(1, len(df) + 2):
                        cell_value = worksheet.cell(row=row, column=col).value
                        if cell_value:
                            max_length = max(max_length, len(str(cell_value)))
                    worksheet.column_dimensions[column_letter].width = min(max_length + 2, 40)
                
                for row in range(2, len(df) + 2):
                    for col in range(1, len(df.columns) + 1):
                        cell = worksheet.cell(row=row, column=col)
                        if row % 2 == 0:
                            cell.fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                        
                        if worksheet.cell(row=1, column=col).value == "الفرق":
                            diff_value = cell.value
                            if diff_value:
                                if diff_value > 0:
                                    cell.font = Font(color="008000", bold=True)
                                elif diff_value < 0:
                                    cell.font = Font(color="FF0000", bold=True)
            else:
                empty_df = pd.DataFrame({"ملاحظة": ["لا توجد بيانات في هذا التبويب"]})
                empty_df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
    
    output.seek(0)
    return output.getvalue()

def compare_sessions(session1_id: str, session2_id: str) -> pd.DataFrame:
    """مقارنة بين جلستين وإظهار الاختلافات"""
    import sqlite3
    from utils.database import DB_PATH
    
    conn = sqlite3.connect(DB_PATH)
    
    query1 = """
        SELECT order_number, invoice_number, sku, product_name, pharmacy_name,
               salla_qty, abc_qty, (salla_qty - abc_qty) as difference,
               case_type, order_status, abc_pharmacist_name
        FROM reconciliation_items 
        WHERE upload_batch_id = ? AND active = 1
    """
    df1 = pd.read_sql_query(query1, conn, params=(session1_id,))
    df1['session'] = 'الجلسة الأولى'
    
    df2 = pd.read_sql_query(query1, conn, params=(session2_id,))
    df2['session'] = 'الجلسة الثانية'
    
    conn.close()
    
    combined = pd.concat([df1, df2], ignore_index=True)
    
    combined['required_action'] = combined['difference'].apply(
        lambda x: 'إضافة' if x > 0 else ('إرجاع' if x < 0 else 'مطابق')
    )
    
    combined = combined.rename(columns={
        "order_number": "رقم الطلب",
        "invoice_number": "رقم الفاتورة",
        "sku": "SKU",
        "product_name": "المنتج",
        "pharmacy_name": "الفرع",
        "salla_qty": "كمية سلة",
        "abc_qty": "كمية ABC",
        "difference": "الفرق",
        "order_status": "حالة الطلب",
        "abc_pharmacist_name": "الصيدلي",
        "session": "الجلسة"
    })
    
    return combined[["رقم الطلب", "رقم الفاتورة", "الصيدلي", "SKU", "المنتج", 
                     "كمية سلة", "كمية ABC", "الفرق", "حالة الطلب", "required_action", "الفرع", "الجلسة"]]

def show():
    st.markdown("""
    <div class="hero">
        <h1>👑 لوحة التحكم الإدارية</h1>
        <p>إدارة الطلبات والفواتير - متابعة الإضافات والإرجاعات - إدارة الجلسات</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 5])
    with col1:
        if st.button("🔄 تحديث الصفحة", use_container_width=True):
            st.rerun()
    with col2:
        if st.button("📥 تصدير إلى Excel", use_container_width=True):
            st.session_state.show_export = True
    
    with st.expander("📂 رفع ملف الطلبات والفواتير", expanded=True):
        uploaded_file = st.file_uploader("اختر ملف Excel (يحتوي على شيتين: 'سلة' و 'abc')", type=["xlsx"])
        if uploaded_file:
            if st.button("🔄 معالجة الملف", use_container_width=True, type="primary"):
                with st.spinner("جاري معالجة الملف..."):
                    results, upload_batch_id = process_excel(uploaded_file, st.session_state.username)
                if results is not None:
                    st.success(f"✅ تمت المعالجة بنجاح! عدد الحالات: {len(results)}")
                    st.balloons()
                    st.rerun()
    
    latest = get_latest_upload_summary()
    if latest:
        batch_id, file_name, uploaded_by, uploaded_at, total_cases, additions, returns, orphan_salla, orphan_abc, post_cutoff, is_locked, session_name = latest
        lock_status = "🔒 مقفلة" if is_locked else "🔓 مفتوحة"
        st.markdown(f"""
        <div class="note-card">
            <strong>📋 الجلسة النشطة:</strong> {session_name or 'غير مسماة'} &nbsp; | &nbsp;
            <strong>الملف:</strong> {file_name} &nbsp; | &nbsp;
            <strong>بواسطة:</strong> {uploaded_by} &nbsp; | &nbsp;
            <strong>التاريخ:</strong> {uploaded_at[:16] if uploaded_at else ''} &nbsp; | &nbsp;
            <strong>الحالة:</strong> {lock_status}
        </div>
        """, unsafe_allow_html=True)
    
    # إدارة الجلسات السابقة
    st.markdown('<div class="section-title">📋 إدارة الجلسات السابقة</div>', unsafe_allow_html=True)
    sessions_df = get_all_sessions()
    if not sessions_df.empty:
        for _, session in sessions_df.iterrows():
            col1, col2, col3, col4, col5 = st.columns([2, 2, 1.5, 1.5, 2])
            session_name_val = session.get('session_name', session['upload_batch_id'][:8])
            with col1:
                st.markdown(f'<div class="session-card"><strong>📅 {session_name_val}</strong><br><small>{session["file_name"][:35]}</small></div>', unsafe_allow_html=True)
            with col2:
                is_active = session.get('is_active', 0)
                active_badge = "✅ نشطة" if is_active else "⏸ غير نشطة"
                st.markdown(f'<div class="session-card"><small>👤 {session["uploaded_by"]}<br>📅 {session["uploaded_at"][:16]}<br>{active_badge}</small></div>', unsafe_allow_html=True)
            with col3:
                st.markdown(f'<div class="session-card"><small>📊 {int(session.get("total_cases", 0))} حالة<br>➕ {int(session.get("total_additions", 0))}<br>➖ {int(session.get("total_returns", 0))}</small></div>', unsafe_allow_html=True)
            with col4:
                is_locked = session.get('is_locked', 0)
                lock_text = "🔒 مقفلة" if is_locked else "🔓 مفتوحة"
                st.markdown(f'<div class="session-card" style="text-align:center;"><small>{lock_text}</small></div>', unsafe_allow_html=True)
            with col5:
                btn1, btn2, btn3, btn4 = st.columns(4)
                with btn1:
                    if not is_locked:
                        if st.button(f"🔒", key=f"lock_{session['upload_batch_id']}"):
                            lock_session(session['upload_batch_id'], st.session_state.username)
                            st.rerun()
                    else:
                        if st.button(f"🔓", key=f"unlock_{session['upload_batch_id']}"):
                            unlock_session(session['upload_batch_id'])
                            st.rerun()
                with btn2:
                    if not is_active:
                        if st.button(f"⭐", key=f"activate_{session['upload_batch_id']}"):
                            activate_session(session['upload_batch_id'])
                            st.rerun()
                with btn3:
                    if st.button(f"👁️", key=f"view_{session['upload_batch_id']}"):
                        st.session_state.view_session_id = session['upload_batch_id']
                        st.rerun()
                with btn4:
                    if st.button(f"🗑️", key=f"delete_{session['upload_batch_id']}"):
                        delete_session(session['upload_batch_id'])
                        st.rerun()
        st.markdown("---")
    
    # مقارنة الجلسات
    st.markdown('<div class="section-title">🔄 مقارنة الجلسات</div>', unsafe_allow_html=True)
    
    sessions_list = get_all_sessions()
    if not sessions_list.empty:
        session_options = {f"{row['session_name']} ({row['uploaded_at'][:16]})": row['upload_batch_id'] 
                          for _, row in sessions_list.iterrows()}
        
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            session1 = st.selectbox("اختر الجلسة الأولى", list(session_options.keys()), key="session1")
        with col2:
            session2 = st.selectbox("اختر الجلسة الثانية", list(session_options.keys()), key="session2")
        with col3:
            if st.button("📊 مقارنة", use_container_width=True):
                with st.spinner("جاري المقارنة..."):
                    comparison_df = compare_sessions(session_options[session1], session_options[session2])
                    st.session_state.comparison_result = comparison_df
                    st.success(f"✅ تمت المقارنة بنجاح! عدد السجلات: {len(comparison_df)}")
        
        if st.session_state.get('comparison_result') is not None:
            st.dataframe(st.session_state.comparison_result, use_container_width=True)
            
            export_data = {"مقارنة_الجلسات": st.session_state.comparison_result}
            excel_data = export_to_excel(export_data)
            st.download_button(
                "📥 تحميل تقرير المقارنة",
                data=excel_data,
                file_name=f"session_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
    
    if st.session_state.get('view_session_id'):
        st.markdown(f'<div class="section-title">📄 عرض الجلسة المحددة</div>', unsafe_allow_html=True)
        session_items = get_session_items(st.session_state.view_session_id)
        if not session_items.empty:
            st.dataframe(session_items, use_container_width=True)
        if st.button("إغلاق العرض", use_container_width=True):
            del st.session_state.view_session_id
            st.rerun()
    
    df = fetch_active_items(include_hidden=True)
    if df.empty:
        st.info("📂 لا توجد بيانات فعالة بعد. ارفع ملف Excel من الأعلى لبدء التحليل.")
        return
    
    # إحصائيات سريعة
    active_mask = ~df["order_status"].apply(is_cancelled_or_returned_status)
    active_df = df[active_mask]
    
    col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    with col1:
        st.metric("📊 إجمالي الحالات", len(active_df))
    with col2:
        st.metric("➕ إضافات", len(active_df[active_df["case_type"] == "addition"]))
    with col3:
        st.metric("➖ إرجاعات", len(active_df[active_df["case_type"] == "return"]))
    with col4:
        st.metric("📦 طلبات بدون فاتورة", len(active_df[active_df["case_type"] == "orphan_salla"]))
    with col5:
        st.metric("🧾 فواتير بدون طلب", len(active_df[active_df["case_type"] == "orphan_abc"]))
    with col6:
        st.metric("⏰ فواتير بعد آخر طلب", len(active_df[active_df["case_type"] == "post_cutoff_abc"]))
    with col7:
        st.metric("✅ تم إنجازها", len(df[df["status"] == "تم"]))
    
    # فلاتر
    col1, col2, col3 = st.columns(3)
    with col1:
        branch_options = ["الكل"] + sorted(df["pharmacy_name"].dropna().astype(str).unique().tolist())
        selected_branch = st.selectbox("🏥 فلتر الفرع", branch_options)
    with col2:
        status_filter = st.selectbox("📌 فلتر حالة الإجراء", ["الكل", "قيد المتابعة", "تم"])
    with col3:
        order_status_options = ["الكل", "تم التوصيل", "ملغي", "مسترجع", "بانتظار الدفع", "تم الاستلام من فرع"]
        selected_order_status = st.selectbox("📋 فلتر حالة الطلب", order_status_options)
    
    filtered_df = df.copy()
    if selected_branch != "الكل":
        filtered_df = filtered_df[filtered_df["pharmacy_name"] == selected_branch]
    if status_filter != "الكل":
        filtered_df = filtered_df[filtered_df["status"] == ("تم" if status_filter == "تم" else "قيد المتابعة")]
    if selected_order_status != "الكل":
        if selected_order_status == "تم الاستلام من فرع":
            filtered_df = filtered_df[filtered_df["order_status"].str.contains("تم الاستلام من فرع", na=False)]
        else:
            filtered_df = filtered_df[filtered_df["order_status"] == selected_order_status]
    
    # فصل البيانات
    active_mask_filtered = ~filtered_df["order_status"].apply(is_cancelled_or_returned_status)
    payment_mask = filtered_df["order_status"].apply(is_pending_payment_status)
    cancelled_mask = filtered_df["order_status"].apply(is_cancelled_or_returned_status)
    
    additions_df = filtered_df[(filtered_df["case_type"] == "addition") & active_mask_filtered]
    returns_df = filtered_df[(filtered_df["case_type"] == "return") & active_mask_filtered]
    orphan_salla_df = filtered_df[(filtered_df["case_type"] == "orphan_salla") & active_mask_filtered]
    orphan_abc_df = filtered_df[(filtered_df["case_type"] == "orphan_abc") & active_mask_filtered]
    post_cutoff_df = filtered_df[(filtered_df["case_type"] == "post_cutoff_abc") & active_mask_filtered]
    payment_df = filtered_df[payment_mask]
    cancelled_df = filtered_df[cancelled_mask]
    
    completed_df = get_completed_items()
    if selected_branch != "الكل":
        completed_df = completed_df[completed_df["pharmacy_name"] == selected_branch]
    
    # تصدير Excel
    if st.session_state.get('show_export', False):
        export_data = {
            "الإضافات": additions_df,
            "الإرجاعات": returns_df,
            "طلبات_بدون_فاتورة": orphan_salla_df,
            "فواتير_بدون_طلب": orphan_abc_df,
            "فواتير_بعد_آخر_طلب": post_cutoff_df,
            "بانتظار_الدفع": payment_df,
            "ملغي_ومسترجع": cancelled_df,
            "تم_الانتهاء": completed_df
        }
        excel_data = export_to_excel(export_data)
        st.download_button(
            "📥 تحميل التقرير",
            data=excel_data,
            file_name=f"balsam_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        st.session_state.show_export = False
    
    # التبويبات مع تلوين
    st.markdown("""
    <style>
    button[data-baseweb="tab"]:nth-child(1) { background-color: #4472C4; color: white; border-radius: 10px 10px 0 0; }
    button[data-baseweb="tab"]:nth-child(2) { background-color: #ED7D31; color: white; border-radius: 10px 10px 0 0; }
    button[data-baseweb="tab"]:nth-child(3) { background-color: #70AD47; color: white; border-radius: 10px 10px 0 0; }
    button[data-baseweb="tab"]:nth-child(4) { background-color: #FFC000; color: white; border-radius: 10px 10px 0 0; }
    button[data-baseweb="tab"][aria-selected="true"] { opacity: 1; }
    button[data-baseweb="tab"][aria-selected="false"] { opacity: 0.8; }
    div[data-testid="stDataFrame"] { direction: rtl; }
    </style>
    """, unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        get_tab_label("📈 الإضافات", len(additions_df[additions_df["status"] == "تم"]), len(additions_df)),
        get_tab_label("📉 الإرجاعات", len(returns_df[returns_df["status"] == "تم"]), len(returns_df)),
        get_tab_label("📦 طلبات بدون فاتورة", len(orphan_salla_df[orphan_salla_df["status"] == "تم"]), len(orphan_salla_df)),
        get_tab_label("🧾 فواتير بدون طلب", len(orphan_abc_df[orphan_abc_df["status"] == "تم"]), len(orphan_abc_df)),
        get_tab_label("⏰ فواتير بعد آخر طلب", len(post_cutoff_df[post_cutoff_df["status"] == "تم"]), len(post_cutoff_df)),
        get_tab_label("💰 بانتظار الدفع", 0, len(payment_df)),
        get_tab_label("⚠️ ملغي/مسترجع", 0, len(cancelled_df)),
        get_tab_label("✅ تم الانتهاء", len(completed_df), len(completed_df))
    ])
    
    # دالة لعرض جدول مع أزرار رموز في النهاية
    def render_dataframe_with_buttons(df, title=""):
        if df.empty:
            st.success("لا توجد بيانات في هذا القسم.")
            return
        
        # تجهيز البيانات للعرض
        display_df = df.copy()
        display_df = display_df.rename(columns={
            "order_number": "رقم الطلب",
            "invoice_number": "رقم الفاتورة",
            "sku": "SKU",
            "product_name": "المنتج",
            "pharmacy_name": "الفرع",
            "salla_qty": "كمية سلة",
            "abc_qty": "كمية ABC",
            "difference": "الفرق",
            "order_status": "حالة الطلب",
            "case_label": "نوع الحالة",
            "status": "الحالة"
        })
        
        # إضافة عمود الأزرار
        display_df["الإجراءات"] = ""
        
        # عرض الجدول
        st.dataframe(
            display_df[["رقم الطلب", "رقم الفاتورة", "SKU", "المنتج", "كمية سلة", "كمية ABC", "الفرق", "حالة الطلب", "الفرع", "نوع الحالة", "الحالة", "الإجراءات"]],
            use_container_width=True,
            height=400
        )
        
        # عرض الأزرار أسفل الجدول (لكل صف على حدة)
        st.markdown("### 🔧 إجراءات الصفوف")
        
        for idx, row in df.iterrows():
            col1, col2, col3, col4, col5, col6 = st.columns([2, 1, 1, 1, 1, 4])
            
            with col1:
                st.write(f"طلب: {row['order_number']} | SKU: {row['sku']}")
            
            with col2:
                is_hidden = row.get('hidden_from_pharmacy', 0) == 1
                if is_hidden:
                    st.button("👁️", key=f"unhide_{idx}", help="إظهار للصيدلية", use_container_width=True)
                else:
                    st.button("🙈", key=f"hide_{idx}", help="إخفاء من الصيدلية", use_container_width=True)
            
            with col3:
                is_locked = row.get('is_item_locked', 0) == 1
                if is_locked:
                    st.button("🔓", key=f"unlock_{idx}", help="فتح التعديل", use_container_width=True)
                else:
                    st.button("🔒", key=f"lock_{idx}", help="قفل التعديل", use_container_width=True)
            
            with col4:
                if row['status'] == "تم":
                    st.button("🔄", key=f"reopen_{idx}", help="إعادة فتح", use_container_width=True)
            
            with col5:
                note_key = f"note_{idx}"
                note_value = st.text_input("", key=note_key, placeholder="ملحوظة", label_visibility="collapsed")
                st.button("💾", key=f"save_{idx}", help="حفظ الملحوظة", use_container_width=True)
            
            st.markdown("---")
    
    with tab1:
        render_dataframe_with_buttons(additions_df)
    with tab2:
        render_dataframe_with_buttons(returns_df)
    with tab3:
        render_dataframe_with_buttons(orphan_salla_df)
    with tab4:
        render_dataframe_with_buttons(orphan_abc_df)
    with tab5:
        render_dataframe_with_buttons(post_cutoff_df)
    with tab6:
        render_dataframe_with_buttons(payment_df)
    with tab7:
        render_dataframe_with_buttons(cancelled_df)
    with tab8:
        if not completed_df.empty:
            render_dataframe_with_buttons(completed_df)
        else:
            st.info("لا توجد طلبات مكتملة")
    
    # آخر دخول للصيدليات
    st.markdown('<div class="section-title">👥 آخر دخول للصيدليات</div>', unsafe_allow_html=True)
    last_logins = get_all_last_logins()
    if not last_logins.empty:
        cols = st.columns(4)
        for idx, (_, row) in enumerate(last_logins.head(8).iterrows()):
            with cols[idx % 4]:
                st.markdown(f"""
                <div class="note-card">
                    <strong>🏥 {row['pharmacy_name'][-10:]}</strong><br>
                    <span>👤 {row['pharmacist_name'] or 'غير مسجل'}</span><br>
                    <span>📅 {row['last_login'][:16] if row['last_login'] else 'لم يدخل'}</span>
                </div>
                """, unsafe_allow_html=True)
