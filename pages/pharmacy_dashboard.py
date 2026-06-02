import streamlit as st
from utils.database import fetch_active_items, get_completed_items
from utils.helpers import is_cancelled_or_returned_status, is_pending_payment_status, get_branch_number
from utils.ui_components import render_metrics, render_case_cards, render_completed_table, get_tab_label
from utils.excel_processor import process_excel

def show():
    pharmacy_name = st.session_state.username
    pharmacist_name = st.session_state.pharmacist_name or ""
    branch_number = get_branch_number(pharmacy_name)

    st.markdown(
        f"""
        <div class="hero">
            <h1>{pharmacy_name}</h1>
            <p>فرع رقم {branch_number} | الصيدلي: {pharmacist_name}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not pharmacist_name:
        st.warning("⚠️ الرجاء إدخال اسم الصيدلي من القائمة الجانبية أولاً")
        return

    if st.button("🔄 تحديث الصفحة", use_container_width=True):
        st.rerun()

    df = fetch_active_items(pharmacy_name, include_hidden=False)
    
    if df.empty:
        st.info("لا توجد حالات نشطة لهذا الفرع حاليًا.")
        completed_df = get_completed_items(pharmacy_name)
        if not completed_df.empty:
            st.markdown("---")
            st.markdown('<div class="section-title">✅ الطلبات المكتملة</div>', unsafe_allow_html=True)
            render_completed_table(completed_df, is_admin=False)
        return

    is_locked = df['is_locked'].iloc[0] == 1 if not df.empty else False
    
    if is_locked:
        st.warning("🔒 هذه الجلسة مقفلة ولا يمكن إجراء تعديلات عليها.")
        allow_actions = False
    else:
        allow_actions = True

    render_metrics(df)

    active_non_cancelled = ~df["order_status"].apply(is_cancelled_or_returned_status)
    active_non_payment = ~df["order_status"].apply(is_pending_payment_status)
    active_operational = active_non_cancelled & active_non_payment
    
    additions_df = df[(df["case_type"] == "addition") & active_operational].copy()
    returns_df = df[(df["case_type"] == "return") & active_operational].copy()
    orphan_salla_df = df[(df["case_type"] == "orphan_salla") & active_operational].copy()
    orphan_abc_df = df[(df["case_type"] == "orphan_abc") & active_operational].copy()
    post_cutoff_df = df[df["case_type"] == "post_cutoff_abc"].copy()
    cancelled_df = df[df["order_status"].apply(is_cancelled_or_returned_status)].copy()
    payment_pending_df = df[df["order_status"].apply(is_pending_payment_status)].copy()
    
    completed_df = get_completed_items(pharmacy_name)
    
    total_items = len(additions_df) + len(returns_df) + len(orphan_salla_df) + len(orphan_abc_df)
    
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        get_tab_label("الإضافات", len(additions_df), total_items),
        get_tab_label("الإرجاعات", len(returns_df), total_items),
        get_tab_label("طلبات بدون فاتورة", len(orphan_salla_df), total_items),
        get_tab_label("فواتير بدون طلب", len(orphan_abc_df), total_items),
        get_tab_label("فواتير بعد آخر طلب", len(post_cutoff_df), total_items),
        get_tab_label("بانتظار الدفع", len(payment_pending_df), total_items),
        get_tab_label("الملغي/المسترجع", len(cancelled_df), total_items),
        get_tab_label("✅ تم الانتهاء", len(completed_df), len(completed_df))
    ])

    with tab1:
        render_case_cards(additions_df, allow_actions, pharmacist_name, pharmacy_name, is_admin=False)
    with tab2:
        render_case_cards(returns_df, allow_actions, pharmacist_name, pharmacy_name, is_admin=False)
    with tab3:
        render_case_cards(orphan_salla_df, allow_actions, pharmacist_name, pharmacy_name, is_admin=False)
    with tab4:
        render_case_cards(orphan_abc_df, allow_actions, pharmacist_name, pharmacy_name, is_admin=False)
    with tab5:
        render_case_cards(post_cutoff_df, False, pharmacist_name, pharmacy_name, is_admin=False)
    with tab6:
        render_case_cards(payment_pending_df, False, pharmacist_name, pharmacy_name, is_admin=False)
    with tab7:
        render_case_cards(cancelled_df, False, pharmacist_name, pharmacy_name, is_admin=False)
    with tab8:
        render_completed_table(completed_df, is_admin=False, total_count=len(completed_df))