import re
from typing import List, Dict, Any, Optional, Tuple

from .retriever import RetrievedMessage


_DATE_PATTERNS = [
	r"\b\d{4}-\d{2}-\d{2}\b",  # 2025-11-09
	r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",  # 11/9/2025 or 11/09/25
	r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:,\s*\d{4})?\b",
	r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*(?:\s+\d{4})?\b",
	r"\b(?:today|tomorrow|tonight|this week|next week|this weekend|next weekend)\b",
]
_DATE_REGEX = re.compile("|".join(_DATE_PATTERNS), flags=re.IGNORECASE)

_NUMBER_WORDS = {
	"zero": 0,
	"one": 1,
	"two": 2,
	"three": 3,
	"four": 4,
	"five": 5,
	"six": 6,
	"seven": 7,
	"eight": 8,
	"nine": 9,
	"ten": 10,
}


def _extract_member_from_question(question: str) -> Optional[str]:
	# Naive heuristic: capture capitalized first + optional last name from possessive or direct mention
	m = re.search(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)['’]s\b", question)
	if m:
		return m.group(1)
	m2 = re.search(r"\babout\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", question)
	if m2:
		return m2.group(1)
	m3 = re.search(r"\bfor\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", question)
	if m3:
		return m3.group(1)
	m4 = re.search(r"\bwhen is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", question, flags=re.IGNORECASE)
	if m4:
		return m4.group(1)
	return None


def _extract_location_from_question(question: str) -> Optional[str]:
	m = re.search(r"\btrip to\s+([A-Z][a-zA-Z]+)\b", question, flags=re.IGNORECASE)
	if m:
		return m.group(1)
	return None


def _filter_by_member(messages: List[RetrievedMessage], member_name: Optional[str]) -> List[RetrievedMessage]:
	if not member_name:
		return messages
	member_l = member_name.lower()
	filtered = [
		m
		for m in messages
		if member_l in (m.meta.get("user_name") or m.meta.get("member_name") or "").lower()
		or member_l in m.text.lower()
	]
	return filtered or messages


def _filter_by_location(messages: List[RetrievedMessage], location: Optional[str]) -> List[RetrievedMessage]:
	if not location:
		return messages
	loc_l = location.lower()
	filtered = [m for m in messages if loc_l in m.text.lower()]
	return filtered or messages


def _extract_date(text: str) -> Optional[str]:
	m = _DATE_REGEX.search(text)
	return m.group(0) if m else None


def _extract_car_count(text: str) -> Optional[int]:
	window = 8
	tokens = re.findall(r"\w+|\d+", text.lower())
	for i, tok in enumerate(tokens):
		if tok in {"car", "cars", "vehicle", "vehicles"}:
			# Look around for numbers
			span = tokens[max(0, i - window) : i + window + 1]
			for s in span:
				if s.isdigit():
					return int(s)
				if s in _NUMBER_WORDS:
					return _NUMBER_WORDS[s]
	return None


def _extract_restaurants(text: str) -> List[str]:
	# Look for phrases like "favorite restaurant(s)" or "love <Name> restaurant" and capture Proper Nouns following 'at', 'in', or commas
	candidates: List[str] = []
	if re.search(r"\bfavorite\b.*\brestaurant", text, flags=re.IGNORECASE):
		# naive proper-noun capture
		for m in re.finditer(r"\b([A-Z][A-Za-z'&.-]+(?:\s+[A-Z][A-Za-z'&.-]+)*)\b", text):
			name = m.group(1)
			# filter obvious non-restaurant entities
			if name.lower() in {"i", "we", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}:
				continue
			if len(name) >= 3:
				candidates.append(name)
	# Common cue: "at <Place>" or "to <Place>"
	for m in re.finditer(r"\b(?:at|to|in)\s+([A-Z][A-Za-z'&.-]+(?:\s+[A-Z][A-Za-z'&.-]+)*)", text):
		candidates.append(m.group(1))
	# Deduplicate while preserving order
	seen = set()
	unique = []
	for c in candidates:
		key = c.lower()
		if key not in seen:
			seen.add(key)
			unique.append(c)
	return unique[:5]


def answer_question(question: str, retrieved: List[RetrievedMessage]) -> str:
	member = _extract_member_from_question(question)
	location = _extract_location_from_question(question)

	scope = _filter_by_member(retrieved, member)
	scope = _filter_by_location(scope, location)

	q_l = question.lower()
	if "trip" in q_l or "travel" in q_l or "flight" in q_l:
		# try to extract a date from the most relevant message mentioning the location
		for r in scope:
			date = _extract_date(r.text)
			if date:
				if member and location:
					return f"{member} is planning the trip to {location} on {date}."
				if member:
					return f"{member}'s trip is on {date}."
				return f"The trip is on {date}."
		# fallback
		return scope[0].text if scope else "Sorry, I couldn't find travel details."

	if "how many" in q_l and ("car" in q_l or "vehicle" in q_l):
		for r in scope:
			count = _extract_car_count(r.text)
			if count is not None:
				if member:
					return f"{member} has {count} car{'s' if count != 1 else ''}."
				return f"They have {count} car{'s' if count != 1 else ''}."
		return scope[0].text if scope else "Sorry, I couldn't find how many cars."

	if "restaurant" in q_l or "favorite" in q_l:
		for r in scope:
			restaurants = _extract_restaurants(r.text)
			if restaurants:
				names = ", ".join(restaurants)
				if member:
					return f"{member}'s favorite restaurants include: {names}."
				return f"Favorite restaurants include: {names}."
		return scope[0].text if scope else "Sorry, I couldn't find favorite restaurants."

	# Generic fallback: echo the top supporting message
	return scope[0].text if scope else "Sorry, I couldn't find an answer."


