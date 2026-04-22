import requests
from bs4 import BeautifulSoup

URL = "https://www.tamilevents.co.uk"

def fetch_events():
    try:
        resp = requests.get(URL, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, "html.parser")
        events = []

        for card in soup.select(".event, .event-item, article, .event-card"):
            title = card.select_one("h2, h3, .event-title")
            date  = card.select_one("time, .date, .event-date")
            link  = card.select_one("a")
            img   = card.select_one("img")

            if not title:
                continue

            events.append({
                "id":          f"uk-{hash(title.get_text())}",
                "title":       title.get_text(strip=True),
                "description": "",
                "date":        date.get_text(strip=True) if date else "",
                "time":        "",
                "city":        "London",
                "country":     "United Kingdom",
                "location":    "",
                "address":     "",
                "image":       img["src"] if img and img.get("src") else "",
                "url":         link["href"] if link and link.get("href") else "",
                "category":    "Cultural",
                "source":      "tamileventsuk",
                "is_free":     False,
                "organizer":   "Tamil Events UK",
            })

        return events
    except Exception:
        return []
