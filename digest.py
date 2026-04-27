import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
DIGEST_FROM    = os.getenv("DIGEST_FROM", "Tamil Events <onboarding@resend.dev>")
DIGEST_TO      = os.getenv("DIGEST_EMAIL", "tamilevents00@gmail.com")
ADMIN_KEY      = os.getenv("ADMIN_KEY", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection":      "keep-alive",
}

# Eventbrite city slugs for Tamil diaspora cities
EVENTBRITE_SEARCHES = [
    ("Toronto",   "canada--toronto"),
    ("London",    "united-kingdom--london"),
    ("Sydney",    "australia--sydney"),
    ("Melbourne", "australia--melbourne"),
    ("Singapore", "singapore--singapore"),
    ("Dubai",     "united-arab-emirates--dubai"),
    ("Kuala Lumpur", "malaysia--kuala-lumpur"),
    ("Chennai",   "india--chennai"),
]

EVENTBRITE_KEYWORDS = ["tamil", "bharatanatyam", "carnatic", "kollywood", "diwali", "pongal"]

# Allevents.in city slugs
ALLEVENTS_CITIES = [
    ("Toronto",      "toronto"),
    ("London",       "london"),
    ("Sydney",       "sydney"),
    ("Singapore",    "singapore"),
    ("Kuala Lumpur", "kuala-lumpur"),
    ("Dubai",        "dubai"),
    ("Melbourne",    "melbourne"),
]


def _eventbrite_city(city_label: str, city_slug: str) -> list[dict]:
    """Scrape Eventbrite's public search page for Tamil events in a city."""
    results = []
    seen    = set()
    for kw in EVENTBRITE_KEYWORDS[:3]:
        url = f"https://www.eventbrite.com/d/{city_slug}/{kw}--events/"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=14)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            # Eventbrite renders event cards with these selectors
            for el in soup.select("h3.eds-event-card__formatted-name--is-clamped, "
                                  "h3.Typography_root__487rx, "
                                  "div[data-testid='event-card'] h3, "
                                  "article h3")[:8]:
                title = el.get_text(strip=True)
                if len(title) < 8 or title.lower() in seen:
                    continue
                seen.add(title.lower())
                # Try to find the parent link
                parent = el.find_parent("a") or el.find_parent("article")
                href = parent.get("href", url) if parent else url
                if href and not href.startswith("http"):
                    href = "https://www.eventbrite.com" + href
                results.append({
                    "title":   title,
                    "url":     href or url,
                    "snippet": city_label,
                    "source":  f"Eventbrite {city_label}",
                })
        except Exception:
            continue
    return results


def _allevents_city(city_label: str, city_slug: str) -> list[dict]:
    """Scrape allevents.in for Tamil events in a city."""
    url = f"https://allevents.in/{city_slug}/tamil"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=14)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        seen    = set()
        for el in soup.select("h3.event-title, .event-title a, li.item h3, "
                              ".event-name, h2.title a, .title a")[:10]:
            title = el.get_text(strip=True)
            if len(title) < 8 or title.lower() in seen:
                continue
            seen.add(title.lower())
            link = el if el.name == "a" else el.find("a")
            href = link.get("href", url) if link else url
            results.append({
                "title":   title,
                "url":     href if href.startswith("http") else url,
                "snippet": city_label,
                "source":  f"AllEvents {city_label}",
            })
        return results
    except Exception:
        return []


def _tamilculture_ca() -> list[dict]:
    """Tamil Culture Canada — server-side rendered WordPress."""
    try:
        resp = requests.get("https://www.tamilculture.ca/events", headers=HEADERS, timeout=14)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        seen    = set()
        for el in soup.select(".tribe-event-url, .entry-title a, h2 a, h3 a")[:12]:
            title = el.get_text(strip=True)
            href  = el.get("href", "")
            if len(title) < 8 or title.lower() in seen:
                continue
            seen.add(title.lower())
            results.append({
                "title":   title,
                "url":     href if href.startswith("http") else "https://www.tamilculture.ca/events",
                "snippet": "Canada",
                "source":  "TamilCulture.ca",
            })
        return results
    except Exception:
        return []


def _tamilevents_uk() -> list[dict]:
    """Tamil Events UK."""
    try:
        resp = requests.get("https://www.tamilevents.co.uk", headers=HEADERS, timeout=14)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        seen    = set()
        for el in soup.select("h2 a, h3 a, .event-title a, article h2 a")[:12]:
            title = el.get_text(strip=True)
            href  = el.get("href", "")
            if len(title) < 8 or title.lower() in seen:
                continue
            seen.add(title.lower())
            results.append({
                "title":   title,
                "url":     href if href.startswith("http") else "https://www.tamilevents.co.uk",
                "snippet": "UK",
                "source":  "TamilEvents UK",
            })
        return results
    except Exception:
        return []


def gather_events() -> list[dict]:
    found = []
    seen  = set()

    def _add(items):
        for r in items:
            key = r["title"].lower()[:60]
            if key not in seen:
                seen.add(key)
                found.append(r)

    # 1. Eventbrite per city
    for city_label, city_slug in EVENTBRITE_SEARCHES:
        _add(_eventbrite_city(city_label, city_slug))

    # 2. AllEvents.in per city
    for city_label, city_slug in ALLEVENTS_CITIES:
        _add(_allevents_city(city_label, city_slug))

    # 3. Tamil-specific sites
    _add(_tamilculture_ca())
    _add(_tamilevents_uk())

    return found[:40]


def _build_html(events: list[dict], admin_url: str) -> str:
    month = datetime.now().strftime("%B %Y")
    admin = f"https://{admin_url}/admin?key={ADMIN_KEY}"

    if events:
        rows = ""
        for e in events:
            url  = e["url"] or "#"
            rows += f"""
            <tr>
              <td style="padding:14px 16px;border-bottom:1px solid #f0f0f5">
                <a href="{url}" style="font-size:14px;font-weight:600;color:#7233CC;text-decoration:none">
                  {e['title']}
                </a>
                <div style="font-size:12px;color:#6e6e73;margin-top:3px">{e['snippet']}</div>
                <div style="font-size:11px;color:#aaa;margin-top:2px">via {e['source']}</div>
              </td>
              <td style="padding:14px 16px;border-bottom:1px solid #f0f0f5;white-space:nowrap;vertical-align:middle">
                <a href="{admin}" style="background:#7233CC;color:white;padding:6px 14px;
                   border-radius:8px;font-size:12px;font-weight:600;text-decoration:none">
                  Add to App
                </a>
              </td>
            </tr>"""
        body = f"""
        <table style="width:100%;border-collapse:collapse">
          <thead>
            <tr style="background:#f5f5f7">
              <th style="text-align:left;padding:10px 16px;font-size:11px;color:#6e6e73;
                         text-transform:uppercase;letter-spacing:0.5px">Event / Source</th>
              <th style="padding:10px 16px;font-size:11px;color:#6e6e73;
                         text-transform:uppercase;letter-spacing:0.5px">Action</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>"""
    else:
        body = """
        <div style="padding:40px;text-align:center;color:#6e6e73;font-size:14px">
          No new Tamil events found from web sources today.<br/>
          <a href="{admin}" style="color:#7233CC;font-weight:600">Add events manually via Admin Panel</a>
        </div>""".format(admin=admin)

    count_text = f"{len(events)} potential events found" if events else "No new events today"

    return f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f5f7">
  <div style="max-width:640px;margin:32px auto;background:white;border-radius:16px;
              overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08)">
    <div style="background:linear-gradient(135deg,#7233CC,#F27A10);padding:28px 32px">
      <div style="font-size:22px;font-weight:800;color:white">🎭 Tamil Events</div>
      <div style="font-size:14px;color:rgba(255,255,255,0.85);margin-top:4px">
        Daily Digest — {month}
      </div>
    </div>
    <div style="padding:16px 32px 8px;font-size:14px;color:#333">
      <strong>{count_text}</strong> from across the web. Review and add the ones you want.
    </div>
    {body}
    <div style="padding:20px 32px;font-size:12px;color:#aaa;border-top:1px solid #f0f0f5">
      <a href="{admin}" style="color:#7233CC;font-weight:600;text-decoration:none">
        Open Admin Panel
      </a> &nbsp;·&nbsp; Tamil Events daily digest — sent every day at 8am UTC
    </div>
  </div>
</body>
</html>"""


def send_digest() -> tuple[bool, str]:
    if not RESEND_API_KEY:
        return False, "RESEND_API_KEY not set in environment variables"

    admin_url = os.getenv("RAILWAY_PUBLIC_DOMAIN", "web-production-13ce5.up.railway.app")
    events    = gather_events()
    month     = datetime.now().strftime("%B %Y")
    subject   = f"🎭 Tamil Events Digest — {month} ({len(events)} found)"

    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type":  "application/json",
            },
            json={
                "from":    DIGEST_FROM,
                "to":      [DIGEST_TO],
                "subject": subject,
                "html":    _build_html(events, admin_url),
            },
            timeout=20,
        )
        if resp.status_code in (200, 201):
            return True, f"Digest sent — {len(events)} events found"
        return False, f"Resend API error {resp.status_code}: {resp.text}"
    except Exception as e:
        return False, f"Send failed: {str(e)}"
