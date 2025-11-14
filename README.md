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
- Dataset refresh script (`app/fetch_all_messages.py`) plus analyzer (`app/analyze_data.py`) that output the analytics JSON and charts into `data/` and `reports/`.
- Data directory with `messages.json`, `messages_full.json`, `messages_fetch_full.json`, and `data_insights.json`.
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
5. Run the data analyzer (writes `data/data_insights.json` and regenerates the charts):
   ```bash
   python app/analyze_data.py
   ```
6. Refresh the full message dump (writes to `data/messages_fetch_full.json`):
   ```bash
   python app/fetch_all_messages.py --delay 1
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

1. **TF‑IDF retrieval + heuristics (implemented)**  
   The service uses TF‑IDF to surface the most relevant messages and then applies regex/keyword heuristics in `app/qa.py` to extract dates, numbers, or restaurant names. It keeps the dependencies minimal, keeps the Docker image small, and still handles the example questions deterministically. The downside is that those heuristics rely on matching keywords and patterns, so they need to be expanded for new question types.

2. **TF‑IDF retrieval + a local slot-filling model**  
   Could capture structured elements (dates, numbers) without calling external services. This would add model artifacts and require tuning, so I avoided it in favor of straightforward heuristics.

3. **Embedding-based retrieval (Sentence Transformers)**  
   Offers stronger semantic matching and paraphrase handling, but leaves you downloading ~90–100MB of model weights, spending 1-3 seconds at startup, and using more RAM. The comparison in `WHY_TFIDF_NOT_EMBEDDINGS.md` highlights those tradeoffs.

4. **Managed LLM (OpenAI/Anthropic)**  
   Has the most natural responses, but needs API keys, incurs cost, and complicates a free public deployment. The assignment requirements did not ask for external APIs or paid services.

Given the small dataset, simple question types, and deployment constraints, TF‑IDF plus targeted heuristics is the best balance of speed, cost, and explainability. It handles the example questions reliably while still being easy for reviewers to understand and debug.

---

## Data Insights (Bonus 2)

Run the analyzer to produce a concise JSON summary and visualizations:
```bash
python app/analyze_data.py
```

`app/analyze_data.py` now loads `data/messages_fetch_full.json` (3,349 records generated by `app/fetch_all_messages.py`). If that dump is being rebuilt or missing, the script falls back to `data/messages_full.json` and then the original `data/messages.json` sample, so you always have something to analyze. The pagination helpers remain available if you prefer to stream directly (`ANALYZE_USE_API=1`).

Snapshot recorded in `data/data_insights.json` (current run using `messages_fetch_full.json`):

- Total messages: 3,349  
- Unique members: 10  
- Members with more than 10 messages: Sophia Al-Farsi, Fatima El-Tahir, Armand Dupont, Hans Müller, Layla Kawaguchi, Amina Van Den Berg, Vikram Desai, Lily O'Sullivan, Lorenzo Cavalli, Thiago Monteiro  
- Empty content messages: 0  
- Messages containing dates: 237  
- Car count conflicts: none  
- Member message distribution: JSON array of counts per member (feeds `reports/messages_by_member.png`)
- Monthly message counts: timeline entries that feed `reports/messages_timeline.png`
- Keyword mention totals: counts for cues the heuristics track (`trip`, `restaurant`, `car`, etc.) and are visualized in `reports/keyword_coverage.png`
- Anomaly breakdown: counts for missing names/timestamps, repeated text, or extra-long messages plus sample details in `reports/anomaly_histogram.png`

All four charts (member distribution, timeline, keyword coverage, anomaly histogram) land in `reports/`. If you need a fresh copy of `data/messages_fetch_full.json`, run `python app/fetch_all_messages.py --delay 1`; the script resumes from the last run, respects rate limits, and appends only new IDs. Re-run `python app/analyze_data.py` afterward to regenerate the charts and JSON.

Visualizations summary:

| Chart | Insight |
| --- | --- |
| `reports/messages_by_member.png` | Bar chart showing which members are most active (Lily, Thiago, Fatima on top). The long tail helps verify whether some identities dominate the chat volume. |
| `reports/messages_timeline.png` | Month-over-month volume trend; spikes in December and August highlight busy planning periods, while the latest partial month drops because the dataset stops in mid-November. |
| `reports/keyword_coverage.png` | Keyword mentions plotted to track how often travel, car, reservation cues appear—this validates the heuristics around these tokens and suggests which signals are least frequent (e.g., `vehicle`). |
| `reports/anomaly_histogram.png` | Counts of anomalies detected (missing names/timestamps, repeated text, long messages); the chart helps spot which issue deserves attention before we refine the QA rules. |

---

## Notes

- Caching: `app/retriever.py` refreshes `/messages` data every 30 minutes. Each refresh runs `fetch_all_messages.fetch_all`, so it rebuilds `data/messages_fetch_full.json` but still serves `data/messages_full.json` (the older dump) if the new copy is unavailable during startup.
- Fallbacks: If heuristics fail to extract structured answers, the service returns the most relevant supporting message text.
- Testing: `pytest test_api.py` exercises both `/health` and `/ask`.


