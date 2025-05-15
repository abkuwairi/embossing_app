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

# ------------------ Data Loading ------------------
def load_master_data():
    """
    Load and return the current master_data file as a DataFrame.
    """
    if os.path.exists(MASTER_FILE):
        df = pd.read_excel(MASTER_FILE, dtype=str)
        df.columns = df.columns.str.strip()
        df['Delivery Branch Code'] = df['Delivery Branch Code'].astype(str).str.strip()
        return df
    return pd.DataFrame(columns=REQUIRED_COLUMNS + ['Load Date'])

# ------------------ UI ------------------
name, auth_status, username = authenticator.login('🔐 Login', 'main')
if auth_status is False:
    st.error('❌ Invalid username or password')
elif auth_status is None:
    st.warning('👈 Please login to continue')
else:
    # Greet
    user_info = credentials['usernames'].get(username, {})
    st.sidebar.success(f"Welcome {user_info.get('name', username)}")
    authenticator.logout('Logout', 'sidebar', key='logout_btn')

    # Roles
    role = user_info.get('role', 'viewer')
    can_upload = role in ['admin', 'management', 'uploader']
    can_manage = role == 'admin'

    # Header
    st.markdown('# 🚀 Card Management System')

    # Tabs
    tabs = ['📊 Card Reports']
    if can_manage:
        tabs.insert(0, '👥 User Management')
    selected_tab = st.selectbox('Main Menu', tabs)

    # User Management
    if selected_tab == '👥 User Management':
        st.header('👥 User Management')
        df_users = pd.DataFrame.from_dict(credentials['usernames'], orient='index')
        df_disp = df_users[['name', 'email', 'phone', 'branch_code', 'branch_name', 'role', 'is_active']]
        df_disp.index.name = 'username'
        st.dataframe(df_disp, use_container_width=True)

    # Card Reports
    if selected_tab == '📊 Card Reports':
        st.header('📊 Card Reports')
        st.info('Upload an XLSX, XLS, or CSV file with columns: ' + ', '.join(REQUIRED_COLUMNS))
        if can_upload:
            uploaded_file = st.file_uploader('Choose a file', type=['xlsx', 'xls', 'csv'], help='Column names must match exactly')
            if uploaded_file:
                try:
                    # Read file
                    if uploaded_file.name.lower().endswith(('.xlsx', '.xls')):
                        df_new = pd.read_excel(uploaded_file, dtype=str)
                    else:
                        df_new = pd.read_csv(uploaded_file, dtype=str)

                    # Sanitize
                    df_new.columns = df_new.columns.str.strip()
                    if any(c not in df_new.columns for c in REQUIRED_COLUMNS):
                        missing = [c for c in REQUIRED_COLUMNS if c not in df_new.columns]
                        st.error(f'Missing columns: {missing}')
                    else:
                        # Debug branch codes
                        df_new['Delivery Branch Code'] = df_new['Delivery Branch Code'].astype(str).str.strip()
                        st.write('📋 Detected branch codes in upload:', df_new['Delivery Branch Code'].unique())

                        # Date parsing
                        df_new['Issuance Date Raw'] = df_new['Issuance Date']
                        parsed = pd.to_datetime(df_new['Issuance Date Raw'].astype(str).str.strip(), errors='coerce', dayfirst=True, infer_datetime_format=True)
                        mask = parsed.isna() & df_new['Issuance Date Raw'].notna()
                        if mask.any():
                            parsed.loc[mask] = pd.to_datetime(df_new.loc[mask, 'Issuance Date Raw'], errors='coerce', dayfirst=False, infer_datetime_format=True)
                            st.write('⚠️ Dates failed initial parse:', df_new.loc[mask, 'Issuance Date Raw'].unique())
                        df_new['Issuance Date'] = parsed.dt.strftime('%Y-%m-%d')

                        # Append
                        df_new['Load Date'] = datetime.today().strftime('%Y-%m-%d')
                        df_master = load_master_data()
                        df_comb = pd.concat([df_master, df_new], ignore_index=True)
                        df_comb.to_excel(MASTER_FILE, index=False)
                        st.success('✅ Data updated successfully')
                        logging.info(f"User {username} uploaded {uploaded_file.name}")
                except Exception as e:
                    st.error(f'❌ Error during processing: {e}')

        # Load and display
        df_all = load_master_data()
        if df_all.empty:
            st.info('ℹ️ No data to display')
        else:
            # Debug master branches
            st.write('📋 All branch codes in master data:', df_all['Delivery Branch Code'].unique())

            # Parse master dates
            parsed = pd.to_datetime(df_all['Issuance Date'], errors='coerce', dayfirst=True, infer_datetime_format=True)
            df_all['Issuance Date'] = parsed

            # Global search
            query = st.text_input('🔍 Global Search')
            if query:
                df_all = df_all[df_all.apply(lambda row: row.astype(str).str.contains(query, case=False).any(), axis=1)]

            # Date filter
            valid = df_all['Issuance Date'].dropna()
            if not valid.empty:
                start = st.date_input('From Date', min_value=valid.min(), max_value=valid.max(), value=valid.min())
                end = st.date_input('To Date', min_value=valid.min(), max_value=valid.max(), value=valid.max())
                df_all = df_all[(df_all['Issuance Date'] >= pd.to_datetime(start)) & (df_all['Issuance Date'] <= pd.to_datetime(end))]

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
                        st.download_button('⬇️ Download Data', buf, f'{branch}.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
