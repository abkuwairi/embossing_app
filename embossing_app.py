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
REQUIRED_COLUMNS = [
    'Unmasked Card Number',
    'Customer Name',
    'Account Number',
    'Issuance Date',
    'Delivery Branch Code'
]

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# Set up logging
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
    # Default credentials (for demo only)
    defaults = {
        'usernames': {
            'admin_user': {'name': 'Admin', 'password': None, 'role': 'admin'},
            'branch101': {'name': 'Branch101', 'password': None, 'role': 'viewer'},
            'branch102': {'name': 'Branch102', 'password': None, 'role': 'viewer'}
        }
    }
    plain = {'admin_user': 'admin123', 'branch101': 'b101', 'branch102': 'b102'}
    for u, info in defaults['usernames'].items():
        info['password'] = stauth.Hasher([plain[u]]).generate()[0]
    with open(CRED_FILE, 'w') as f:
        json.dump(defaults, f, indent=4)
    return defaults

credentials = load_credentials()
active = {
    u: {'name': v['name'], 'password': v['password']}
    for u, v in credentials['usernames'].items()
}
auth = stauth.Authenticate(
    {'usernames': active},
    cookie_name='card_app_cookie',
    key='secure_and_unique_key',
    cookie_expiry_days=1
)

# ------------------ Data Loading ------------------
@st.cache_data(show_spinner=False)
def load_master_data() -> pd.DataFrame:
    """
    Load and cache the master dataset.
    """
    if os.path.exists(MASTER_FILE):
        df = pd.read_excel(MASTER_FILE, dtype=str)
        df.columns = df.columns.str.strip()
        df['Delivery Branch Code'] = df['Delivery Branch Code'].astype(str).str.strip()
        # Ensure date parsing
        df['Issuance Date'] = pd.to_datetime(df['Issuance Date'], errors='coerce')
        return df
    # Return empty structure
    cols = REQUIRED_COLUMNS + ['Load Date']
    return pd.DataFrame(columns=cols)

# ------------------ UI ------------------
st.set_page_config(page_title='Card Management', layout='wide')
name, status, username = auth.login('🔐 Login', 'main')
if status is False:
    st.error('❌ Invalid credentials')
elif status is None:
    st.warning('👈 Please login to continue')
else:
    auth.logout('Logout', 'sidebar')
    st.sidebar.success(f'Welcome {name}')

    # Main Tabs
    tab_upload, tab_reports = st.tabs(['📤 Upload Data', '📊 Reports & Analytics'])

    # Upload Tab
    with tab_upload:
        st.header('📤 Upload Card Data')
        uploaded = st.file_uploader(
            'Upload .xlsx, .xls or .csv',
            type=['xlsx', 'xls', 'csv'],
            help='Ensure columns: ' + ', '.join(REQUIRED_COLUMNS)
        )
        if uploaded:
            try:
                if uploaded.name.lower().endswith(('xlsx', 'xls')):
                    df_new = pd.read_excel(uploaded, dtype=str)
                else:
                    df_new = pd.read_csv(uploaded, dtype=str)
                df_new.columns = df_new.columns.str.strip()
                missing = [c for c in REQUIRED_COLUMNS if c not in df_new.columns]
                if missing:
                    st.error(f'Missing columns: {missing}')
                else:
                    # Preview
                    st.subheader('Preview of Uploaded Data')
                    st.dataframe(df_new.head(5), use_container_width=True)

                    if st.button('Save to Master'):
                        # Clean
                        df_new['Delivery Branch Code'] = df_new['Delivery Branch Code'].astype(str).str.strip()
                        df_new['Issuance Date'] = pd.to_datetime(
                            df_new['Issuance Date'], errors='coerce', dayfirst=True
                        )
                        df_new['Load Date'] = datetime.today().strftime('%Y-%m-%d')

                        master = load_master_data()
                        # Remove duplicates
                        combined = pd.concat([master, df_new], ignore_index=True)
                        combined.drop_duplicates(
                            subset=['Unmasked Card Number', 'Account Number', 'Delivery Branch Code'],
                            inplace=True
                        )
                        combined.to_excel(MASTER_FILE, index=False)
                        st.success('✅ Data saved successfully')
                        logging.info(f"{username} saved {len(df_new)} rows")
                        load_master_data.clear()
            except Exception as e:
                st.error(f'❌ Error: {e}')

    # Reports Tab
    with tab_reports:
        st.header('📊 Reports & Branch Data')
        df_all = load_master_data()
        if df_all.empty:
            st.info('No data available. Please upload first.')
        else:
            # Analytics: count by branch
            counts = df_all.groupby('Delivery Branch Code').size().reset_index(name='Count')
            st.subheader('Cards per Branch')
            st.dataframe(counts, use_container_width=True)

            # Branch filter selector
            branches = sorted(df_all['Delivery Branch Code'].unique())
            selected = st.multiselect('Select Branch(es)', branches, default=branches)
            view = df_all[df_all['Delivery Branch Code'].isin(selected)]

            # Date range
            min_d, max_d = view['Issuance Date'].min(), view['Issuance Date'].max()
            start, end = st.date_input('Date range', [min_d, max_d], min_value=min_d, max_value=max_d)
            mask = view['Issuance Date'].between(pd.to_datetime(start), pd.to_datetime(end))
            view = view[mask]

            # Display data
            st.subheader('Filtered Data')
            st.dataframe(view, use_container_width=True)

            # Download
            now = datetime.now().strftime('%Y%m%d_%H%M%S')
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                view.to_excel(writer, index=False, sheet_name='Data')
            buf.seek(0)
            st.download_button(
                label=f'⬇️ Download Export ({now})',
                data=buf,
                file_name=f'cards_export_{now}.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
