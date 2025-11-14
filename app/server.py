from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from .retriever import MessagesRetriever
from .qa import answer_question

retriever = MessagesRetriever()

# Setup app lifespan (like FastAPI startup)
@asynccontextmanager
async def lifespan(app):
    try:
        # preload the retriever
        await retriever.refresh()
        # print("Retriever refreshed at startup")
    except Exception as e:
        # print(f"Retriever failed on startup: {e}")
        pass
    yield

# Main app
app = FastAPI(title="Aurora Member QA", version="0.1.0", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def root():
    # Serve the main HTML chat UI
    html_path = Path(__file__).parent / "templates" / "index.html"
    with open(html_path, "r", encoding="utf-8") as f:
        # print("Loaded UI template")
        return f.read()

@app.get("/health")
async def health():
    # Health endpoint for smoke tests
    return {"status": "ok"}

@app.get("/ask")
async def ask(question = Query(..., description="Natural language question")):
    # Defensive check for empty input
    if not question or not question.strip():
        raise HTTPException(status_code=400, detail="Question must not be empty")
    # print(f"Question asked: {question}")
    results = await retriever.retrieve(question, top_k=6)
    # print(f"Top candidates: {[x.text for x in results]}")
    answer = answer_question(question, results)
    # print(f"Answer produced: {answer}")
    return {"answer": answer}


