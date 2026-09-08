"""Thin HTTP interface. The analyst endpoint arrives with the model integration."""

from fastapi import FastAPI

app = FastAPI(title="Premier League AI Evals POC", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
