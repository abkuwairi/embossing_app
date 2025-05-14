import streamlit as st
import pandas as pd
import os
import io
import streamlit_authenticator as stauth
from datetime import datetime

# بيانات المستخدمين المشفرة مسبقًا
usernames = ['admin_user', 'branch101', 'branch102']
names = ['Admin', '101', '102']
hashed_passwords = [
    '$2b$12$VaSfgEv8qGeM2cf.XJngnOKRYaODu6DhHuMKPC8U/nTwZa/8s3FQW',  # admin123
    '$2b$12$NykdiGRPNN3LB3hnflZ75eab9xHiFSA0O9Uv7k7nN8XKhslYruFKO',  # b101
    '$2b$12$Z9qC1b1hjg/U5D9clU6xQOKVIn2ycpTGn64sQeCNP.DTmBTaJljta'   # b102
]

# استخدام مفتاح توقيع أقوى (32 حرفًا)
authenticator = stauth.Authenticate(
    names=names,
    usernames=usernames,
    passwords=hashed_passwords,
    cookie_name="embossing_app_cookie",
    key="abcd1234abcd1234abcd1234abcd1234",  # مفتاح توقيع 32 حرفًا
    cookie_expiry_days=1
)

name, authentication_status, username = authenticator.login("🔐 تسجيل الدخول")

if authentication_status is False:
    st.error("❌ اسم المستخدم أو كلمة المرور غير صحيحة")
elif authentication_status is None:
    st.warning("👈 الرجاء تسجيل الدخول للاستمرار")
elif authentication_status:
    st.sidebar.success(f"مرحباً {name}")
    authenticator.logout("تسجيل الخروج", "sidebar")

    user_role = "uploader" if username == "admin_user" else "viewer"
    st.title("📋 نظام تحميل ومتابعة بطاقات Embossing")

    DATA_DIR = "data"
    MASTER_FILE = os.path.join(DATA_DIR, "master_data.xlsx")
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    if user_role == "uploader":
        uploaded_file = st.file_uploader("📁 الرجاء رفع تقرير البطاقات اليومي (Excel فقط)", type=["xlsx"])
        if uploaded_file:
            try:
                df_new = pd.read_excel(uploaded_file, dtype=str)
                df_new["Load Date"] = datetime.today().strftime('%Y-%m-%d')

                if os.path.exists(MASTER_FILE):
                    df_old = pd.read_excel(MASTER_FILE, dtype=str)
                    df_combined = pd.concat([df_old, df_new], ignore_index=True)
                else:
                    df_combined = df_new

                df_combined.to_excel(MASTER_FILE, index=False)
                st.success("✅ تم تحديث قاعدة البيانات بنجاح.")
            except Exception as e:
                st.error(f"❌ خطأ أثناء رفع الملف: {e}")

    if os.path.exists(MASTER_FILE):
        df_all = pd.read_excel(MASTER_FILE, dtype=str)
        df_all["Delivery Branch Code"] = df_all["Delivery Branch Code"].astype(str).str.strip()
        df_all = df_all.drop_duplicates(subset=["Unmasked Card Number", "Account Number"])
        df_all["Issuance Date"] = pd.to_datetime(df_all["Issuance Date"], errors='coerce', dayfirst=True)

        search_term = st.text_input("🔍 ابحث باسم الزبون أو رقم البطاقة أو الحساب:")
        df_all["Customer Name"] = df_all["Customer Name"].fillna("").astype(str)
        df_all["Account Number"] = df_all["Account Number"].fillna("").astype(str)
        df_all["Unmasked Card Number"] = df_all["Unmasked Card Number"].fillna("").astype(str)

        if search_term:
            df_all = df_all[
                df_all["Customer Name"].str.contains(search_term, case=False, na=False) |
                df_all["Account Number"].str.contains(search_term, na=False) |
                df_all["Unmasked Card Number"].str.contains(search_term, na=False)
            ]

        if not df_all["Issuance Date"].isna().all():
            min_date = df_all["Issuance Date"].min()
            max_date = df_all["Issuance Date"].max()
            start_date = st.date_input("📆 من تاريخ إصدار", min_value=min_date, max_value=max_date, value=min_date)
            end_date = st.date_input("📆 إلى تاريخ إصدار", min_value=min_date, max_value=max_date, value=max_date)
            df_all = df_all[
                (df_all["Issuance Date"] >= pd.to_datetime(start_date)) &
                (df_all["Issuance Date"] <= pd.to_datetime(end_date))
            ]

        branches = sorted(df_all["Delivery Branch Code"].dropna().unique())
        for branch in branches:
            df_branch = df_all[df_all["Delivery Branch Code"] == branch]
            with st.expander(f"📌 بيانات الفرع: {branch}", expanded=False):
                st.dataframe(df_branch, use_container_width=True)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_branch.to_excel(writer, index=False, sheet_name='Sheet1')
                    workbook = writer.book
                    worksheet = writer.sheets['Sheet1']
                    text_format = workbook.add_format({'num_format': '@'})
                    worksheet.set_column('A:A', None, text_format)
                    worksheet.set_column('B:B', None, text_format)
                output.seek(0)
                st.download_button(
                    label=f"⬇️ تحميل بيانات الفرع {branch}",
                    data=output,
                    file_name=f"branch_{branch}_cards.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    else:
        st.info("ℹ️ لم يتم تحميل أي بيانات بعد.")