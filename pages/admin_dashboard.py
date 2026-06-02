import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
from utils.database import (
    get_latest_upload_summary, get_all_sessions, get_session_items, 
    lock_session, unlock_session, activate_session, fetch_active_items,
    get_all_last_logins, get_completed_items
)
from utils.helpers import is_cancelled_or_returned_status, is_pending_payment_status
from utils.ui_components import render_metrics, render_completed_table, get_tab_label
from utils.excel_processor import process_excel

def show():
    st.markdown(
        """
        <div class="hero">
            <h1>لوحة التحكم الإدارية</h1>
            <p>مطابقة أكثر دقة بين سلة و ABC مع فصل الحالات الفعلية عن السطور غير المربوطة وحفظ الإنجاز بين كل رفعة وأخرى.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    latest = get_latest_upload_summary()
    if latest:
        batch_id, file_name, uploaded_by, uploaded_at, total_cases, additions, returns, orphan_salla, orphan_abc, branch_mismatch, special_review, is_locked, session_name = latest
        lock_status = "🔒 مقفلة" if is_locked else "🔓 مفتوحة"
        st.markdown(
            f"""
            <div class="note-card">
                <strong>الجلسة النشطة:</strong> {session_name or 'غير مسماة'} &nbsp; | &nbsp;
                <strong>الملف:</strong> {file_name} &nbsp; | &nbsp;
                <strong>بواسطة:</strong> {uploaded_by} &nbsp; | &nbsp;
                <strong>التاريخ:</strong> {uploaded_at[:16] if uploaded_at else ''} &nbsp; | &nbsp;
                <strong>الحالة:</strong> {lock_status}
            </div>
            """,
            unsafe_allow_html=True,
        )

    with st.expander("رفع ملف الطلبات والفواتير", expanded=True):
        uploaded_file = st.file_uploader("اختر ملف Excel", type=["xlsx"], key="reconciliation")
        if uploaded_file and st.button("معالجة الملف و ترحيل الحالات", use_container_width=True):
            with st.spinner("جاري قراءة الملف وتصنيف الحالات بدقة..."):
                results, upload_batch_id = process_excel(uploaded_file, st.session_state.username)
            st.success(f"✅ تمت المعالجة بنجاح. تم إنشاء جلسة جديدة: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            st.rerun()

    st.markdown('<div class="section-title">📋 إدارة الجلسات السابقة</div>', unsafe_allow_html=True)
    
    sessions_df = get_all_sessions()
    if not sessions_df.empty:
        for _, session in sessions_df.iterrows():
            col1, col2, col3, col4, col5 = st.columns([2.5, 2.5, 2, 1.5, 2])
            
            session_name_val = session.get('session_name', '')
            if not session_name_val or pd.isna(session_name_val):
                session_name_val = session['upload_batch_id'][:8]
            
            with col1:
                st.markdown(f"""
                <div class="session-card">
                    <strong>📅 {session_name_val}</strong><br>
                    <small>{session['file_name'][:35] if session['file_name'] else ''}</small>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                is_active = session.get('is_active', 0)
                active_badge = "✅ نشطة" if is_active else "⏸ غير نشطة"
                st.markdown(f"""
                <div class="session-card">
                    <small>👤 {session['uploaded_by']}<br>
                    📅 {session['uploaded_at'][:16] if session['uploaded_at'] else ''}<br>
                    {active_badge}</small>
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                st.markdown(f"""
                <div class="session-card">
                    <small>📊 {int(session.get('total_cases', 0))} حالة<br>
                    ➕ {int(session.get('total_additions', 0))} | ➖ {int(session.get('total_returns', 0))}</small>
                </div>
                """, unsafe_allow_html=True)
            
            with col4:
                is_locked = session.get('is_locked', 0)
                lock_class = "lock-closed" if is_locked else "lock-open"
                lock_text = "مقفلة" if is_locked else "مفتوحة"
                st.markdown(f"""
                <div class="session-card" style="text-align: center;">
                    <span class="lock-badge {lock_class}">🔒 {lock_text}</span>
                    <br><small>{session.get('locked_by', '')[:15] if session.get('locked_by') else ''}</small>
                </div>
                """, unsafe_allow_html=True)
            
            with col5:
                btn1, btn2, btn3 = st.columns(3)
                with btn1:
                    if not is_locked:
                        if st.button(f"🔒 قفل", key=f"lock_{session['upload_batch_id']}", use_container_width=True):
                            lock_session(session['upload_batch_id'], st.session_state.username)
                            st.rerun()
                    else:
                        if st.button(f"🔓 فتح", key=f"unlock_{session['upload_batch_id']}", use_container_width=True):
                            unlock_session(session['upload_batch_id'])
                            st.rerun()
                
                with btn2:
                    if not is_active:
                        if st.button(f"⭐ تفعيل", key=f"activate_{session['upload_batch_id']}", use_container_width=True):
                            activate_session(session['upload_batch_id'])
                            st.rerun()
                
                with btn3:
                    if st.button(f"👁️ عرض", key=f"view_{session['upload_batch_id']}", use_container_width=True):
                        st.session_state.view_session_id = session['upload_batch_id']
                        st.rerun()
        
        st.markdown("---")
    
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
        st.info("لا توجد بيانات فعالة بعد. ارفع الملف من الأعلى لبدء التحليل.")
        return

    render_metrics(df)
    
    # فلتر
    col1, col2 = st.columns(2)
    with col1:
        branch_options = ["الكل"] + sorted(df["pharmacy_name"].dropna().astype(str).unique().tolist())
        selected_branch = st.selectbox("فلتر الفرع", branch_options)
    with col2:
        performer_values = sorted({value for value in df["performed_by"].fillna("").astype(str).tolist() if value.strip()})
        selected_performer = st.selectbox("فلتر المنفذ", ["الكل"] + performer_values)

    filtered_df = df.copy()
    if selected_branch != "الكل":
        filtered_df = filtered_df[filtered_df["pharmacy_name"] == selected_branch]
    if selected_performer != "الكل":
        filtered_df = filtered_df[filtered_df["performed_by"] == selected_performer]

    st.markdown('<div class="section-title">👥 آخر دخول للصيدليات</div>', unsafe_allow_html=True)
    last_logins = get_all_last_logins()
    if not last_logins.empty:
        cols = st.columns(4)
        for idx, (_, row) in enumerate(last_logins.head(8).iterrows()):
            with cols[idx % 4]:
                st.markdown(
                    f"""
                    <div class="note-card">
                        <strong>{row['pharmacy_name'][-10:]}</strong><br>
                        <span style="color:#58707a;">{row['pharmacist_name'] or 'غير مسجل'}</span><br>
                        <span style="color:#58707a;">{row['last_login'][:16] if row['last_login'] else 'لم يدخل بعد'}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    # إعداد التبويبات مع الأعداد
    total_active = len(filtered_df)
    additions_count = len(filtered_df[filtered_df["case_type"] == "addition"])
    returns_count = len(filtered_df[filtered_df["case_type"] == "return"])
    orphan_salla_count = len(filtered_df[filtered_df["case_type"] == "orphan_salla"])
    orphan_abc_count = len(filtered_df[filtered_df["case_type"] == "orphan_abc"])
    post_cutoff_count = len(filtered_df[filtered_df["case_type"] == "post_cutoff_abc"])
    payment_pending_count = len(filtered_df[filtered_df["order_status"].apply(is_pending_payment_status)])
    cancelled_count = len(filtered_df[filtered_df["order_status"].apply(is_cancelled_or_returned_status)])
    
    completed_df = get_completed_items()
    if selected_branch != "الكل":
        completed_df = completed_df[completed_df["pharmacy_name"] == selected_branch]
    completed_count = len(completed_df)

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        get_tab_label("الإضافات", additions_count, total_active),
        get_tab_label("الإرجاعات", returns_count, total_active),
        get_tab_label("طلبات بدون فاتورة", orphan_salla_count, total_active),
        get_tab_label("فواتير بدون طلب", orphan_abc_count, total_active),
        get_tab_label("فواتير بعد آخر طلب", post_cutoff_count, total_active),
        get_tab_label("بانتظار الدفع", payment_pending_count, total_active),
        get_tab_label("الملغي/المسترجع", cancelled_count, total_active),
        get_tab_label("✅ تم الانتهاء", completed_count, completed_count)
    ])

    with tab1:
        additions = filtered_df[filtered_df["case_type"] == "addition"]
        st.dataframe(additions, use_container_width=True)
    with tab2:
        returns = filtered_df[filtered_df["case_type"] == "return"]
        st.dataframe(returns, use_container_width=True)
    with tab3:
        orphan_salla = filtered_df[filtered_df["case_type"] == "orphan_salla"]
        st.dataframe(orphan_salla, use_container_width=True)
    with tab4:
        orphan_abc = filtered_df[filtered_df["case_type"] == "orphan_abc"]
        st.dataframe(orphan_abc, use_container_width=True)
    with tab5:
        post_cutoff = filtered_df[filtered_df["case_type"] == "post_cutoff_abc"]
        st.dataframe(post_cutoff, use_container_width=True)
    with tab6:
        payment_pending = filtered_df[filtered_df["order_status"].apply(is_pending_payment_status)]
        st.dataframe(payment_pending, use_container_width=True)
    with tab7:
        cancelled = filtered_df[filtered_df["order_status"].apply(is_cancelled_or_returned_status)]
        st.dataframe(cancelled, use_container_width=True)
    with tab8:
        render_completed_table(completed_df, is_admin=True, total_count=completed_count)