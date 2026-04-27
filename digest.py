import os
import smtplib
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

GMAIL_USER     = os.getenv("GMAIL_USER", "tamilevents00@gmail.com")
GMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
DIGEST_TO      = os.getenv("DIGEST_EMAIL", "tamilevents00@gmail.com")
ADMIN_URL      = os.getenv("RAILWAY_PUBLIC_DOMAIN", "web-production-13ce5.up.railway.app")
ADMIN_KEY      = os.getenv("ADMIN_KEY", "")

SEARCH_QUERIES = [
    "tamil cultural events 2026",
    "tamil festival events toronto london singapore",
    "bharatanatyam carnatic music event 2026",
    "kollywood tamil entertainment show 2026",
    "tamil food festival 2026",
    "pongal diwali tamil community event",
]

TAMIL_SITES = [
    ("tamilculture.ca",    "https://www.tamilculture.ca/events"),
    ("tamilevents.co.uk",  "https://www.tamilevents.co.uk"),
    ("sangam.org",         "https://www.sangam.org/events"),
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TamilEventsBot/1.0)"}


def _ddg_search(query: str) -> list[dict]:
    """DuckDuckGo HTML search — no API key needed."""
    try:
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers=HEADERS,
            timeout=10,
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for r in soup.select(".result")[:4]:
            title_el = r.select_one(".result__title a")
            snippet  = r.select_one(".result__snippet")
            if not title_el:
                continue
            results.append({
                "title":   title_el.get_text(strip=True),
                "url":     title_el.get("href", ""),
                "snippet": snippet.get_text(strip=True) if snippet else "",
                "source":  "web search",
            })
        return results
    except Exception:
        return []


def _site_scrape(name: str, url: str) -> list[dict]:
    """Best-effort scrape of a Tamil event site."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for tag in soup.find_all(["h2", "h3"], limit=8):
            text = tag.get_text(strip=True)
            if len(text) > 10:
                link = tag.find("a")
                results.append({
                    "title":   text,
                    "url":     link["href"] if link and link.get("href") else url,
                    "snippet": "",
                    "source":  name,
                })
        return results
    except Exception:
        return []


def gather_events() -> list[dict]:
    found = []
    seen  = set()

    for q in SEARCH_QUERIES:
        for r in _ddg_search(q):
            key = r["title"].lower()[:60]
            if key not in seen:
                seen.add(key)
                found.append(r)

    for name, url in TAMIL_SITES:
        for r in _site_scrape(name, url):
            key = r["title"].lower()[:60]
            if key not in seen:
                seen.add(key)
                found.append(r)

    return found[:30]


def _build_html(events: list[dict]) -> str:
    month = datetime.now().strftime("%B %Y")
    admin = f"https://{ADMIN_URL}/admin?key={ADMIN_KEY}"

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
          <td style="padding:14px 16px;border-bottom:1px solid #f0f0f5;white-space:nowrap">
            <a href="{admin}" style="background:#7233CC;color:white;padding:6px 14px;
               border-radius:8px;font-size:12px;font-weight:600;text-decoration:none">
              Add to App
            </a>
          </td>
        </tr>"""

    return f"""
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f5f7">
  <div style="max-width:640px;margin:32px auto;background:white;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08)">

    <!-- Header -->
    <div style="background:linear-gradient(135deg,#7233CC,#F27A10);padding:28px 32px">
      <div style="font-size:22px;font-weight:800;color:white">🎭 Tamil Events</div>
      <div style="font-size:14px;color:rgba(255,255,255,0.85);margin-top:4px">
        Daily Digest — {month}
      </div>
    </div>

    <!-- Intro -->
    <div style="padding:20px 32px 8px;font-size:14px;color:#333">
      Found <strong>{len(events)}</strong> potential Tamil events from across the web.
      Review them below and add the ones you want to the app.
    </div>

    <!-- Table -->
    <table style="width:100%;border-collapse:collapse">
      <thead>
        <tr style="background:#f5f5f7">
          <th style="text-align:left;padding:10px 16px;font-size:11px;color:#6e6e73;text-transform:uppercase;letter-spacing:0.5px">
            Event / Source
          </th>
          <th style="padding:10px 16px;font-size:11px;color:#6e6e73;text-transform:uppercase;letter-spacing:0.5px">
            Action
          </th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>

    <!-- Footer -->
    <div style="padding:20px 32px;font-size:12px;color:#aaa;border-top:1px solid #f0f0f5">
      <a href="{admin}" style="color:#7233CC;font-weight:600;text-decoration:none">Open Admin Panel</a>
      &nbsp;·&nbsp; Tamil Events daily digest
    </div>
  </div>
</body>
</html>"""


def send_digest() -> tuple[bool, str]:
    if not GMAIL_PASSWORD:
        return False, "GMAIL_APP_PASSWORD not set in environment variables"

    events = gather_events()
    if not events:
        return False, "No events found"

    month = datetime.now().strftime("%B %Y")
    msg   = MIMEMultipart("alternative")
    msg["Subject"] = f"🎭 Tamil Events Digest — {month} ({len(events)} found)"
    msg["From"]    = GMAIL_USER
    msg["To"]      = DIGEST_TO
    msg.attach(MIMEText(_build_html(events), "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_USER, DIGEST_TO, msg.as_string())
        return True, f"Sent digest with {len(events)} events to {DIGEST_TO}"
    except Exception as e:
        return False, str(e)
