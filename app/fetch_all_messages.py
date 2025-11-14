import argparse
import json
import time
from pathlib import Path

import httpx

MESSAGES_URL = "https://november7-730026606190.europe-west1.run.app/messages/"
DEFAULT_LIMIT = 100
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
# Keep the pagination dump inside the data folder so everything is grouped together.
OUTPUT_PATH = DATA_DIR / "messages_fetch_full.json"
TEMP_OUTPUT = DATA_DIR / "messages_fetch_full.tmp.json"


def _load_existing():
    if not OUTPUT_PATH.exists():
        return []
    with OUTPUT_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("items", []) if isinstance(data, dict) else data


def fetch_all(limit: int = DEFAULT_LIMIT, delay: float = 0.2, *, output_path: Path = OUTPUT_PATH, temp_path: Path = TEMP_OUTPUT):
    """Stream messages with skip/limit and save into a local JSON file."""
    collected = list(_load_existing())
    print(f"Starting with {len(collected)} cached messages.")
    seen_ids = {msg.get("id") for msg in collected if msg.get("id")}
    skip = len(collected)
    total = None

    with httpx.Client(timeout=30, follow_redirects=True) as client:
        while True:
            params = {"skip": skip, "limit": limit}
            resp = client.get(MESSAGES_URL, params=params)

            if resp.status_code == 200:
                payload = resp.json()
                chunk = []
                if isinstance(payload, dict):
                    chunk = payload.get("items", [])
                    total = payload.get("total", total)
                elif isinstance(payload, list):
                    chunk = payload
                else:
                    raise ValueError("Unexpected API response")

                if not chunk:
                    print("No more messages returned; stopping.")
                    break

                added = 0
                for msg in chunk:
                    msg_id = msg.get("id")
                    if msg_id and msg_id in seen_ids:
                        continue
                    if msg_id:
                        seen_ids.add(msg_id)
                    collected.append(msg)
                    added += 1

                print(f"Fetched {len(chunk)} rows (added {added}), total collected {len(collected)}.")
                if total and len(collected) >= total:
                    print("Collected at least total count from API.")
                    break

                skip += len(chunk)
                time.sleep(delay)
                continue

            if resp.status_code in {400, 401, 402, 403, 404, 405} and limit > 1:
                limit = max(1, limit // 2)
                print(f"Got {resp.status_code}; reducing limit to {limit} and retrying.")
                time.sleep(delay)
                continue

            if resp.status_code in {400, 401, 402, 403, 404, 405}:
                print(f"Received {resp.status_code} even at limit=1; stopping early.")
                break

            resp.raise_for_status()

    report = {"total": total or len(collected), "items": collected}
    temp_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    temp_path.replace(output_path)
    print(f"Wrote {len(collected)} messages to {output_path}")



def main():
    parser = argparse.ArgumentParser(description="Fetch all messages via pagination.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Initial page size")
    parser.add_argument("--delay", type=float, default=0.2, help="Pause between requests")
    args = parser.parse_args()
    fetch_all(limit=args.limit, delay=args.delay)


if __name__ == "__main__":
    main()

