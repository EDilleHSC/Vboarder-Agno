import psycopg2
from psycopg2 import sql

TABLES = {
    "agno_sessions": """
        CREATE TABLE IF NOT EXISTS agno_sessions (
            id SERIAL PRIMARY KEY,
            session_id TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """,
    "agno_memories": """
        CREATE TABLE IF NOT EXISTS agno_memories (
            id SERIAL PRIMARY KEY,
            session_id TEXT NOT NULL,
            memory TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """,
    "agno_metrics": """
        CREATE TABLE IF NOT EXISTS agno_metrics (
            id SERIAL PRIMARY KEY,
            session_id TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value FLOAT,
            recorded_at TIMESTAMP DEFAULT NOW()
        );
    """,
    "agno_knowledge": """
        CREATE TABLE IF NOT EXISTS agno_knowledge (
            id SERIAL PRIMARY KEY,
            topic TEXT NOT NULL,
            content TEXT,
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """,
    "agno_evals": """
        CREATE TABLE IF NOT EXISTS agno_evals (
            id SERIAL PRIMARY KEY,
            eval_name TEXT NOT NULL,
            result JSONB,
            run_at TIMESTAMP DEFAULT NOW()
        );
    """
}

import os


def connect():
    return psycopg2.connect(
        dbname=os.getenv("AGNO_DB_NAME", "ai"),
        user=os.getenv("AGNO_DB_USER", "ai"),
        password=os.getenv("AGNO_DB_PASSWORD", "ai"),  # pulled from env
        host=os.getenv("AGNO_DB_HOST", "localhost"),
        port=os.getenv("AGNO_DB_PORT", "5432")
    )

def init_tables():
    conn = connect()
    cur = conn.cursor()
    for name, ddl in TABLES.items():
        try:
            cur.execute(sql.SQL(ddl))
            print(f"✅ Created or verified: {name}")
        except Exception as e:
            print(f"❌ Error creating {name}: {e}")
    conn.commit()
    cur.close()
    conn.close()

if __name__ == "__main__":
    init_tables()
