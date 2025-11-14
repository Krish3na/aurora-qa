import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import httpx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

MESSAGES_URL = "https://november7-730026606190.europe-west1.run.app/messages/"
PAGE_LIMIT = 100  # Keep limit at default page size to avoid API throttling
MIN_LIMIT = 1
REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)
KEYWORD_CUES = ["trip", "travel", "flight", "car", "vehicle", "restaurant", "reservation"]
USE_API = os.getenv("ANALYZE_USE_API", "false").lower() in {"1", "true", "yes", "on"}
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
# keep analyzer outputs next to the fetch script so we know where the data lives.
DATA_DUMP = DATA_DIR / "messages_fetch_full.json"
FALLBACK_DUMP = DATA_DIR / "messages_full.json"
SAMPLE_DUMP = DATA_DIR / "messages.json"


def _load_messages_from(path: Path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]
    if isinstance(data, list):
        return data
    raise ValueError(f"Unexpected format in {path}")


def _handle_api_failure(exc, collected):
    # fallback to whatever dump we have when the live pagination fails.
    fallback = _load_messages_from(DATA_DUMP) or _load_messages_from(FALLBACK_DUMP) or _load_messages_from(SAMPLE_DUMP)
    if fallback:
        existing_ids = {m.get("id") for m in collected if m.get("id")}
        combined = list(collected)
        added = 0
        for msg in fallback:
            msg_id = msg.get("id")
            if msg_id and msg_id in existing_ids:
                continue
            combined.append(msg)
            if msg_id:
                existing_ids.add(msg_id)
            added += 1
        print(
            f"API pagination failed ({exc}); kept {len(collected)} API records and "
            f"added {added} fallback records from local dump."
        )
        return combined
    raise exc


def _fetch_page(client, skip):
    limit = PAGE_LIMIT
    while True:
        params = {"skip": skip, "limit": limit}
        resp = client.get(MESSAGES_URL, params=params)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and isinstance(data.get("items"), list):
                return data, len(data["items"]), limit
            if isinstance(data, list):
                return {"items": data}, len(data), limit
            raise ValueError("Unexpected response format")

        if resp.status_code in {400, 401, 403, 405} and limit > MIN_LIMIT:
            limit = max(MIN_LIMIT, limit // 2)
            continue

        resp.raise_for_status()


def _fetch_messages_from_api():
    collected = []
    skip = 0
    total = None
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            while True:
                data, page_count, used_limit = _fetch_page(client, skip)
                chunk = data.get("items", [])
                if not chunk:
                    break

                collected.extend(chunk)
                skip += page_count

                if total is None:
                    total = data.get("total")
                if total is not None and skip >= total:
                    break
                if used_limit and page_count < used_limit:
                    break
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        return _handle_api_failure(exc, collected)

    if total is not None and len(collected) >= total:
        return collected
    fallback = _load_messages_from(DATA_DUMP) or _load_messages_from(FALLBACK_DUMP) or _load_messages_from(SAMPLE_DUMP)
    return collected or fallback


def fetch_messages():
    if USE_API:
        return _fetch_messages_from_api()
    # Prefer the full dump when available, otherwise fall back to the shipped 100-message sample.
    for candidate in (DATA_DUMP, FALLBACK_DUMP, SAMPLE_DUMP):
        if candidate.exists():
            print(f"Loading data from {candidate}.")
            return _load_messages_from(candidate)
    return []


def _parse_timestamp(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _sample_messages(messages, limit=3):
    samples = []
    for m in messages[:limit]:
        samples.append({
            "id": m.get("id"),
            "member": m.get("user_name"),
            "preview": (m.get("message") or "")[:120],
        })
    return samples


# draw a horizontal bar chart of the most active members.
def _plot_member_distribution(distribution, out_path):
    if not distribution:
        return
    names = [entry["member"] for entry in distribution]
    counts = [entry["count"] for entry in distribution]
    plt.figure(figsize=(10, 5))
    plt.barh(names[::-1], counts[::-1], color="#5a7bd0")
    plt.title("Top Members by Message Count")
    plt.xlabel("Message count")
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


# simple timeline to show how conversations wave over months.
def _plot_timeline(monthly_counts, out_path):
    if not monthly_counts:
        return
    months = [entry["month"] for entry in monthly_counts]
    counts = [entry["count"] for entry in monthly_counts]
    plt.figure(figsize=(10, 4))
    plt.plot(months, counts, marker="o", color="#c65c8f")
    plt.title("Messages Over Time")
    plt.xlabel("Month")
    plt.ylabel("Messages")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


# keyword coverage to see which cues come up most.
def _plot_keyword_coverage(keyword_counts, out_path):
    if not keyword_counts:
        return
    sorted_items = sorted(keyword_counts.items(), key=lambda item: item[1], reverse=True)
    keywords, counts = zip(*sorted_items)
    plt.figure(figsize=(10, 4))
    plt.bar(keywords, counts, color="#3b8c5a")
    plt.title("Keyword Mentions")
    plt.ylabel("Mentions")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


# anomalies histogram for quick spotting of odd rows.
def _plot_anomaly_histogram(anomaly_counts, out_path):
    # Always emit a chart so reviewers see that we checked for anomalies.
    plt.figure(figsize=(10, 4))
    if not anomaly_counts:
        plt.title("Anomaly Counts (none detected)")
        plt.text(0.5, 0.5, "No anomalies found", ha="center", va="center", fontsize=12)
        plt.axis("off")
    else:
        types = list(anomaly_counts.keys())
        counts = [anomaly_counts[t] for t in types]
        plt.bar(types, counts, color="#e07b39")
        plt.title("Anomaly Counts")
        plt.ylabel("Count")
        plt.xticks(rotation=45)
        plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


# gather counts, keywords, and anomalies for the report.
def analyze(messages):
    member_counts = Counter()
    empty_contents = []
    keyword_counts = Counter({kw: 0 for kw in KEYWORD_CUES})
    timeline_counts = Counter()
    car_mentions = defaultdict(list)
    duplicate_counter = Counter()
    missing_name_messages = []
    missing_timestamp_messages = []
    long_messages = []
    anomaly_counts = Counter()
    date_regex = re.compile(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|[A-Za-z]+ \d{1,2}(?:, \d{4})?)\b")

    for m in messages:
        member = (m.get("user_name", "") or "").strip()
        text = str(m.get("message", "") or "")
        if not text.strip():
            empty_contents.append(m)
        if member:
            member_counts[member] += 1
        else:
            missing_name_messages.append(m)

        timestamp = _parse_timestamp(m.get("timestamp", ""))
        if timestamp:
            month_label = f"{timestamp.year}-{timestamp.month:02}"
            timeline_counts[month_label] += 1
        else:
            missing_timestamp_messages.append(m)

        normalized = text.lower()
        for keyword in KEYWORD_CUES:
            if keyword in normalized:
                keyword_counts[keyword] += 1

        if len(text) > 220:
            long_messages.append({"member": member or "Unknown", "length": len(text), "preview": text[:120]})

        if "car" in normalized or "vehicle" in normalized:
            car_mentions[member or "Unknown"].append(text)

        duplicate_key = (member or "Unknown", text)
        duplicate_counter[duplicate_key] += 1

    duplicate_examples = []
    for (owner, msg_text), count in duplicate_counter.items():
        if count > 1:
            duplicate_examples.append({
                "member": owner,
                "count": count,
                "preview": msg_text[:120],
            })

    messages_with_dates = sum(1 for m in messages if date_regex.search(str(m.get("message", ""))))
    duplicate_members = [name for name, cnt in member_counts.items() if cnt > 10]

    def extract_car_count(t):
        tokens = re.findall(r"\w+|\d+", t.lower())
        for i, tok in enumerate(tokens):
            if tok in {"car", "cars", "vehicle", "vehicles"}:
                span = tokens[max(0, i - 5): i + 6]
                for s in span:
                    if s.isdigit():
                        return int(s)
        return None

    car_count_conflicts = []
    for member, texts in car_mentions.items():
        counts = {extract_car_count(t) for t in texts}
        counts.discard(None)
        if len(counts) > 1:
            car_count_conflicts.append({"member": member, "counts": sorted(counts)})

    member_distribution = [
        {"member": name, "count": count}
        for name, count in member_counts.most_common()
    ]
    monthly_counts = [
        {"month": month, "count": count}
        for month, count in sorted(timeline_counts.items())
    ]

    anomalies = []
    if missing_name_messages:
        anomalies.append({
            "issue": "missing_user_name",
            "count": len(missing_name_messages),
            "examples": _sample_messages(missing_name_messages),
        })
        anomaly_counts["missing_user_name"] = len(missing_name_messages)
    if missing_timestamp_messages:
        anomalies.append({
            "issue": "missing_timestamp",
            "count": len(missing_timestamp_messages),
            "examples": _sample_messages(missing_timestamp_messages),
        })
        anomaly_counts["missing_timestamp"] = len(missing_timestamp_messages)
    if long_messages:
        anomalies.append({
            "issue": "long_message",
            "count": len(long_messages),
            "examples": long_messages[:3],
        })
        anomaly_counts["long_message"] = len(long_messages)
    if duplicate_examples:
        anomalies.append({
            "issue": "duplicate_text",
            "count": len(duplicate_examples),
            "examples": duplicate_examples[:3],
        })
        anomaly_counts["duplicate_text"] = len(duplicate_examples)

    return {
        "total_messages": len(messages),
        "unique_members": len(member_counts),
        "duplicate_member_names_over_10_msgs": duplicate_members,
        "empty_content_messages": len(empty_contents),
        "messages_with_dates": messages_with_dates,
        "car_count_conflicts": car_count_conflicts[:10],
        "member_message_distribution": member_distribution,
        "monthly_message_counts": monthly_counts,
        "keyword_mentions": dict(keyword_counts),
        "anomaly_counts": dict(anomaly_counts),
        "anomalies": anomalies,
    }


def main():
    # print("starting data analysis...")
    print("Starting full analysis run.")
    msgs = fetch_messages()
    report = analyze(msgs)
    print("Computed report, dumping to JSON.")
    insights_path = DATA_DIR / "data_insights.json"
    with insights_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Wrote {insights_path}")
    _plot_member_distribution(report["member_message_distribution"][:10], REPORTS_DIR / "messages_by_member.png")
    print("Saved member distribution chart.")
    _plot_timeline(report["monthly_message_counts"], REPORTS_DIR / "messages_timeline.png")
    print("Saved timeline chart.")
    _plot_keyword_coverage(report["keyword_mentions"], REPORTS_DIR / "keyword_coverage.png")
    print("Saved keyword coverage chart.")
    _plot_anomaly_histogram(report.get("anomaly_counts", {}), REPORTS_DIR / "anomaly_histogram.png")
    print("Saved anomaly histogram chart.")
    print("Charts saved in reports/")


if __name__ == "__main__":
    main()


