import streamlit as st
import pandas as pd
import os
import io
import json
import logging
import streamlit_authenticator as stauth
from datetime import datetime

# Must be first command
st.set_page_config(page_title='Card Management', layout='wide')

# Configuration
DATA_DIR = 'data'
CRED_FILE = os.path.join(DATA_DIR, 'credentials.json')
MASTER_FILE = os.path.join(DATA_DIR, 'master_data.xlsx')
LOG_FILE = os.path.join(DATA_DIR, 'app.log')
REQUIRED_COLUMNS = ['Unmasked Card Number', 'Customer Name', 'Account Number', 'Issuance Date', 'Delivery Branch Code']

os.makedirs(DATA_DIR, exist_ok=True)

# Logging setup
logger = logging.getLogger()
logger.setLevel(logging.INFO)
for handler in list(logger.handlers):
    logger.removeHandler(handler)
file_handler = logging.FileHandler(LOG_FILE, mode='a')
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
logger.addHandler(file_handler)

# Credentials handling
def load_credentials():
    if os.path.exists(CRED_FILE):
        return json.load(open(CRED_FILE))
    defaults = {'usernames': {
        'admin_user': {'name': 'Admin', 'role': 'admin', 'password': None},
        'branch101': {'name': 'Branch101', 'role': 'viewer', 'password': None},
        'branch102': {'name': 'Branch102', 'role': 'viewer', 'password': None}
    }}
    plain = {'admin_user': 'admin123', 'branch101': 'b101', 'branch102': 'b102'}
    for u,v in defaults['usernames'].items():
        v['password'] = stauth.Hasher([plain[u]]).generate()[0]
    json.dump(defaults, open(CRED_FILE, 'w'), indent=4)
    return defaults

credentials = load_credentials()
active_users = {u: {'name':v['name'], 'password':v['password']} for u,v in credentials['usernames'].items()}
auth = stauth.Authenticate({'usernames': active_users}, cookie_name='card_app_cookie', key='secure_key', cookie_expiry_days=1)

# Load master data
def load_master_data():
    if os.path.exists(MASTER_FILE):
        df = pd.read_excel(MASTER_FILE, dtype=str)
        df.columns = df.columns.str.strip()
        df['Delivery Branch Code'] = df['Delivery Branch Code'].astype(str).str.strip()
        df['Issuance Date'] = pd.to_datetime(df['Issuance Date'], errors='coerce')
        return df
    cols = REQUIRED_COLUMNS + ['Load Date']
    return pd.DataFrame(columns=cols)

# UI
name, status, username = auth.login('🔐 Login','main')
if status is False:
    st.error('Invalid credentials')
elif status is None:
    st.warning('Please login')
else:
    auth.logout('Logout','sidebar')
    st.sidebar.success(f'Welcome {name}')
    role = credentials['usernames'][username]['role']
    logger.info(f"{username} logged in")

    # Tabs for admin or user
    if role == 'admin':
        tabs = st.tabs(['User Management','Upload Data','Reports & Branch Data','Application Logs'])
    else:
        tabs = st.tabs(['Upload Data','Reports & Branch Data'])
    # Unpack tabs
    idx = 0
    if role == 'admin':
        tab_users, tab_upload, tab_reports, tab_logs = tabs
    else:
        tab_upload, tab_reports = tabs

    # User Management
    if role == 'admin':
        with tab_users:
            st.header('User Management')
            df_users = pd.DataFrame.from_dict(credentials['usernames'], orient='index')
            df_disp = df_users[['name','role']]
            df_disp.index.name = 'username'
            st.dataframe(df_disp, use_container_width=True)

    # Upload Data
    with tab_upload:
        st.header('Upload Card Data')
        uploaded = st.file_uploader('Upload .xlsx/.xls/.csv', type=['xlsx','xls','csv'])
        if uploaded:
            df_new = pd.read_excel(uploaded, dtype=str) if uploaded.name.lower().endswith(('xlsx','xls')) else pd.read_csv(uploaded, dtype=str)
            df_new.columns = df_new.columns.str.strip()
            missing = [c for c in REQUIRED_COLUMNS if c not in df_new.columns]
            if missing:
                st.error(f'Missing columns: {missing}')
            else:
                st.dataframe(df_new.head(5), use_container_width=True)
                if st.button('Save to Master'):
                    df_new['Delivery Branch Code'] = df_new['Delivery Branch Code'].astype(str).str.strip()
                    df_new['Issuance Date'] = pd.to_datetime(df_new['Issuance Date'], errors='coerce', dayfirst=True)
                    df_new['Load Date'] = datetime.today().strftime('%Y-%m-%d')
                    master_df = load_master_data()
                    combined = pd.concat([master_df, df_new], ignore_index=True)
                    combined.drop_duplicates(subset=['Unmasked Card Number','Account Number','Delivery Branch Code'], inplace=True)
                    combined.to_excel(MASTER_FILE, index=False)
                    st.success('✅ Data saved successfully')
                    load_master_data.clear()
                    st.experimental_rerun()

    # Reports & Branch Data
    with tab_reports:
        st.header('Reports & Branch Data')
        df = load_master_data()
        if df.empty:
            st.info('No data.')
        else:
            term = st.text_input('🔍 Search by name, card, account')
            dff = df.copy()
            if term:
                mask = (
                    dff['Customer Name'].str.contains(term, case=False, na=False) |
                    dff['Unmasked Card Number'].str.contains(term, na=False) |
                    dff['Account Number'].str.contains(term, na=False)
                )
                dff = dff[mask]
            fr = st.date_input('From date', value=df['Issuance Date'].min(), min_value=df['Issuance Date'].min(), max_value=df['Issuance Date'].max())
            to = st.date_input('To date', value=df['Issuance Date'].max(), min_value=df['Issuance Date'].min(), max_value=df['Issuance Date'].max())
            res = dff[(dff['Issuance Date'] >= pd.to_datetime(fr)) & (dff['Issuance Date'] <= pd.to_datetime(to))]
            st.dataframe(res.reset_index(drop=True), use_container_width=True)

    # Application Logs
    if role=='admin':
        with tab_logs:
            st.header('Application Logs')
            if os.path.exists(LOG_FILE):
                logs = open(LOG_FILE).read()
                st.text_area('Logs', logs, height=400)
            else:
                st.info('No logs found.')
