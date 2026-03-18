import psycopg2
import psycopg2.extras
import pandas as pd
from typing import Optional, Tuple
# import streamlit as st
from constants import HOST, PORT, DATABASE, USER, PASSWORD

# ── DB CONFIG ──────────────────────────────────────────────────────────────────
DB_CONFIG = {
    "host":     HOST,           # ← change this
    "port":     PORT,           # ← change this``
    "database": DATABASE,       # ← change this
    "user":     USER,            # ← change this
    "password": PASSWORD,        # ← change this
}


# ── TABLE SCHEMA (used in the LLM prompt) ─────────────────────────────────────
TABLE_SCHEMA = """
You are an expert PostgreSQL query generator. The database contains MGNREGA (India rural employment scheme) data.

== TABLES & COLUMNS ==

1. Category_wise_Household_Workers_<YEAR>
   (years: 2018_2019, 2019_2020, 2020_2021, 2021_2022, 2022_2023, 2023_2024, 2024_2025, 2025_2026)
   Columns:
     "s.no"                          - row number (IMPORTANT: must always be quoted as "s.no" in SQL)
     state                           - state / UT name
     jobcards___applied_for          - job cards applied (lakhs)
     jobcards___issued               - job cards issued (lakhs)
     registered_workers___scs        - SC registered workers (lakhs)
     registered_workers___sts        - ST registered workers (lakhs)
     registered_workers___others     - Other registered workers (lakhs)
     registered_workers___total_workers - total registered workers (lakhs)
     registered_workers___women      - women registered workers (lakhs)
     active_workers___scs            - SC active workers (lakhs)
     active_workers___sts            - ST active workers (lakhs)
     active_workers___others         - other active workers (lakhs)
     active_workers___total_workers  - total active workers (lakhs)
     active_workers___women          - women active workers (lakhs)

   NOTE: The first data row ("s.no" = '1', state = '2') contains column header labels — skip it.
         The row where state = 'Total' contains national totals.

2. Total_No_of_Aadhaar_Nos_Entered_for_MGNREGA_<YEAR>
   (years: 2020_2021 … 2025_2026)
   Columns:
     state, total_workers, aadhaar_seeded_count, aadhaar_seeded_percent,
     uidai_sent_count, uidai_sent_percent, auth_success_count, auth_success_percent,
     npci_sent_count, npci_sent_percent, npci_success_active_count, npci_success_active_percent,
     inactive_bank_count, inactive_bank_percent, account_not_mapped_count,
     account_not_mapped_percent, total_failure

   NOTE: The first row (state = '2') contains column header labels — skip it.
         To skip it use: WHERE state != '2'

3. jobcard_not_issued_<YEAR>
   (years: 2018_2019 … 2025_2026)
   Columns:
     s_no, state, registered_households

== RULES ==
- Always use double-quoted table names, e.g. "Category_wise_Household_Workers_2020_2021"
- The column named s.no MUST always be written as "s.no" (with double quotes) in every query — never as s.no unquoted, as PostgreSQL will treat the dot as a table alias separator and throw an error.
- Filter out header/total rows from Category_wise tables: WHERE state NOT IN ('2', 'Total', 'State') AND "s.no" != '1'
- Filter out header rows from Aadhaar tables: WHERE state NOT IN ('2', 'Total', 'State')
- For jobcard_not_issued tables there is no header row to skip.
- Numeric columns are stored as TEXT — cast with CAST(col AS NUMERIC) when doing arithmetic.
- Return only the SQL query — no explanation, no markdown fences.
"""


# ── CONNECTION ─────────────────────────────────────────────────────────────────
@st.cache_resource
def get_connection():
    """Return a persistent psycopg2 connection (cached by Streamlit)."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        return conn
    except Exception as e:
        st.error(f"❌ Database connection failed: {e}")
        return None


# ── QUERY RUNNER ───────────────────────────────────────────────────────────────
def run_query(sql: str) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Execute *sql* and return (DataFrame, None) on success
    or (None, error_message) on failure.
    """
    conn = get_connection()
    if conn is None:
        return None, "No database connection."
    try:
        df = pd.read_sql_query(sql, conn)
        return df, None
    except Exception as e:
        # Attempt reconnect once
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            conn.autocommit = True
            df = pd.read_sql_query(sql, conn)
            return df, None
        except Exception as e2:
            return None, str(e2)


# ── TABLE LIST ─────────────────────────────────────────────────────────────────
def get_table_list() -> list[str]:
    """Return all table names in the public schema."""
    conn = get_connection()
    if conn is None:
        return []
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;"
        )
        return [row[0] for row in cur.fetchall()]
    except Exception:
        return []
