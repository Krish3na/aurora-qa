import time
from dataclasses import dataclass
import httpx
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

MESSAGES_URL = "https://november7-730026606190.europe-west1.run.app/messages/"
CACHE_TTL_SECONDS = 15 * 60  # Refresh every 15 minutes

@dataclass
class RetrievedMessage:
    text: str
    score: float
    meta: dict

class MessagesRetriever:
    def __init__(self):
        self._vectorizer = None
        self._matrix = None
        self._docs = []
        self._last_refresh = 0.0

    def _should_refresh(self):
        # print("Checking if we should refresh cache...")
        # always refresh if it's too old or matrix is None
        return (time.time() - self._last_refresh) > CACHE_TTL_SECONDS or self._matrix is None

    async def _fetch_messages(self):
        # print("Fetching messages from public API...")
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(MESSAGES_URL)
            resp.raise_for_status()
            data = resp.json()
            # The API may return either a list or an envelope with items
            if isinstance(data, dict) and isinstance(data.get("items"), list):
                return data["items"]
            if isinstance(data, list):
                return data
            raise ValueError("Unexpected response format from messages API")

    def _build_corpus(self, messages):
        corpus = []
        docs = []
        for msg in messages:
            member_name = str(msg.get("user_name", ""))
            content = str(msg.get("message", ""))
            if not content.strip():
                continue
            joined = f"{member_name} {content}".strip()
            corpus.append(joined)
            docs.append(msg)
        # print(f"Corpus constructed, {len(corpus)} docs")
        return corpus, docs

    async def refresh(self):
        messages = await self._fetch_messages()
        corpus, docs = self._build_corpus(messages)
        # Fit TF-IDF model
        vectorizer = TfidfVectorizer(stop_words="english", max_features=50000, ngram_range=(1, 2))
        matrix = vectorizer.fit_transform(corpus) if corpus else None
        self._vectorizer = vectorizer
        self._matrix = matrix
        self._docs = docs
        self._last_refresh = time.time()
        # print("Retriever cache refreshed!")

    async def retrieve(self, question, top_k=5):
        if self._should_refresh():
            await self.refresh()
        if not question or self._matrix is None or self._vectorizer is None or self._matrix.shape[0] == 0:
            return []
        # print(f"Looking up answers for: {question}")
        q_vec = self._vectorizer.transform([question])
        scores = cosine_similarity(q_vec, self._matrix)[0]
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
        results = []
        for idx, score in ranked:
            doc = self._docs[idx]
            text = " ".join(
                str(x) for x in [doc.get("user_name", ""), doc.get("message", "")] if x
            )
            # print(f"Candidate: {text} (score={score:.3f})")
            results.append(RetrievedMessage(text=text, score=float(score), meta=doc))
        return results


