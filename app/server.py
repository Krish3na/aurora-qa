from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Query

from .retriever import MessagesRetriever
from .qa import answer_question

retriever = MessagesRetriever()


@asynccontextmanager
async def lifespan(app: FastAPI):
	try:
		await retriever.refresh()
	except Exception:
		pass
	yield


app = FastAPI(title="Member QA Service", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> Dict[str, Any]:
	return {"status": "ok"}


@app.get("/ask")
async def ask(question: str = Query(..., description="Natural language question")) -> Dict[str, str]:
	if not question or not question.strip():
		raise HTTPException(status_code=400, detail="Question must not be empty")
	results = await retriever.retrieve(question, top_k=6)
	answer = answer_question(question, results)
	return {"answer": answer}


