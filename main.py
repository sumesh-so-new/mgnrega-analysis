from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from db import TABLE_SCHEMA
from constants import OPENAI_API_KEY

# ── APP ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="MGNREGA Text-to-SQL API",
    description="Converts natural language questions into PostgreSQL SELECT queries.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── CLIENT ─────────────────────────────────────────────────────────────────────
def get_openai_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not configured.")
    return OpenAI(api_key=OPENAI_API_KEY)


# ── SCHEMAS ────────────────────────────────────────────────────────────────────
class SQLRequest(BaseModel):
    query: str  # Natural language question from the user

class SQLResponse(BaseModel):
    sql: str    # Generated PostgreSQL SELECT statement


# ── ROUTES ─────────────────────────────────────────────────────────────────────
@app.get("/health")
def health_check():
    """Simple liveness probe."""
    return {"status": "ok"}


@app.post("/generate-sql", response_model=SQLResponse)
def generate_sql(request: SQLRequest) -> SQLResponse:
    """
    Convert a natural-language question into a PostgreSQL SELECT statement.

    - **query**: Plain-English question about MGNREGA data.

    Returns the raw SQL string ready to execute against the database.

    Model choice: gpt-4o
      • Best accuracy for complex schema understanding & SQL generation
      • Understands table-naming conventions, quoting rules, type casting
      • Faster & cheaper than o1/o3 while still highly capable for SQL tasks
    """
    if not request.query.strip():
        raise HTTPException(status_code=422, detail="Query must not be empty.")

    client = get_openai_client()

    system_prompt = (
        TABLE_SCHEMA
        + "\n\nGenerate a valid PostgreSQL SELECT query for the user's question. "
        "Output ONLY the raw SQL — no markdown, no explanation."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",     # Best accuracy for SQL generation tasks
            temperature=0,      # Deterministic output for SQL
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": request.query},
            ],
        )
        sql = response.choices[0].message.content.strip()

        # Strip accidental markdown code fences
        if sql.startswith("```"):
            sql = sql.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        return SQLResponse(sql=sql)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SQL generation failed: {str(e)}")
