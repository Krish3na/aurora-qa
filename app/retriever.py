import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path

from .fetch_all_messages import fetch_all
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

CACHE_TTL_SECONDS = 30 * 60  # Refresh every 30 minutes (read-heavy cache)
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
LOCAL_DUMP = DATA_DIR / "messages_fetch_full.json"
FALLBACK_DUMP = DATA_DIR / "messages_full.json"
SAMPLE_DUMP = DATA_DIR / "messages.json"


@dataclass
class RetrievedMessage:
    text: str
    score: float
    meta: dict


def _load_messages_from(path: Path):
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data["items"]
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    return []


def _load_local_messages(prefer_primary=True):
    sources = [LOCAL_DUMP, FALLBACK_DUMP, SAMPLE_DUMP] if prefer_primary else [FALLBACK_DUMP, LOCAL_DUMP, SAMPLE_DUMP]
    for path in sources:
        data = _load_messages_from(path)
        if data:
            return data
    return []


class MessagesRetriever:
    def __init__(self):
        self._vectorizer = None
        self._matrix = None
        self._docs = []
        self._last_refresh = 0.0

    def _should_refresh(self):
        # print("Checking if we should refresh cache...")
        return (time.time() - self._last_refresh) > CACHE_TTL_SECONDS or self._matrix is None

    def _build_model(self, messages):
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
        vectorizer = TfidfVectorizer(stop_words="english", max_features=50000, ngram_range=(1, 2))
        matrix = vectorizer.fit_transform(corpus) if corpus else None
        self._vectorizer = vectorizer
        self._matrix = matrix
        self._docs = docs

    async def refresh(self):
        # Load whatever data we already have before fetching to avoid empty responses
        cached_messages = _load_local_messages()
        if cached_messages:
            self._build_model(cached_messages)

        try:
            await asyncio.to_thread(fetch_all, limit=100, delay=1)
        except Exception as exc:
            print(f"fetch_all failed: {exc}")

        messages = _load_local_messages()
        if messages:
            self._build_model(messages)

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


