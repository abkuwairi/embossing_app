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
    defaults = {
        'usernames': {
            'admin_user': {'name': 'Admin', 'password': None, 'role': 'admin', 'branch_code': ''},
            'branch101': {'name': 'Branch101', 'password': None, 'role': 'viewer', 'branch_code': '101'},
            'branch102': {'name': 'Branch102', 'password': None, 'role': 'viewer', 'branch_code': '102'}
        }
    }
    plain = {'admin_user': 'admin123', 'branch101': 'b101', 'branch102': 'b102'}
    for u, info in defaults['usernames'].items():
        info['password'] = stauth.Hasher([plain[u]]).generate()[0]
    with open(CRED_FILE, 'w') as f:
        json.dump(defaults, f, indent=4)
    return defaults

credentials = load_credentials()
active = {u: {'name': i['name'], 'password': i['password']} for u,i in credentials['usernames'].items()}
auth = stauth.Authenticate({'usernames': active}, cookie_name='cookie', key='key', cookie_expiry_days=1)

# ------------------ Data Loading ------------------
def load_master_data():
    if os.path.exists(MASTER_FILE):
        df = pd.read_excel(MASTER_FILE, dtype=str)
        df.columns = df.columns.str.strip()
        df['Delivery Branch Code'] = df['Delivery Branch Code'].astype(str).str.strip()
        return df
    return pd.DataFrame(columns=REQUIRED_COLUMNS + ['Load Date'])

# ------------------ UI ------------------
name, status, user = auth.login('🔐 Login', 'main')
if status is False:
    st.error('Invalid credentials')
elif status is None:
    st.warning('Please login')
else:
    auth.logout('Logout', 'sidebar')
    st.sidebar.success(f'Welcome {name}')

    # Card Reports
    st.header('📊 Card Reports')
    upload = st.file_uploader('Upload Excel/CSV', type=['xlsx','xls','csv'])
    if upload:
        df_new = pd.read_excel(upload, dtype=str) if upload.name.endswith(('xlsx','xls')) else pd.read_csv(upload, dtype=str)
        df_new.columns = df_new.columns.str.strip()
        missing = [c for c in REQUIRED_COLUMNS if c not in df_new.columns]
        if missing:
            st.error(f'Missing columns: {missing}')
        else:
            df_new['Delivery Branch Code'] = df_new['Delivery Branch Code'].astype(str).str.strip()
            df_new['Load Date'] = datetime.today().strftime('%Y-%m-%d')
            df_master = load_master_data()
            pd.concat([df_master, df_new], ignore_index=True).to_excel(MASTER_FILE, index=False)
            st.success('Data saved')

    # Display raw data by branch without filters
    df_all = load_master_data()
    if df_all.empty:
        st.info('No data available')
    else:
        branches = sorted(df_all['Delivery Branch Code'].unique())
        for b in branches:
            df_b = df_all[df_all['Delivery Branch Code'] == b]
            with st.expander(f'Branch {b} ({len(df_b)} rows)'):
                st.dataframe(df_b, use_container_width=True)
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='xlsxwriter') as w:
                    df_b.to_excel(w, index=False)
                buf.seek(0)
                st.download_button('Download', buf, file_name=f'branch_{b}.xlsx')
