import streamlit as st
from io import BytesIO
from datetime import datetime
from utils.excel_processor import update_balances

def show():
    st.markdown(
        """
        <div class="hero">
            <h1>🔄 تحديث أرصدة الفروع</h1>
            <p>رفع ملفات ABC و Salla لتحديث الأرصدة بناءً على المعادلات المحددة</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    col1, col2 = st.columns(2)
    with col1:
        abc_file = st.file_uploader("📊 رفع ملف ABC (يبدأ من الصف 5)", type=["xlsx"], key="abc_balances")
    with col2:
        salla_file = st.file_uploader("📋 رفع ملف Salla", type=["xlsx"], key="salla_balances")
    
    if abc_file and salla_file:
        if st.button("🔄 تنفيذ تحديث الأرصدة", use_container_width=True):
            with st.spinner("جاري تحديث الأرصدة..."):
                result_df, result = update_balances(abc_file, salla_file)
                if result_df is not None:
                    st.success(f"✅ تم التحديث بنجاح! عدد الأصناف المحدثة: {result}")
                    st.dataframe(result_df.head(20), use_container_width=True)
                    
                    output = BytesIO()
                    result_df.to_excel(output, index=False)
                    output.seek(0)
                    st.download_button(
                        "📥 تحميل ملف Salla المحدث",
                        data=output,
                        file_name=f"salla_updated_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
                else:
                    st.error(f"❌ خطأ في التحديث: {result}")