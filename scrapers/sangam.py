import requests
from bs4 import BeautifulSoup

URL = "https://www.sangam.org/events"

def fetch_events():
    try:
        resp = requests.get(URL, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, "html.parser")
        events = []

        for card in soup.select(".event, article, .event-listing"):
            title = card.select_one("h2, h3, a")
            date  = card.select_one("time, .date")
            link  = card.select_one("a")
            img   = card.select_one("img")

            if not title:
                continue

            events.append({
                "id":          f"sg-{hash(title.get_text())}",
                "title":       title.get_text(strip=True),
                "description": "",
                "date":        date.get_text(strip=True) if date else "",
                "time":        "",
                "city":        "",
                "country":     "",
                "location":    "",
                "address":     "",
                "image":       img["src"] if img and img.get("src") else "",
                "url":         link["href"] if link and link.get("href") else "",
                "category":    "Cultural",
                "source":      "sangam",
                "is_free":     False,
                "organizer":   "Sangam.org",
            })

        return events
    except Exception:
        return []
