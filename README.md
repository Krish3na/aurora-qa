## Member QA Service (FastAPI)

A question-answering API that inspects member chatter from the public `/messages` endpoint and returns responses such as:

- “When is Layla planning her trip to London?”
- “How many cars does Vikram Desai have?”
- “What are Amira’s favorite restaurants?”

The implementation combines a TF-IDF retriever with lightweight heuristics for dates, numbers, and restaurant names. When extraction fails, the service returns the most relevant supporting message instead.

### Public Data Source

- Messages API: `https://november7-730026606190.europe-west1.run.app/messages`
- Docs: `https://november7-730026606190.europe-west1.run.app/docs#/default/get_messages_messages__get`

### API

- `GET /ask?question=...`  
  Response:
  ```json
  { "answer": "..." }
  ```
- `GET /health`

### Deliverables

- `/ask` endpoint that returns `{"answer": "..."}` in JSON.
- `/health` readiness endpoint.
- Render deployment using `aurora-qa` (see `render.yaml` and Dockerfile).
- Documentation in `README.md`, `EXPLANATION.md`, `NLP_BEGINNER_GUIDE.md`, `WHY_TFIDF_NOT_EMBEDDINGS.md`.
- Data analysis script `analyze_data.py` producing `data_insights.json`.
- Pytest suite (`test_api.py`) that exercises the HTTP endpoints.

### Examples

- “When is Layla planning her trip to London?”
- “How many cars does Vikram Desai have?”
- “What are Amira’s favorite restaurants?”

This service uses a TF‑IDF retriever on top of the messages, with light heuristics to extract dates, counts, and restaurant names for common question types. It falls back to returning the most relevant supporting message if no direct extraction succeeds.

---

## Local Development

1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   ```
2. Run the server:
   ```bash
   python main.py
   ```
3. Try the API:
   ```bash
   curl "http://localhost:8000/ask?question=When is Layla planning her trip to London?"
   ```
4. Access interactive docs at `http://localhost:8000/docs`
5. Run the data analyzer (saves `data_insights.json`):
   ```bash
   python analyze_data.py
   ```

---

## Testing

Run `pytest test_api.py` to exercise the `/health` and `/ask` flows. The test file includes print statements so you can see what scenario is running and verify that requests succeeded.

---

## Deployment (Render - Docker)

This repo includes a `Dockerfile` and `render.yaml` for a one-click Render deploy.

Steps:
1. Push this repo to GitHub.
2. In Render, create a new Web Service from your repo.
3. Choose Docker environment. Render will auto-detect `Dockerfile`.
4. Expose port `8000`. Health check path: `/health`.
5. Deploy. Your public URL will serve `/ask`.

Alternative hosts (also work with the Dockerfile):
- Railway, Fly.io, Google Cloud Run, Azure Container Apps.

### GitHub + Render workflow

1. Push your branch to `https://github.com/<your-username>/aurora-qa.git`.
2. Connect that repository in Render; it reads `render.yaml` and knows to run the `aurora-qa` service.
3. Render builds the Docker image, runs the container on port 8000, and exposes `/ask`.
4. Render’s free tier may ask for a credit card to prevent abuse, but no charges occur unless paid features are enabled.
5. After each GitHub push, Render redeploys automatically.

---

## Design Notes (Bonus 1)

I explored several strategies for building the QA capability:

1. **Rule-based retrieval + heuristics** (implemented)  
   Fast, predictable answers using regexes and helper functions in `app/qa.py`. It keeps the dependencies minimal and the Docker image small. The downside is that it needs explicit keyword matches for each kind of question.

2. **TF‑IDF retrieval + a local slot-filling model**  
   Could capture structured elements (dates, numbers) without calling external services. This would add model artifacts and require tuning, so I avoided it in favor of straightforward heuristics.

3. **Embedding-based retrieval (Sentence Transformers)**  
   Offers stronger semantic matching and paraphrase handling, but leaves you downloading ~90–100MB of model weights, spending 1-3 seconds at startup, and using more RAM. The comparison in `WHY_TFIDF_NOT_EMBEDDINGS.md` highlights those tradeoffs.

4. **Managed LLM (OpenAI/Anthropic)**  
   Has the most natural responses, but needs API keys, incurs cost, and complicates a free public deployment. The assignment requirements did not ask for external APIs or paid services.

Given the small dataset, simple question types, and deployment constraints, TF‑IDF plus targeted heuristics is the best balance of speed, cost, and explainability. It handles the example questions reliably while still being easy for reviewers to understand and debug.

---

## Data Insights (Bonus 2)

Run the analyzer to produce a concise JSON summary:
```bash
python analyze_data.py
```

Current snapshot recorded in `data_insights.json`:

- Total messages: 100  
- Unique members: 10  
- Duplicate member names (over 10 messages): Sophia Al-Farsi, Fatima El-Tahir, Hans Müller  
- Empty content messages: 0  
- Messages containing dates: 6  
- Car count conflicts: none

The analyzer also flags high-frequency members and any conflicting counts so you can monitor anomalies as the data grows. Update the script for additional checks if needed.

---

## Notes

- Caching: `app/retriever.py` refreshes the `/messages` data every 15 minutes.
- Fallbacks: If heuristics fail to extract structured answers, the service returns the most relevant supporting message text.
- Testing: `pytest test_api.py` exercises both `/health` and `/ask`.


