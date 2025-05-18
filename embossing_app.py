import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# --- إعداد قاعدة البيانات (SQLite) ---
conn = sqlite3.connect('cards.db', check_same_thread=False)
c = conn.cursor()
c.execute('''
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_number TEXT UNIQUE,
    account_number TEXT,
    customer_name TEXT,
    expiry_date TEXT,
    issuance_date TEXT,
    branch_code TEXT,
    imported_at TEXT
)
''')
conn.commit()

st.title("نظام تسليم البطاقات – نموذج أولي")

# --- رفع الملف اليومي ---
uploaded_file = st.file_uploader("Upload CSV or XLSX", type=['csv', 'xlsx'])
if uploaded_file:
    if uploaded_file.name.lower().endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
    st.subheader("معاينة البيانات")
    st.dataframe(df.head())

    if st.button("استيراد إلى قاعدة البيانات"):
        for _, row in df.iterrows():
            # تأكد من أن أسماء الأعمدة في ملفك تتطابق مع الأسماء هنا
            c.execute('''
                INSERT OR REPLACE INTO cards
                (card_number, account_number, customer_name, expiry_date, issuance_date, branch_code, imported_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                str(row['Unmasked Card Number']),
                str(row['Account Number']),
                row.get('Customer Name',''),
                str(row['Expiry Date']),
                str(row['Issuance Date']),
                str(row['Delivery Branch Code']),
                datetime.now().isoformat()
            ))
        conn.commit()
        st.success("تم الاستيراد بنجاح!")

# --- قسم البحث والتقارير ---
st.markdown("---")
st.subheader("بحث في البطاقات")
col = st.selectbox("Search by", ['card_number','account_number'], format_func=lambda x: 'رقم البطاقة' if x=='card_number' else 'رقم الحساب')
val = st.text_input("أدخل القيمة")
date_from = st.date_input("من تاريخ:", datetime.today())
date_to   = st.date_input("إلى تاريخ:", datetime.today())

if st.button("بحث"):
    query = f"""
      SELECT card_number AS 'رقم البطاقة',
             account_number AS 'رقم الحساب',
             customer_name AS 'اسم العميل',
             expiry_date AS 'تاريخ الانتهاء',
             issuance_date AS 'تاريخ الإصدار',
             branch_code AS 'رمز الفرع'
      FROM cards
      WHERE {col} = ?
        AND date(issuance_date) BETWEEN date(?) AND date(?)
      ORDER BY issuance_date DESC
    """
    results = pd.read_sql(query, conn, params=(val, date_from, date_to))
    st.dataframe(results)
