from fastapi import FastAPI
from search import search

app = FastAPI(title="Coach Search API")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/search")
def search_endpoint(q: str, method: str = "hybrid"):
    return search(q, method)