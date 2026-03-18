from openai import OpenAI
from db import TABLE_SCHEMA
# import streamlit as st
from constants import OPENAI_API_KEY, HOST, PORT, DATABASE, USER, PASSWORD

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
