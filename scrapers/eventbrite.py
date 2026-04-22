import os
import requests

PRIVATE_TOKEN = os.getenv("EVENTBRITE_PRIVATE_TOKEN", "")
BASE_URL = "https://www.eventbriteapi.com/v3"

TAMIL_KEYWORDS = [
    "tamil", "tamilnadu", "kollywood", "carnatic", "bharatanatyam",
    "pongal", "diwali tamil", "sangam", "jallikattu", "thiruvizha"
]

def fetch_events():
    if not PRIVATE_TOKEN:
        return []

    headers = {"Authorization": f"Bearer {PRIVATE_TOKEN}"}
    all_events = []

    for keyword in TAMIL_KEYWORDS:
        try:
            resp = requests.get(
                f"{BASE_URL}/events/search/",
                headers=headers,
                params={
                    "q": keyword,
                    "expand": "organizer,venue",
                    "sort_by": "date",
                    "status": "live",
                },
                timeout=10,
            )
            if resp.status_code != 200:
                continue

            for ev in resp.json().get("events", []):
                venue = ev.get("venue") or {}
                address = venue.get("address") or {}
                organizer = ev.get("organizer") or {}

                all_events.append({
                    "id":          ev.get("id", ""),
                    "title":       ev.get("name", {}).get("text", ""),
                    "description": ev.get("description", {}).get("text", "") or "",
                    "date":        (ev.get("start", {}).get("local", "") or "")[:10],
                    "time":        (ev.get("start", {}).get("local", "") or "")[11:16],
                    "city":        address.get("city", ""),
                    "country":     address.get("country", ""),
                    "location":    venue.get("name", ""),
                    "address":     address.get("localized_address_display", ""),
                    "image":       (ev.get("logo") or {}).get("url", ""),
                    "url":         ev.get("url", ""),
                    "category":    "Cultural",
                    "source":      "eventbrite",
                    "is_free":     ev.get("is_free", False),
                    "organizer":   organizer.get("name", ""),
                })
        except Exception:
            continue

    # Deduplicate by id
    seen = set()
    unique = []
    for e in all_events:
        if e["id"] not in seen:
            seen.add(e["id"])
            unique.append(e)

    return unique
