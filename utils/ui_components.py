import streamlit as st
import pandas as pd
from utils.helpers import status_pill, case_pill, status_alert_pill, payment_alert_pill, numeric_value

def render_metrics(df: pd.DataFrame):
    total = len(df)
    additions = int((df["case_type"] == "addition").sum())
    returns = int((df["case_type"] == "return").sum())
    orphan_salla = int((df["case_type"] == "orphan_salla").sum())
    orphan_abc = int((df["case_type"] == "orphan_abc").sum())
    completed = int((df["status"] == "تم").sum()) # تعديل اللبس النصي القديم
    
    st.markdown(f"""
    <style>
    .dashboard-container {{
        display: flex; flex-wrap: wrap; gap: 15px; justify-content: space-between; margin-bottom: 25px;
    }}
    .creative-card {{
        flex: 1; min-width: 160px; background: rgba(255, 255, 255, 0.9);
        border-radius: 20px; padding: 20px; text-align: center;
        box-shadow: 0 10px 20px rgba(31, 122, 140, 0.05);
        border: 1px solid rgba(31, 122, 140, 0.1); transition: all 0.3s ease;
        border-bottom: 4px solid #6c757d;
    }}
    .creative-card:hover {{
        transform: translateY(-5px); box-shadow: 0 15px 30px rgba(31, 122, 140, 0.15);
    }}
    .card-additions {{ border-bottom-color: #4472C4; }}
    .card-returns {{ border-bottom-color: #ED7D31; }}
    .card-salla {{ border-bottom-color: #70AD47; }}
    .card-abc {{ border-bottom-color: #FFC000; }}
    .card-done {{ border-bottom-color: #28a745; }}
    </style>
    
    <div class="dashboard-container">
        <div class="creative-card">
            <div style="font-size: 0.9rem; color: #64748b; font-weight: 500;">📊 إجمالي الحالات</div>
            <div style="font-size: 2.2rem; font-weight: 800; color: #1e293b; margin-top: 5px;">{total}</div>
        </div>
        <div class="creative-card card-additions">
            <div style="font-size: 0.9rem; color: #4472C4; font-weight: bold;">➕ الإضافات</div>
            <div style="font-size: 2.2rem; font-weight: 800; color: #4472C4; margin-top: 5px;">{additions}</div>
        </div>
        <div class="creative-card card-returns">
            <div style="font-size: 0.9rem; color: #ED7D31; font-weight: bold;">🔄 الإرجاعات</div>
            <div style="font-size: 2.2rem; font-weight: 800; color: #ED7D31; margin-top: 5px;">{returns}</div>
        </div>
        <div class="creative-card card-salla">
            <div style="font-size: 0.9rem; color: #70AD47; font-weight: bold;">🛒 بدون فاتورة</div>
            <div style="font-size: 2.2rem; font-weight: 800; color: #70AD47; margin-top: 5px;">{orphan_salla}</div>
        </div>
        <div class="creative-card card-abc">
            <div style="font-size: 0.9rem; color: #FFC000; font-weight: bold;">📄 بدون طلب</div>
            <div style="font-size: 2.2rem; font-weight: 800; color: #FFC000; margin-top: 5px;">{orphan_abc}</div>
        </div>
        <div class="creative-card card-done">
            <div style="font-size: 0.9rem; color: #28a745; font-weight: bold;">✅ المكتملة</div>
            <div style="font-size: 2.2rem; font-weight: 800; color: #28a745; margin-top: 5px;">{completed}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_case_cards(df: pd.DataFrame, allow_actions: bool, pharmacist_name: str, 
                      pharmacy_name: str, is_admin: bool = False):
    if df.empty:
        st.success("لا توجد حالات في هذا القسم.")
        return

    for idx, row in df.iterrows():
        with st.container():
            col1, col2 = st.columns([4, 1])
            
            with col1:
                subcol1, subcol2, subcol3, subcol4 = st.columns(4)
                with subcol1:
                    st.markdown(f"**📋 رقم الطلب:** {row['order_number']}")
                    st.markdown(f"**🏷️ SKU:** {row['sku']}")
                    diff_value = numeric_value(row['difference'])
                    st.markdown(f"**📊 الفرق:** {'+' if diff_value > 0 else ''}{diff_value}")
                with subcol2:
                    st.markdown(f"**📦 المنتج:** {row['product_name'][:40]}...")
                    st.markdown(f"**🏥 الفرع:** {row['pharmacy_name'] or 'غير محدد'}")
                with subcol3:
                    invoice_display = row['invoice_number'] or 'غير متوفر'
                    pharmacist_display = row.get('abc_pharmacist_name', '') or ''
                    if not pharmacist_display or pharmacist_display == '':
                        pharmacist_display = 'غير معروف'
                    st.markdown(f"**🧾 رقم الفاتورة/الصيدلي:** {invoice_display}/{pharmacist_display}")
                    st.markdown(f"**📅 تاريخ الطلب:** {row['order_date'][:16] if row['order_date'] else 'غير متوفر'}")
                with subcol4:
                    st.markdown(f"**✅ الحالة:** {status_pill(row['status'])}", unsafe_allow_html=True)
                    st.markdown(f"**🧾 تاريخ الفاتورة:** {row['invoice_date'][:16] if row['invoice_date'] else 'غير متوفر'}")
            
            with col2:
                if is_admin and row.get('hidden_from_pharmacy', 0) == 1:
                    if st.button("👁️ إظهار", key=f"unhide_{idx}", use_container_width=True):
                        from utils.database import unhide_item_from_pharmacy
                        unhide_item_from_pharmacy(row['item_key'])
                        st.rerun()
                elif is_admin and row.get('hidden_from_pharmacy', 0) == 0:
                    if st.button("🙈 إخفاء", key=f"hide_{idx}", use_container_width=True):
                        from utils.database import hide_item_from_pharmacy
                        hide_item_from_pharmacy(row['item_key'], st.session_state.username)
                        st.rerun()
            
            with st.expander("📋 تفاصيل إضافية"):
                detail_cols = st.columns(3)
                with detail_cols[0]:
                    st.markdown(f"**كمية سلة:** {int(row['salla_qty']) if pd.notna(row['salla_qty']) else 0}")
                    st.markdown(f"**كمية ABC:** {int(row['abc_qty']) if pd.notna(row['abc_qty']) else 0}")
                with detail_cols[1]:
                    st.markdown(f"**حالة الطلب:** {row['order_status'] or 'غير متوفرة'}")
                    st.markdown(f"**نوع البروفايل:** {row.get('profile_type', '') or 'غير متوفر'}")
                with detail_cols[2]:
                    st.markdown(f"**تصنيف البيع:** {row.get('receipt_classification', '') or 'غير متوفر'}")
                    st.markdown(f"**فروع ABC:** {row.get('all_abc_pharmacies', '') or 'غير متوفر'}")
                st.markdown(f"**التفصيل:** {row.get('case_reason', '')}")
            
            note_key = f"note_{idx}"
            note_value = st.text_area(
                "📝 ملحوظة الصيدلي",
                value=row.get("pharmacist_note", "") or "",
                key=note_key,
                height=60,
            )
            
            btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 4])
            with btn_col1:
                if st.button("💾 حفظ", key=f"save_{note_key}", use_container_width=True):
                    from utils.database import save_case_note
                    save_case_note(
                        order_number=row["order_number"],
                        sku=row["sku"],
                        pharmacy_name=pharmacy_name,
                        case_type=row["case_type"],
                        note=note_value,
                    )
                    st.rerun()
            
            if allow_actions and row["status"] != "تم" and row["case_type"] in {"addition", "return", "orphan_salla", "orphan_abc"}:
                button_label = "✅ تأكيد" if row["case_type"] in {"addition", "orphan_salla"} else "🔄 تأكيد"
                with btn_col2:
                    if st.button(button_label, key=f"done_{note_key}", use_container_width=True):
                        from utils.database import save_case_note, mark_case_done
                        save_case_note(
                            order_number=row["order_number"],
                            sku=row["sku"],
                            pharmacy_name=pharmacy_name,
                            case_type=row["case_type"],
                            note=note_value,
                        )
                        mark_case_done(
                            order_number=row["order_number"],
                            sku=row["sku"],
                            pharmacy_name=pharmacy_name,
                            case_type=row["case_type"],
                            performed_by=pharmacist_name,
                        )
                        st.rerun()
            
            if is_admin and row["status"] == "تم":
                with btn_col2:
                    if st.button("🔓 إعادة فتح", key=f"reopen_{note_key}", use_container_width=True):
                        from utils.database import reopen_case
                        reopen_case(
                            order_number=row["order_number"],
                            sku=row["sku"],
                            pharmacy_name=pharmacy_name,
                            case_type=row["case_type"],
                        )
                        st.rerun()
            
            st.markdown("---")

def render_completed_table(df: pd.DataFrame, is_admin: bool = False, total_count: int = 0):
    """عرض جدول المكتملات مع إحصائية"""
    if df.empty:
        st.info("لا توجد طلبات مكتملة بعد.")
        return
    
    display_df = df.copy()
    display_df = display_df.rename(columns={
        "order_number": "رقم الطلب",
        "invoice_number": "رقم الفاتورة",
        "sku": "SKU",
        "product_name": "المنتج",
        "case_label": "نوع الإجراء",
        "performed_by": "تم بواسطة",
        "performed_at": "تاريخ الإكمال",
        "pharmacy_name": "الصيدلية"
    })
    
    cols_to_show = ["رقم الطلب", "رقم الفاتورة", "SKU", "المنتج", "نوع الإجراء", "تم بواسطة", "تاريخ الإكمال"]
    
    if is_admin:
        cols_to_show.insert(1, "الصيدلية")
    
    st.dataframe(display_df[cols_to_show], use_container_width=True)

def get_tab_label(label: str, current: int, total: int) -> str:
    """إنشاء اسم التبويب مع العدد"""
    return f"{label} ({current}/{total})"
