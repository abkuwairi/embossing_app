import streamlit as st
import pandas as pd
import os
import io
import json
import logging
import streamlit_authenticator as stauth
from datetime import datetime

# ------------------ Configuration ------------------
DATA_DIR = 'data'
CRED_FILE = os.path.join(DATA_DIR, 'credentials.json')
MASTER_FILE = os.path.join(DATA_DIR, 'master_data.xlsx')
REQUIRED_COLUMNS = ['Unmasked Card Number', 'Customer Name', 'Account Number', 'Issuance Date', 'Delivery Branch Code']

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# Set up logging to file
logging.basicConfig(
    filename=os.path.join(DATA_DIR, 'app.log'),
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)

# ------------------ Credentials Handling ------------------
def load_credentials():
    if os.path.exists(CRED_FILE):
        with open(CRED_FILE, 'r') as f:
            return json.load(f)
    default_credentials = {
        'usernames': {
            'admin_user': {'name': 'Admin', 'password': None, 'email': 'admin@example.com', 'phone': '', 'branch_code': '', 'branch_name': '', 'is_active': True, 'role': 'admin'},
            'branch101': {'name': 'Branch101', 'password': None, 'email': '', 'phone': '', 'branch_code': '101', 'branch_name': 'Branch 101', 'is_active': True, 'role': 'viewer'},
            'branch102': {'name': 'Branch102', 'password': None, 'email': '', 'phone': '', 'branch_code': '102', 'branch_name': 'Branch 102', 'is_active': True, 'role': 'viewer'}
        }
    }
    plain_defaults = {'admin_user': 'admin123', 'branch101': 'b101', 'branch102': 'b102'}
    for user, info in default_credentials['usernames'].items():
        pwd = plain_defaults.get(user, 'password123')
        info['password'] = stauth.Hasher([pwd]).generate()[0]
    with open(CRED_FILE, 'w') as f:
        json.dump(default_credentials, f, indent=4)
    return default_credentials

credentials = load_credentials()

# ------------------ Streamlit-Authenticator ------------------
active_users = {
    user: {'name': info['name'], 'password': info['password']}
    for user, info in credentials['usernames'].items() if info.get('is_active')
}
authenticator = stauth.Authenticate(
    {'usernames': active_users},
    cookie_name='card_mgmt_cookie',
    key='xyz123xyz123xyz123xyz123xyz123',
    cookie_expiry_days=1
)

# ------------------ Caching Data Loads ------------------
@st.cache_data
def load_master_data():
    if os.path.exists(MASTER_FILE):
        df = pd.read_excel(MASTER_FILE, dtype=str)
        df.columns = df.columns.str.strip()
        return df
    return pd.DataFrame(columns=REQUIRED_COLUMNS + ['Load Date'])

# ------------------ UI ------------------
name, auth_status, username = authenticator.login('🔐 Login', 'main')
if auth_status is False:
    st.error('❌ Invalid username or password')
elif auth_status is None:
    st.warning('👈 Please login to continue')
else:
    # Greet user
    if username in credentials['usernames']:
        st.sidebar.success(f"Welcome {credentials['usernames'][username]['name']}")
    else:
        st.sidebar.error('Error: Username not found')
    authenticator.logout('Logout', 'sidebar', key='logout_btn')

    # Permissions
    role = credentials['usernames'][username]['role']
    can_upload = role in ['admin', 'management', 'uploader']
    can_manage = role == 'admin'

    # Header
    if os.path.exists('logo.png'):
        st.image('logo.png', use_container_width=True)
    st.markdown('# 🚀 Card Management System')

    # Navigation tabs
    tabs = ['📊 Card Reports']
    if can_manage:
        tabs.insert(0, '👥 User Management')
    selected_tab = st.selectbox('Main Menu', tabs)

    # ------------------ User Management ------------------
    if selected_tab == '👥 User Management':
        st.header('👥 User Management')
        st.subheader('All Users')
        df_users = pd.DataFrame.from_dict(credentials['usernames'], orient='index')
        df_disp = df_users[['name', 'email', 'phone', 'branch_code', 'branch_name', 'role', 'is_active']]
        df_disp.index.name = 'username'
        st.dataframe(df_disp, use_container_width=True)

        st.subheader('Add New User')
        with st.form('add_form'):
            new_user = st.text_input('Username')
            full_name = st.text_input('Full Name')
            email = st.text_input('Email')
            phone = st.text_input('Phone Number')
            branch_code = st.text_input('Branch Code')
            branch_name = st.text_input('Branch Name')
            password = st.text_input('Password', type='password')
            is_active = st.checkbox('Active', value=True)
            role_choice = st.selectbox('Role', ['admin', 'management', 'viewer', 'uploader'])
            if st.form_submit_button('Add User'):
                missing_cols = [c for c in REQUIRED_COLUMNS if c not in load_master_data().columns]
                if missing_cols:
                    st.error(f'Cannot add user before uploading data. Missing columns: {missing_cols}')
                elif new_user in credentials['usernames']:
                    st.error('User already exists')
                else:
                    credentials['usernames'][new_user] = {
                        'name': full_name,
                        'email': email,
                        'phone': phone,
                        'branch_code': branch_code,
                        'branch_name': branch_name,
                        'role': role_choice,
                        'is_active': is_active,
                        'password': stauth.Hasher([password]).generate()[0]
                    }
                    with open(CRED_FILE, 'w') as f:
                        json.dump(credentials, f, indent=4)
                    st.success('User added successfully')

    # ------------------ Card Reports ------------------
    if selected_tab == '📊 Card Reports':
        st.header('📊 Card Reports')
        st.info('Upload an XLSX or CSV file containing columns: ' + ', '.join(REQUIRED_COLUMNS))
        if can_upload:
            uploaded_file = st.file_uploader('Choose a file', type=['xlsx', 'csv'], help='Ensure column names match exactly')
            if uploaded_file:
                try:
                    df_new = (
                        pd.read_csv(uploaded_file, dtype=str)
                        if uploaded_file.name.lower().endswith('.csv')
                        else pd.read_excel(uploaded_file, dtype=str)
                    )
                    missing = [c for c in REQUIRED_COLUMNS if c not in df_new.columns]
                    if missing:
                        st.error(f'Missing columns: {missing}')
                    else:
                        df_new['Load Date'] = datetime.today().strftime('%Y-%m-%d')
                        df_master = load_master_data()
                        df_comb = pd.concat([df_master, df_new], ignore_index=True)
                        df_comb.to_excel(MASTER_FILE, index=False)
                        st.success('✅ Data updated successfully')
                        logging.info(f"User {username} uploaded {uploaded_file.name}")
                except Exception as e:
                    st.error(f'❌ Error during processing: {e}')

        df_all = load_master_data()
        if df_all.empty:
            st.info('ℹ️ No data to display')
        else:
            df_all['Issuance Date'] = pd.to_datetime(df_all['Issuance Date'], errors='coerce', dayfirst=True)
            bad_count = df_all['Issuance Date'].isna().sum()
            if bad_count > 0:
                st.warning(f'Failed to parse {bad_count} dates')

            # Global search filter
            query = st.text_input('🔍 Global Search')
            if query:
                df_all = df_all[df_all.apply(lambda row: row.astype(str).str.contains(query, case=False).any(), axis=1)]

            # Date range filter
            if not df_all['Issuance Date'].isna().all():
                min_date = df_all['Issuance Date'].min()
                max_date = df_all['Issuance Date'].max()
                start = st.date_input('From Date', min_value=min_date, max_value=max_date, value=min_date)
                end = st.date_input('To Date', min_value=min_date, max_value=max_date, value=max_date)
                start_ts, end_ts = pd.to_datetime(start), pd.to_datetime(end)
                df_all = df_all[(df_all['Issuance Date'] >= start_ts) & (df_all['Issuance Date'] <= end_ts)]

            # Display by branch
            for branch in sorted(df_all['Delivery Branch Code'].unique()):
                subset = df_all[df_all['Delivery Branch Code'] == branch]
                with st.expander(f'Branch {branch} ({len(subset)} rows)'):
                    st.dataframe(subset, use_container_width=True)
                    if can_upload:
                        buf = io.BytesIO()
                        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                            subset.to_excel(writer, index=False, sheet_name='Sheet1')
                        buf.seek(0)
                        st.download_button('⬇️ Download Data', buf, f'{branch}.xlsx',
                                            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
# End of app
