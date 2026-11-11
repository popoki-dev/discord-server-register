from fastapi import FastAPI
from sqlalchemy import text

from app.database import engine

app = FastAPI(title="Discord Server Register")


@app.get("/health")
def health() -> dict:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}
