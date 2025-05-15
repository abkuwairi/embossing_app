import streamlit as st
import pandas as pd
import os
import io
import streamlit_authenticator as stauth
from datetime import datetime

# إعداد بيانات الاعتماد المسبقة
usernames = ['admin_user', 'branch101', 'branch102']
names = ['Admin', 'Branch 101', 'Branch 102']
hashed_passwords = [
    '$2b$12$VaSfgEv8qGeM2cf.XJngnOKRYaODu6DhHuMKPC8U/nTwZa/8s3FQW',  # admin123
    '$2b$12$NykdiGRPNN3LB3hnflZ75eab9xHiFSA0O9Uv7k7nN8XKhslYruFKO',  # b101
    '$2b$12$Z9qC1b1hjg/U5D9clU6xQOKVIn2ycpTGn64sQeCNP.DTmBTaJjlta'   # b102
]

# تحضير قاموس الاعتماد
credentials = {'usernames': {}}
for uname, full_name, pwd in zip(usernames, names, hashed_passwords):
    credentials['usernames'][uname] = {'name': full_name, 'password': pwd}

# إنشاء المصادق
authenticator = stauth.Authenticate(
    credentials,
    'embossing_app_cookie',
    'abcd1234abcd1234abcd1234abcd1234',
    cookie_expiry_days=1
)

# واجهة تسجيل الدخول
name, authentication_status, username = authenticator.login('🔐 تسجيل الدخول', 'main')

if authentication_status is False:
    st.error('❌ اسم المستخدم أو كلمة المرور غير صحيحة')
elif authentication_status is None:
    st.warning('👈 الرجاء تسجيل الدخول للاستمرار')
else:
    # زر تسجيل الخروج
    authenticator.logout('تسجيل الخروج', 'sidebar')
    st.sidebar.success(f'مرحباً {name}')

    # تحديد صلاحية المستخدم
    is_uploader = (username == 'admin_user')

    # إعداد المسارات
    DATA_DIR = 'data'
    MASTER_FILE = os.path.join(DATA_DIR, 'master_data.xlsx')
    os.makedirs(DATA_DIR, exist_ok=True)

    # رفع الملف (للمشرف)
    if is_uploader:
        uploaded_file = st.file_uploader('📁 رفع تقرير بطاقات اليومي (Excel فقط)', type=['xlsx'])
        if uploaded_file is not None:
            try:
                df_new = pd.read_excel(uploaded_file, dtype=str)
                df_new['Load Date'] = datetime.today().strftime('%Y-%m-%d')
                if os.path.exists(MASTER_FILE):
                    df_old = pd.read_excel(MASTER_FILE, dtype=str)
                    df_combined = pd.concat([df_old, df_new], ignore_index=True)
                else:
                    df_combined = df_new
                df_combined.to_excel(MASTER_FILE, index=False)
                st.success('✅ تم تحديث قاعدة البيانات بنجاح.')
            except Exception as e:
                st.error(f'❌ خطأ أثناء رفع الملف: {e}')

    # عرض التقارير
    st.title('📊 تقارير ومتابعة بطاقات Embossing')
    if os.path.exists(MASTER_FILE):
        df_all = pd.read_excel(MASTER_FILE, dtype=str)
        df_all['Delivery Branch Code'] = df_all['Delivery Branch Code'].astype(str).str.strip()
        df_all = df_all.drop_duplicates(subset=['Unmasked Card Number', 'Account Number'])
        df_all['Issuance Date'] = pd.to_datetime(df_all['Issuance Date'], errors='coerce', dayfirst=True)

        # البحث النصي
        search_term = st.text_input('🔍 ابحث باسم الزبون أو رقم البطاقة أو الحساب')
        for col in ['Customer Name', 'Account Number', 'Unmasked Card Number']:
            df_all[col] = df_all[col].fillna('').astype(str)
        if search_term:
            mask = (
                df_all['Customer Name'].str.contains(search_term, case=False) |
                df_all['Account Number'].str.contains(search_term) |
                df_all['Unmasked Card Number'].str.contains(search_term)
            )
            df_all = df_all[mask]

        # فلترة بالتواريخ
        if not df_all['Issuance Date'].isna().all():
            min_date = df_all['Issuance Date'].min()
            max_date = df_all['Issuance Date'].max()
            start_date = st.date_input('📆 من تاريخ الإصدار', min_value=min_date, max_value=max_date, value=min_date)
            end_date = st.date_input('📆 إلى تاريخ الإصدار', min_value=min_date, max_value=max_date, value=max_date)
            df_all = df_all[(df_all['Issuance Date'] >= start_date) & (df_all['Issuance Date'] <= end_date)]

        # عرض البيانات حسب الفروع
        branches = sorted(df_all['Delivery Branch Code'].unique())
        for branch in branches:
            df_branch = df_all[df_all['Delivery Branch Code'] == branch]
            with st.expander(f'📌 بيانات الفرع: {branch}', expanded=False):
                st.dataframe(df_branch, use_container_width=True)
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                    df_branch.to_excel(writer, index=False)
                buf.seek(0)
                st.download_button(
                    label=f'⬇️ تحميل بيانات الفرع {branch}',
                    data=buf,
                    file_name=f'branch_{branch}.xlsx',
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
    else:
        st.info('ℹ️ لا توجد بيانات حتى الآن.')
