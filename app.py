import streamlit as st
import pandas as pd
from main import generate_sql
from db import run_query, get_table_list

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