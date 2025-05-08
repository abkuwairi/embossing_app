import streamlit as st
import pandas as pd
import os
import io
import streamlit_authenticator as stauth
from datetime import datetime

# ====== إعدادات الملفات ======
DATA_DIR = "data"
MASTER_FILE = os.path.join(DATA_DIR, "master_data.xlsx")
USERS_FILE = os.path.join(DATA_DIR, "users_data.xlsx")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# ====== تحميل/إنشاء ملف المستخدمين ======
def load_users():
    if os.path.exists(USERS_FILE):
        return pd.read_excel(USERS_FILE, dtype=str)
    else:
        return pd.DataFrame(columns=[
            'Username', 'Name', 'Password', 'Email', 
            'Phone', 'Branch', 'Role', 'Active'
        ])

def save_users(df):
    df.to_excel(USERS_FILE, index=False)

# ====== تهيئة المصادقة ======
users_df = load_users()
if not users_df.empty:
    credentials = {'usernames': {}}
    for _, row in users_df.iterrows():
        if row['Active'] == 'True':
            credentials['usernames'][row['Username']] = {
                'name': row['Name'],
                'password': row['Password'],
                'email': row['Email'],
                'branch': row['Branch'],
                'role': row['Role']
            }
else:
    # بيانات افتراضية للمشرف إذا لم يوجد ملف
    hashed_admin_pass = stauth.Hasher(['admin123']).generate()[0]
    credentials = {
        'usernames': {
            'admin_user': {
                'name': 'Admin',
                'password': hashed_admin_pass,
                'email': 'admin@example.com',
                'branch': '0',
                'role': 'admin',
            }
        }
    }
    save_users(pd.DataFrame([{
        'Username': 'admin_user',
        'Name': 'Admin',
        'Password': hashed_admin_pass,
        'Email': 'admin@example.com',
        'Phone': '',
        'Branch': '0',
        'Role': 'admin',
        'Active': 'True'
    }]))

authenticator = stauth.Authenticate(
    credentials,
    "embossing_app",
    "abcdef",
    1
)

name, authentication_status, username = authenticator.login("🔐 تسجيل الدخول")

if authentication_status is False:
    st.error("❌ اسم المستخدم أو كلمة المرور غير صحيحة")
elif authentication_status is None:
    st.warning("👈 الرجاء تسجيل الدخول للاستمرار")
elif authentication_status:
    st.sidebar.success(f"مرحباً {name}")
    authenticator.logout("تسجيل الخروج", "sidebar")
    users_df = load_users()
    current_user = users_df[users_df['Username'] == username].iloc[0]
    user_role = current_user['Role']

    # ====== واجهة إدارة المستخدمين (للمشرف فقط) ======
    if user_role == 'admin':
        st.sidebar.header("👨💼 لوحة التحكم")
        admin_action = st.sidebar.selectbox("اختر إجراء:", [
            "إنشاء مستخدم جديد", 
            "عرض/تعديل المستخدمين",
            "تغيير كلمة المرور"
        ])

        # ------ إنشاء مستخدم جديد ------
        if admin_action == "إنشاء مستخدم جديد":
            st.subheader("➕ إنشاء مستخدم جديد")
            with st.form("user_form"):
                new_name = st.text_input("الاسم الكامل:")
                new_username = st.text_input("اسم المستخدم:")
                new_email = st.text_input("البريد الإلكتروني:")
                new_phone = st.text_input("رقم الهاتف:")
                new_branch = st.text_input("رقم الفرع:")
                new_role = st.selectbox("الدور:", ["admin", "branch"])
                new_pass = st.text_input("كلمة المرور المؤقتة:", type="password")
                submitted = st.form_submit_button("حفظ")

                if submitted:
                    if new_username in users_df['Username'].values:
                        st.error("اسم المستخدم موجود مسبقاً!")
                    else:
                        hashed_pass = stauth.Hasher([new_pass]).generate()[0]
                        new_user = {
                            'Username': new_username,
                            'Name': new_name,
                            'Password': hashed_pass,
                            'Email': new_email,
                            'Phone': new_phone,
                            'Branch': new_branch,
                            'Role': new_role,
                            'Active': 'True'
                        }
                        users_df = pd.concat([users_df, pd.DataFrame([new_user])], ignore_index=True)
                        save_users(users_df)
                        st.success("✅ تم إنشاء المستخدم بنجاح")

        # ------ عرض/تعديل المستخدمين ------
        elif admin_action == "عرض/تعديل المستخدمين":
            st.subheader("👥 إدارة المستخدمين")
            edited_df = st.data_editor(
                users_df.drop(columns=['Password']),
                use_container_width=True,
                column_config={
                    "Active": st.column_config.CheckboxColumn("مفعل"),
                    "Role": st.column_config.SelectboxColumn("الدور", options=["admin", "branch"])
                }
            )
            if st.button("حفظ التعديلات"):
                users_df.update(edited_df)
                save_users(users_df)
                st.rerun()

        # ------ تغيير كلمة المرور ------
        elif admin_action == "تغيير كلمة المرور":
            st.subheader("🔒 تغيير كلمة مرور مستخدم")
            target_user = st.selectbox("اختر المستخدم:", users_df['Username'])
            new_pass = st.text_input("كلمة المرور الجديدة:", type="password")
            if st.button("تحديث"):
                hashed_pass = stauth.Hasher([new_pass]).generate()[0]
                users_df.loc[users_df['Username'] == target_user, 'Password'] = hashed_pass
                save_users(users_df)
                st.success("✅ تم التحديث بنجاح")

    # ====== الوظائف الرئيسية للتطبيق ======
    st.title("📋 نظام تحميل ومتابعة بطاقات Embossing")

    # ===== رفع التقرير =====
    if user_role == "admin" or user_role == "branch":
        uploaded_file = st.file_uploader("📁 الرجاء رفع تقرير البطاقات اليومي (Excel فقط)", type=["xlsx"])
        if uploaded_file:
            try:
                df_new = pd.read_excel(uploaded_file, dtype=str)
                
                # ------ تنظيف أسماء الأعمدة ------
                df_new.columns = df_new.columns.str.strip()
                df_new["Load Date"] = datetime.today().strftime('%Y-%m-%d')

                # ------ التحقق من الأعمدة المطلوبة ------
                required_columns = [
                    "Delivery Branch Code", 
                    "Unmasked Card Number", 
                    "Account Number", 
                    "Issuance Date", 
                    "Customer Name"
                ]
                missing_columns = [col for col in required_columns if col not in df_new.columns]
                
                if missing_columns:
                    st.error(f"❌ الملف المرفوع يفتقد الأعمدة التالية: {', '.join(missing_columns)}")
                    st.write("ملاحظة: تأكد من عدم وجود مسافات زائدة في أسماء الأعمدة!")
                    st.write("الأعمدة الموجودة:", df_new.columns.tolist())
                    st.stop()

                # ------ دمج البيانات ------
                if os.path.exists(MASTER_FILE):
                    df_old = pd.read_excel(MASTER_FILE, dtype=str)
                    df_combined = pd.concat([df_old, df_new], ignore_index=True)
                else:
                    df_combined = df_new

                df_combined.to_excel(MASTER_FILE, index=False)
                st.success("✅ تم تحديث قاعدة البيانات بنجاح.")
            except Exception as e:
                st.error(f"❌ خطأ أثناء رفع الملف: {e}")

    # ===== عرض البيانات =====
    if os.path.exists(MASTER_FILE):
        df_all = pd.read_excel(MASTER_FILE, dtype=str)

        # ------ التحقق من الأعمدة في الملف الرئيسي ------
        required_columns = [
            "Delivery Branch Code", 
            "Unmasked Card Number", 
            "Account Number", 
            "Issuance Date", 
            "Customer Name"
        ]
        missing_columns = [col for col in required_columns if col not in df_all.columns]
        
        if missing_columns:
            st.error(f"❌ ملف البيانات الرئيسي تالف! الأعمدة المفقودة: {', '.join(missing_columns)}")
            st.stop()

        # ------ معالجة البيانات ------
        df_all["Delivery Branch Code"] = df_all["Delivery Branch Code"].astype(str).str.strip()
        df_all = df_all.drop_duplicates(subset=["Unmasked Card Number", "Account Number"])
        df_all["Issuance Date"] = pd.to_datetime(df_all["Issuance Date"], errors='coerce', dayfirst=True)

        # 🔍 بحث
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

        # 🗓 فلترة بالتاريخ
        if not df_all["Issuance Date"].isna().all():
            min_date = df_all["Issuance Date"].min()
            max_date = df_all["Issuance Date"].max()

            start_date = st.date_input("📆 من تاريخ إصدار", min_value=min_date, max_value=max_date, value=min_date)
            end_date = st.date_input("📆 إلى تاريخ إصدار", min_value=min_date, max_value=max_date, value=max_date)

            df_all = df_all[
                (df_all["Issuance Date"] >= pd.to_datetime(start_date)) &
                (df_all["Issuance Date"] <= pd.to_datetime(end_date))
            ]

        # 📌 عرض الفروع
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