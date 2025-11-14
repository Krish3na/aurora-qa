import re

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

# try to get a member's name out of a question
def _extract_member_from_question(question):
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
	# print(f"Could not extract member from question: {question}")
	return None

# Looks for locations, right now only simple 'trip to X'
def _extract_location_from_question(question):
	m = re.search(r"\btrip to\s+([A-Z][a-zA-Z]+)\b", question, flags=re.IGNORECASE)
	if m:
		return m.group(1)
	return None

# filter retrieved messages for ones referencing the member
def _filter_by_member(messages, member_name):
	if not member_name:
		return messages
	member_l = member_name.lower()
	filtered = [
		m
		for m in messages
		if member_l in (m.meta.get("user_name", "")).lower()
		or member_l in m.text.lower()
	]
	# print(f"Filtered by member: {filtered if filtered else messages}")
	return filtered or messages

# filter retrieved messages by location keyword
def _filter_by_location(messages, location):
	if not location:
		return messages
	loc_l = location.lower()
	filtered = [m for m in messages if loc_l in m.text.lower()]
	# print(f"Filtered by location: {filtered if filtered else messages}")
	return filtered or messages

# Extracts the first date-like string using above regexes
def _extract_date(text):
	m = _DATE_REGEX.search(text)
	return m.group(0) if m else None

# Try to find a number (or word-number) near "car(s)" mention
def _extract_car_count(text):
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

# look for proper-noun phrases after certain cues
def _extract_restaurants(text):
	candidates = []
	if re.search(r"\bfavorite\b.*\brestaurant", text, flags=re.IGNORECASE):
		# naive proper-noun capture
		for m in re.finditer(r"\b([A-Z][A-Za-z'&.-]+(?:\s+[A-Z][A-Za-z'&.-]+)*)\b", text):
			name = m.group(1)
			# filter obvious non-restaurant entities
			if name.lower() in {"i", "we", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}:
				continue
			if len(name) >= 3:
				candidates.append(name)
	# Common cue "at <Place>" or "to <Place>"
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
	# print(f"Extracted restaurant candidates: {candidates}")
	return unique[:5]

def answer_question(question, retrieved):
	# print(f"Question: {question}")
	member = _extract_member_from_question(question)
	location = _extract_location_from_question(question)
	scope = _filter_by_member(retrieved, member)
	scope = _filter_by_location(scope, location)

	q_l = question.lower()
	# print("Final message candidates:", [m.text for m in scope])
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
		# if no clear date is present, prefer a longer message that actually talks about trips
		travel_keywords = ["trip", "trips", "travel", "flight", "itinerary"]
		for r in scope:
			text_l = r.text.lower()
			if any(kw in text_l for kw in travel_keywords) and len(r.text.strip()) > 20:
				raw = r.meta.get("message") or r.text
				if member:
					return f"{member} mentioned: {raw}"
				return raw
		# final fallback: just show the top message for transparency
		if scope:
			raw = scope[0].meta.get("message") or scope[0].text
			if member:
				return f"{member} mentioned: {raw}"
			return raw
		return "Sorry, I couldn't find travel details."

	if "how many" in q_l and ("car" in q_l or "vehicle" in q_l):
		for r in scope:
			count = _extract_car_count(r.text)
			if count is not None:
				if member:
					return f"{member} has {count} car{'s' if count != 1 else ''}."
				return f"They have {count} car{'s' if count != 1 else ''}."
		# print("No car count found; fallback")
		return scope[0].text if scope else "Sorry, I couldn't find how many cars."

	if "restaurant" in q_l or "favorite" in q_l:
		for r in scope:
			restaurants = _extract_restaurants(r.text)
			if restaurants:
				names = ", ".join(restaurants)
				if member:
					return f"{member}'s favorite restaurants include: {names}."
				return f"Favorite restaurants include: {names}."
		# print("No restaurant found; fallback")
		return scope[0].text if scope else "Sorry, I couldn't find favorite restaurants."

	# fallback to the top message
	return scope[0].text if scope else "Sorry, I couldn't find an answer."