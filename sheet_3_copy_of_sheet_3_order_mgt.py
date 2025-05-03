import pandas as pd
import re
from datetime import datetime
import gspread
import numpy as np
from oauth2client.service_account import ServiceAccountCredentials
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
import pytz

# Supabase PostgreSQL credentials
user = "postgres.flidrqugtnmhnqspqthb"
password = "shanto8616"
host = "aws-0-ap-south-1.pooler.supabase.com"
port = 5432
database = "postgres"
sslmode = "require"

# SQLAlchemy engine
connection_string = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}?sslmode={sslmode}"
try:
    engine = create_engine(connection_string)
    with engine.connect() as conn:
        print("✅ Connected to Supabase PostgreSQL")
except OperationalError as e:
    print(f"❌ Connection failed: {e}")

# --- Connect to Google Sheet ---
sheet_id_1 = "1Rz5ctnSMSh_UGmhYkE_jX6zYGCabz28BEHaNnfbRn0I"
sheet_name_1 = "Sheet1"
csv_url_1 = f"https://docs.google.com/spreadsheets/d/{sheet_id_1}/gviz/tq?tqx=out:csv&sheet={sheet_name_1}"

def load_data(csv_url):
    try:
        df = pd.read_csv(csv_url, low_memory=False)
        df.columns = [clean_column_name(col) for col in df.columns]
        df = df.fillna('')
        if df.columns[0] != 'OA':
            df.rename(columns={df.columns[0]: 'OA'}, inplace=True)
        return df
    except Exception as e:
        print(f"Error loading data: {e}")
        return None

def clean_column_name(col_name):
    col_name = col_name.strip()
    col_name = re.sub(r'[^A-Za-z0-9_]+', '', col_name)
    return col_name.replace(' ', '_').replace('-', '_')

df_1 = load_data(csv_url_1)
print("Data from Sheet 1 (first 5 rows):")
print(df_1.head())
df_1['ReleaseDate'] = pd.to_datetime(df_1['ReleaseDate'], errors='coerce')

# Get today's date and first day of this month
today = pd.Timestamp.today().normalize()
start_of_month = today.replace(day=1)

# Filter MTD: from 1st of this month to today
df_mtd = df_1[(df_1['ReleaseDate'] >= start_of_month) & (df_1['ReleaseDate'] <= today)]

if df_mtd.empty:
    # No current-month data found → fallback to previous month
    last_day_prev_month = start_of_month - pd.Timedelta(days=1)
    start_prev_month = last_day_prev_month.replace(day=1)

    df_mtd = df_1[
        (df_1['ReleaseDate'] >= start_prev_month) &
        (df_1['ReleaseDate'] <= last_day_prev_month)
    ]


# --- Insert into Supabase PostgreSQL ---
def insert_data_to_supabase(df, table_name):
    try:
        # Clean datetime columns
        for col in df.columns:
            if df[col].dtype == 'object':
                try:
                    df[col] = pd.to_datetime(df[col], errors='raise')
                    print(f"Column '{col}' converted to datetime.")
                except:
                    continue

        dtype_mapping = {
            'object': 'TEXT',
            'int64': 'BIGINT',
            'float64': 'DOUBLE PRECISION',
            'bool': 'BOOLEAN',
            'datetime64[ns]': 'TIMESTAMP'
        }

        column_defs = []
        for col in df.columns:
            col_dtype = str(df[col].dtype)
            pg_type = dtype_mapping.get(col_dtype, 'TEXT')
            column_defs.append(f'"{col}" {pg_type}')

        # Drop and recreate table using SQLAlchemy text()
        with engine.begin() as conn:
            conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}"'))
            conn.execute(text(f'CREATE TABLE "{table_name}" ({", ".join(column_defs)})'))
            df.to_sql(table_name, con=conn, index=False, if_exists='append', method='multi')
            print(f"✅ Inserted {len(df)} rows into Supabase table '{table_name}'")
    except Exception as e:
        print(f"❌ Error inserting to Supabase: {e}")

if df_mtd is not None:
    insert_data_to_supabase(df_mtd, 'order_relased')

# --- Fetch from Supabase ---
def fetch_from_supabase(query):
    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
            print("✅ Data fetched successfully.")
            return df
    except Exception as e:
        print(f"❌ Fetch error: {e}")
        return None

Sheet_3_order_MGT = fetch_from_supabase("""
    SELECT "OA", "Product", "Category", "Slider", SUM("QuantityPCS") AS "QuantityPCS", "ReleaseDate"
    FROM "order_relased"
    WHERE "ReleaseDate" BETWEEN DATE_TRUNC('month', CURRENT_DATE) AND CURRENT_DATE
    GROUP BY "OA", "Product", "Category", "Slider", "ReleaseDate"
    ORDER BY "ReleaseDate" DESC;
""")

Copy_Sheet_3_order_MGT = fetch_from_supabase("""
SELECT 
        "Category",
        tzp_numbers,
        "ReleaseDate",
        SUM("QuantityPCS") AS total
    FROM (
        SELECT 
            "OA",
            "Product",
            "Category",
            "Slider",
            "QuantityPCS",
            "ReleaseDate",
            "Salesperson",
            REGEXP_MATCHES("Slider", 'TZP-[0-9]+') AS tzp_numbers
        FROM "order_relased"
    ) AS new_tab
    WHERE "ReleaseDate" BETWEEN DATE_TRUNC('month', CURRENT_DATE) AND CURRENT_DATE
    GROUP BY "Category", tzp_numbers, "ReleaseDate"
    ORDER BY "ReleaseDate" DESC;


""")

# --- Google Sheet Pasting ---
def authenticate_google_sheets(json_credentials_file):
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.file"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(json_credentials_file, scope)
    return gspread.authorize(creds)

def paste_dataframe_to_sheet(sheet_id, worksheet_name, data_frame, credentials_file,
                             start_cell="A1", clear_before_paste=True,
                             clear_range=None, timestamp_cell=None,
                             include_headers=True):
    try:
        client = authenticate_google_sheets(credentials_file)
        sheet = client.open_by_key(sheet_id)
        worksheet = sheet.worksheet(worksheet_name)

        if clear_before_paste:
            if clear_range:
                worksheet.batch_clear([clear_range])
            else:
                worksheet.clear()

        # Convert 'ReleaseDate' column to datetime format if it exists
        if 'ReleaseDate' in data_frame.columns:
            data_frame['ReleaseDate'] = pd.to_datetime(data_frame['ReleaseDate'], errors='coerce')

        for col in data_frame.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns:
            # If the column is datetime, format it to 'YYYY-MM-DD HH:MM:SS'
            data_frame[col] = data_frame[col].dt.strftime('%Y-%m-%d %H:%M:%S')

        data_frame.replace([np.nan, pd.NaT], '', inplace=True)

        def format_cell(val):
            if pd.isna(val):
                return ''
            elif isinstance(val, (int, float)):
                return round(val, 4) if isinstance(val, float) else val
            return str(val)

        formatted_values = data_frame.applymap(format_cell).values.tolist()
        data = [data_frame.columns.tolist()] + formatted_values if include_headers else formatted_values

        worksheet.update(start_cell, data)

        if timestamp_cell:
            local_tz = pytz.timezone('Asia/Dhaka')
            local_time = datetime.now(local_tz).strftime("%Y-%m-%d %H:%M:%S")
            worksheet.update(timestamp_cell, [[local_time]])
            print(f"⏱️ Timestamp written to {timestamp_cell}: {local_time}")

        print(f"✅ Data pasted to '{worksheet_name}' at {start_cell}")

    except Exception as e:
        print(f"❌ Error pasting to Google Sheets: {e}")

# --- Paste Data ---
if Sheet_3_order_MGT is not None:
    paste_dataframe_to_sheet(
        sheet_id="1acV7UrmC8ogC54byMrKRTaD9i1b1Cf9QZ-H1qHU5ZZc",
        worksheet_name="Sheet3",
        data_frame=Sheet_3_order_MGT,
        credentials_file="gcreds.json",
        start_cell="A2",
        clear_before_paste=True,
        clear_range="A2:F",
        timestamp_cell="L2",
        include_headers=False
    )
else:
    print("❌ Sheet_3_order_MGT is None, skipping paste.")

if Copy_Sheet_3_order_MGT is not None:
    paste_dataframe_to_sheet(
        sheet_id="1acV7UrmC8ogC54byMrKRTaD9i1b1Cf9QZ-H1qHU5ZZc",
        worksheet_name="Copy of Sheet3",
        data_frame=Copy_Sheet_3_order_MGT,
        credentials_file="gcreds.json",
        start_cell="A2",
        clear_before_paste=True,
        clear_range="A2:D",
        timestamp_cell="H2",
        include_headers=False
    )
else:
    print("❌ Copy_Sheet_3_order_MGT is None, skipping paste.")
