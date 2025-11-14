import json
import re
from collections import Counter, defaultdict
import httpx

MESSAGES_URL = "https://november7-730026606190.europe-west1.run.app/messages/"


def fetch_messages():
    # pull data down for analysis
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        resp = client.get(MESSAGES_URL)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            # print(f"Got {len(data['items'])} items.")
            return data["items"]
        if isinstance(data, list):
            return data
        raise ValueError("Unexpected response format")


def analyze(messages):
    # count message volume per member
    member_counts = Counter((m.get("user_name", "")).strip() for m in messages)
    # search for totally empty messages, spot anomalies
    empty_contents = [m for m in messages if not m.get("message")]
    # look for messages mentioning a date
    date_regex = re.compile(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|[A-Za-z]+ \d{1,2}(?:, \d{4})?)\b")
    car_mentions = defaultdict(list)

    for m in messages:
        member = (m.get("user_name", "")).strip()
        text = str(m.get("message", ""))
        if not text:
            continue
        if "car" in text.lower() or "vehicle" in text.lower():
            car_mentions[member].append(text)

    # print("members/msgs sampled:", list(member_counts.items())[:3])

    duplicate_members = [name for name, cnt in member_counts.items() if name and cnt > 10]
    messages_with_dates = sum(1 for m in messages if date_regex.search(str(m.get("message", ""))))

    # is there more than one car count per member?
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
    # print("car count conflicts found:", car_count_conflicts[:2])

    return {
        "total_messages": len(messages),
        "unique_members": sum(1 for n in member_counts if n),
        "duplicate_member_names_over_10_msgs": duplicate_members,
        "empty_content_messages": len(empty_contents),
        "messages_with_dates": messages_with_dates,
        "car_count_conflicts": car_count_conflicts[:10],
    }


def main():
    # print("starting data analysis...")
    msgs = fetch_messages()
    report = analyze(msgs)
    print(json.dumps(report, indent=2))
    with open("data_insights.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print("Wrote data_insights.json")


if __name__ == "__main__":
    main()


