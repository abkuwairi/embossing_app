import streamlit as st
import pandas as pd
import os
import io
import streamlit_authenticator as stauth
from datetime import datetime

# Must be first command
st.set_page_config(page_title='Card Management', layout='wide')

# -------------------- Authentication Setup --------------------
usernames = ['admin_user', 'branch101', 'branch102']
names = ['Admin', 'Branch 101', 'Branch 102']
plain_passwords = ['admin123', 'b101', 'b102']
hashed_passwords = stauth.Hasher(plain_passwords).generate()
credentials = {'usernames': {}}
for uname, name_, pwd in zip(usernames, names, hashed_passwords):
    credentials['usernames'][uname] = {'name': name_, 'password': pwd}
authenticator = stauth.Authenticate(
    credentials,
    cookie_name='card_app_cookie',
    key='secure_key_123',
    cookie_expiry_days=1
)
name, auth_status, username = authenticator.login('🔐 Login', 'main')
if auth_status is False:
    st.error('❌ Invalid username or password')
elif auth_status is None:
    st.warning('👈 Please log in to continue')
else:
    authenticator.logout('Logout', 'sidebar')
    st.sidebar.success(f'Welcome {name}')
    # Determine role
    is_admin = username == 'admin_user'

    # -------------------- Data Paths --------------------
    DATA_DIR = 'data'
    MASTER_FILE = os.path.join(DATA_DIR, 'master_data.xlsx')
    os.makedirs(DATA_DIR, exist_ok=True)

    # -------------------- User Management --------------------
    if is_admin:
        st.sidebar.markdown('---')
        st.sidebar.header('Admin: User Management')
        df_users = pd.DataFrame.from_dict(credentials['usernames'], orient='index')
        df_users_display = df_users[['name']].rename(columns={'name':'Full Name'})
        df_users_display.index.name = 'Username'
        st.sidebar.dataframe(df_users_display)

    # -------------------- Upload Section --------------------
    st.title('📤 Upload Daily Card Report')
    if is_admin or username.startswith('branch'):
        with st.form('upload_form'):
            file = st.file_uploader('Choose Excel (.xlsx) file', type=['xlsx'], help='Daily card report')
            submit = st.form_submit_button('Save to Master')
            if submit:
                if not file:
                    st.error('Please select a file')
                else:
                    df_new = pd.read_excel(file, dtype=str)
                    df_new['Load Date'] = datetime.today().strftime('%Y-%m-%d')
                    # Append to master
                    if os.path.exists(MASTER_FILE):
                        df_old = pd.read_excel(MASTER_FILE, dtype=str)
                        df_comb = pd.concat([df_old, df_new], ignore_index=True)
                    else:
                        df_comb = df_new
                    df_comb.to_excel(MASTER_FILE, index=False)
                    st.success('✅ Master data updated')

    # -------------------- Reports & Branch Data --------------------
    st.title('📊 Reports & Branch Data')
    if os.path.exists(MASTER_FILE):
        df_all = pd.read_excel(MASTER_FILE, dtype=str)
        df_all['Delivery Branch Code'] = df_all['Delivery Branch Code'].astype(str).str.strip()
        df_all = df_all.drop_duplicates(subset=['Unmasked Card Number', 'Account Number'])
        df_all['Issuance Date'] = pd.to_datetime(df_all['Issuance Date'], errors='coerce', dayfirst=True)

        # Search bar
        search_term = st.text_input('🔍 Search by customer, card, or account')
        df_filtered = df_all.copy()
        if search_term:
            mask = (
                df_filtered['Customer Name'].str.contains(search_term, case=False, na=False) |
                df_filtered['Account Number'].str.contains(search_term, na=False) |
                df_filtered['Unmasked Card Number'].str.contains(search_term, na=False)
            )
            df_filtered = df_filtered[mask]

        # Date filters
        min_d = df_filtered['Issuance Date'].min()
        max_d = df_filtered['Issuance Date'].max()
        from_date = st.date_input('From date', value=min_d, min_value=min_d, max_value=max_d)
        to_date = st.date_input('To date', value=max_d, min_value=min_d, max_value=max_d)
        start_ts = pd.to_datetime(from_date)
        end_ts = pd.to_datetime(to_date)
        df_filtered = df_filtered[(df_filtered['Issuance Date'] >= start_ts) & (df_filtered['Issuance Date'] <= end_ts)]

        # Display by branch
        branches = sorted(df_filtered['Delivery Branch Code'].unique())
        for b in branches:
            df_b = df_filtered[df_filtered['Delivery Branch Code'] == b]
            st.subheader(f'Branch {b} ({len(df_b)} records)')
            st.dataframe(df_b, use_container_width=True)
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as w:
                df_b.to_excel(w, index=False, sheet_name='Sheet1')
            buf.seek(0)
            st.download_button(f'⬇️ Download Branch {b}', buf, f'branch_{b}.xlsx',
                               'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    else:
        st.info('ℹ️ No data available. Please upload a report.')
