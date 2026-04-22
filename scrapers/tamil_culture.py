import requests
from bs4 import BeautifulSoup

URL = "https://www.tamilculture.ca/events"

def fetch_events():
    try:
        resp = requests.get(URL, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, "html.parser")
        events = []

        for card in soup.select(".event-item, .tribe-event, article"):
            title = card.select_one("h2, h3, .tribe-event-title")
            date  = card.select_one(".tribe-event-date-start, time, .date")
            loc   = card.select_one(".tribe-venue, .location")
            link  = card.select_one("a")
            img   = card.select_one("img")

            if not title:
                continue

            events.append({
                "id":          f"tc-{hash(title.get_text())}",
                "title":       title.get_text(strip=True),
                "description": "",
                "date":        date.get_text(strip=True) if date else "",
                "time":        "",
                "city":        "Toronto",
                "country":     "Canada",
                "location":    loc.get_text(strip=True) if loc else "",
                "address":     "",
                "image":       img["src"] if img and img.get("src") else "",
                "url":         link["href"] if link and link.get("href") else "",
                "category":    "Cultural",
                "source":      "tamilculture",
                "is_free":     False,
                "organizer":   "Tamil Culture",
            })

        return events
    except Exception:
        return []
