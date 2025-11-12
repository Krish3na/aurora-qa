import time
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import httpx
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


MESSAGES_URL = "https://november7-730026606190.europe-west1.run.app/messages/"
CACHE_TTL_SECONDS = 15 * 60


@dataclass
class RetrievedMessage:
	text: str
	score: float
	meta: Dict[str, Any]


class MessagesRetriever:
	def __init__(self) -> None:
		self._vectorizer: TfidfVectorizer | None = None
		self._matrix = None
		self._docs: List[Dict[str, Any]] = []
		self._last_refresh: float = 0.0

	def _should_refresh(self) -> bool:
		return (time.time() - self._last_refresh) > CACHE_TTL_SECONDS or self._matrix is None

	async def _fetch_messages(self) -> List[Dict[str, Any]]:
		async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
			resp = await client.get(MESSAGES_URL)
			resp.raise_for_status()
			data = resp.json()
			# The API may return either a list or an envelope with {"total": ..., "items": [...]}
			if isinstance(data, dict) and isinstance(data.get("items"), list):
				return data["items"]
			if isinstance(data, list):
				return data
			raise ValueError("Unexpected response format from messages API")

	def _build_corpus(self, messages: List[Dict[str, Any]]) -> Tuple[List[str], List[Dict[str, Any]]]:
		corpus: List[str] = []
		docs: List[Dict[str, Any]] = []
		for msg in messages:
			member_name = str(msg.get("user_name") or msg.get("member_name") or msg.get("member") or "")
			content = str(msg.get("message") or msg.get("content") or "")
			title = str(msg.get("title") or "")
			joined = " ".join([member_name, title, content]).strip()
			if not joined:
				continue
			corpus.append(joined)
			docs.append(msg)
		return corpus, docs

	async def refresh(self) -> None:
		messages = await self._fetch_messages()
		corpus, docs = self._build_corpus(messages)
		vectorizer = TfidfVectorizer(stop_words="english", max_features=50_000, ngram_range=(1, 2))
		matrix = vectorizer.fit_transform(corpus) if corpus else None
		self._vectorizer = vectorizer
		self._matrix = matrix
		self._docs = docs
		self._last_refresh = time.time()

	async def retrieve(self, question: str, top_k: int = 5) -> List[RetrievedMessage]:
		if self._should_refresh():
			await self.refresh()
		if not question or self._matrix is None or self._vectorizer is None or self._matrix.shape[0] == 0:
			return []
		q_vec = self._vectorizer.transform([question])
		scores = cosine_similarity(q_vec, self._matrix)[0]
		ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
		results: List[RetrievedMessage] = []
		for idx, score in ranked:
			doc = self._docs[idx]
			text = " ".join(
				str(x)
				for x in [
					doc.get("user_name") or doc.get("member_name") or doc.get("member") or "",
					doc.get("title") or "",
					doc.get("message") or doc.get("content") or "",
				]
				if x
			)
			results.append(RetrievedMessage(text=text, score=float(score), meta=doc))
		return results


