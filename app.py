import streamlit as st
import pandas as pd
# from main import generate_sql
# from db import run_query, get_table_list
import psycopg2
import psycopg2.extras
import pandas as pd
from typing import Optional, Tuple

import os
from dotenv import load_dotenv
load_dotenv()
# from streamlit import st

HOST = os.getenv("HOST")
PORT = os.getenv("PORT")
DATABASE = os.getenv("DATABASE")
USER = os.getenv("USER")
PASSWORD = os.getenv("PASSWORD")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# HOST = st.secrets["HOST"]
# PORT = st.secrets["PORT"]
# DATABASE = st.secrets["DATABASE"]
# USER =  st.secrets["USER"]
# PASSWORD = st.secrets["PASSWORD"]
# OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

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

from openai import OpenAI
# from db import TABLE_SCHEMA
import streamlit as st
# from constants import OPENAI_API_KEY, HOST, PORT, DATABASE, USER, PASSWORD

# ── CLIENT ─────────────────────────────────────────────────────────────────────
@st.cache_resource
def get_openai_client():
    api_key = OPENAI_API_KEY
    if not api_key:
        st.error("❌ OPENAI_API_KEY not found in Streamlit secrets.")
        return None
    return OpenAI(api_key=api_key)


# ── TEXT → SQL ─────────────────────────────────────────────────────────────────
def generate_sql(natural_language_query: str) -> tuple[str | None, str | None]:
    """
    Convert *natural_language_query* to a PostgreSQL SELECT statement.
    Returns (sql_string, None) or (None, error_message).

    Model choice: gpt-4o
      • Best accuracy for complex schema understanding & SQL generation
      • Understands table-naming conventions, quoting rules, type casting
      • Faster & cheaper than o1/o3 while still highly capable for SQL tasks
    """
    client = get_openai_client()
    if client is None:
        return None, "OpenAI client not initialised."

    system_prompt = (
        TABLE_SCHEMA
        + "\n\nGenerate a valid PostgreSQL SELECT query for the user's question. "
        "Output ONLY the raw SQL — no markdown, no explanation."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",          # Best accuracy for SQL generation tasks
            temperature=0,           # Deterministic output for SQL
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": natural_language_query},
            ],
        )
        sql = response.choices[0].message.content.strip()
        # Strip accidental markdown code fences
        if sql.startswith("```"):
            sql = sql.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        return sql, None
    except Exception as e:
        return None, str(e)

def format_table_name(table_name: str) -> str:
    parts = table_name.split("_")

    # Extract year if present
    if parts[-1].isdigit() and parts[-2].isdigit():
        year = f"{parts[-2]}–{parts[-1]}"
        name_parts = parts[:-2]
    else:
        year = ""
        name_parts = parts

    # Convert to readable text
    readable_name = " ".join(name_parts)

    # Capitalize nicely
    readable_name = readable_name.title()

    # Add year back
    if year:
        return f"{readable_name} ({year})"
    return readable_name

# ── PAGE CONFIG ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MGNREGA Text-to-SQL",
    page_icon="🔍",
    layout="wide",
)

# ── CUSTOM CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .sql-box {
        background: #1e1e2e;
        color: #cdd6f4;
        padding: 1rem 1.2rem;
        border-radius: 8px;
        font-family: 'Courier New', monospace;
        font-size: 0.9rem;
        white-space: pre-wrap;
        overflow-x: auto;
    }
    .metric-card {
        background: #f0f4ff;
        border-left: 4px solid #4c6ef5;
        padding: 0.6rem 1rem;
        border-radius: 6px;
        margin-bottom: 0.5rem;
    }
    .stTextArea textarea { font-size: 1rem; }
</style>
""", unsafe_allow_html=True)

# ── HEADER ─────────────────────────────────────────────────────────────────────
st.title("🔍 MGNREGA Text-to-SQL Explorer")
st.caption("Ask questions in plain English — get live data from your PostgreSQL database.")

# ── SIDEBAR ────────────────────────────────────────────────────────────────────
# with st.sidebar:
#     st.header("📋 Database Tables")
#     tables = get_table_list()
#     if tables:
#         st.success(f"{len(tables)} tables found")
#         for t in tables:
#             st.markdown(f"- `{t}`")
#     else:
#         st.warning("Could not load table list. Check DB connection.")

#     st.divider()
#     st.markdown("**Model:** `gpt-4o`")
#     st.markdown("**DB:** PostgreSQL 16")
#     st.markdown("**Schema:** MGNREGA India")

with st.sidebar:
    st.header("📋 Database Tables")

    tables = get_table_list()

    if tables:
        # 🔹 Extract unique year ranges from table names
        years = set()
        for t in tables:
            parts = t.split("_")
            for i in range(len(parts)-1):
                if parts[i].isdigit() and parts[i+1].isdigit():
                    years.add(f"{parts[i]}-{parts[i+1]}")

        years = sorted(list(years))

        # 🔽 Dropdown
        selected_year = st.selectbox(
            "📅 Select Year Range",
            ["All"] + years
        )

        # 🔹 Filter tables
        if selected_year != "All":
            start, end = selected_year.split("-")
            filtered_tables = [
                t for t in tables if f"{start}_{end}" in t
            ]
        else:
            filtered_tables = tables

        st.success(f"{len(filtered_tables)} tables found")

        for t in filtered_tables:
            # st.markdown(f"- `{t}`")
            pretty_name = format_table_name(t)
            st.markdown(
                f"<span style='color:#FFA500;'> {pretty_name}</span>",
                unsafe_allow_html=True
            )

    else:
        st.warning("Could not load table list. Check DB connection.")

# ── EXAMPLE QUERIES ────────────────────────────────────────────────────────────
EXAMPLES = [
    "Which 5 states had the most active women workers in 2022-2023?",
    "Show total registered SC workers by state for 2023-2024",
    "Which states have more than 10 lakh registered ST workers in 2021-2022?",
    "List states where Aadhaar seeding is below 80% in 2022-2023",
    "Show job cards issued vs applied for Bihar across all years",
    "Which state had the highest number of households not issued job cards in 2020-2021?",
]

if "run_query_flag" not in st.session_state:
    st.session_state.run_query_flag = False
    
st.subheader("💡 Example Questions")
cols = st.columns(3)
selected_example = None
# for i, ex in enumerate(EXAMPLES):
#     if cols[i % 3].button(ex, key=f"ex_{i}", use_container_width=True):
#         selected_example = ex

for i, ex in enumerate(EXAMPLES):
    if cols[i % 3].button(ex, key=f"ex_{i}", use_container_width=True):
        st.session_state.user_query = ex
        st.session_state.run_query_flag = True

# ── MAIN INPUT ─────────────────────────────────────────────────────────────────
st.subheader("✍️ Your Question")
default_val = selected_example if selected_example else ""
user_query = st.text_area(
    label="Ask anything about MGNREGA data:",
    # value=default_val,
    value=st.session_state.get("user_query", ""),
    height=80,
    placeholder="e.g. Which state has the highest number of active workers in 2023-2024?",
)

run_btn = st.button("🚀 Generate SQL & Fetch Data", type="primary", use_container_width=True)

if run_btn:
    st.session_state.run_query_flag = True

# ── HISTORY ────────────────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []   # list of {question, sql, rows, error}

# ── EXECUTION ──────────────────────────────────────────────────────────────────
# if run_btn and user_query.strip():
if st.session_state.run_query_flag and user_query.strip():
    with st.spinner("🤖 Generating SQL with GPT-4o…"):
        sql, gen_error = generate_sql(user_query.strip())

    if gen_error:
        st.error(f"SQL generation failed: {gen_error}")
    else:
        st.subheader("📝 Generated SQL")
        st.markdown(f'<div class="sql-box">{sql}</div>', unsafe_allow_html=True)

        # Allow manual edit before running
        edited_sql = st.text_area("✏️ Edit SQL if needed:", value=sql, height=120, key="edited_sql")

        with st.spinner("⚙️ Executing query…"):
            df, exec_error = run_query(edited_sql)

        if exec_error:
            st.error(f"Query execution failed: {exec_error}")
            st.session_state.history.append(
                {"question": user_query, "sql": sql, "df": None, "error": exec_error}
            )
        else:
            # ── RESULTS ────────────────────────────────────────────────────────
            st.subheader("📊 Results")
            row_count = len(df)
            col_count = len(df.columns)

            m1, m2 = st.columns(2)
            m1.metric("Rows returned", row_count)
            m2.metric("Columns", col_count)

            if row_count == 0:
                st.info("Query executed successfully but returned no rows.")
            else:
                # Numeric conversion for better display
                for col in df.columns:
                    try:
                        df[col] = pd.to_numeric(df[col])
                    except Exception:
                        pass

                tab1, tab2, tab3 = st.tabs(["📋 Table", "📈 Chart", "📥 Download"])

                with tab1:
                    st.dataframe(df, use_container_width=True, height=420)

                with tab2:
                    numeric_cols = df.select_dtypes(include="number").columns.tolist()
                    text_cols    = df.select_dtypes(exclude="number").columns.tolist()
                    if numeric_cols and text_cols:
                        x_col = st.selectbox("X axis (category)", text_cols, key="x_col")
                        y_col = st.selectbox("Y axis (value)", numeric_cols, key="y_col")
                        chart_type = st.radio("Chart type", ["Bar", "Line", "Area"], horizontal=True)
                        chart_df = df[[x_col, y_col]].set_index(x_col)
                        if chart_type == "Bar":
                            st.bar_chart(chart_df)
                        elif chart_type == "Line":
                            st.line_chart(chart_df)
                        else:
                            st.area_chart(chart_df)
                    else:
                        st.info("Need at least one text column and one numeric column to plot a chart.")

                with tab3:
                    csv = df.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        "⬇️ Download CSV",
                        data=csv,
                        file_name="query_results.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )

            st.session_state.history.append(
                {"question": user_query, "sql": sql, "df": df, "error": None}
            )

elif run_btn:
    st.warning("Please enter a question first.")

# ── QUERY HISTORY ──────────────────────────────────────────────────────────────
if st.session_state.history:
    st.divider()
    st.subheader("🕘 Query History")
    for i, item in enumerate(reversed(st.session_state.history)):
        label = f"Q{len(st.session_state.history) - i}: {item['question'][:80]}…"
        with st.expander(label):
            st.markdown(f'<div class="sql-box">{item["sql"]}</div>', unsafe_allow_html=True)
            if item["error"]:
                st.error(item["error"])
            elif item["df"] is not None:
                st.dataframe(item["df"], use_container_width=True)
