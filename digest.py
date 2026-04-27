import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
DIGEST_FROM    = os.getenv("DIGEST_FROM", "Tamil Events <onboarding@resend.dev>")
DIGEST_TO      = os.getenv("DIGEST_EMAIL", "tamilevents00@gmail.com")
ADMIN_KEY      = os.getenv("ADMIN_KEY", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# Known Tamil event websites to check directly
TAMIL_SITES = [
    {
        "name":     "Tamil Culture",
        "url":      "https://www.tamilculture.ca/events",
        "selectors": ["h2 a", "h3 a", ".tribe-event-url", ".entry-title a"],
    },
    {
        "name":     "Tamil Events UK",
        "url":      "https://www.tamilevents.co.uk",
        "selectors": ["h2 a", "h3 a", ".event-title a", "article h2"],
    },
    {
        "name":     "Sangam.org",
        "url":      "https://www.sangam.org/events",
        "selectors": ["h2 a", "h3 a", ".event a"],
    },
    {
        "name":     "Tamil Guardian Events",
        "url":      "https://www.tamilguardian.com/category/culture",
        "selectors": ["h2 a", "h3 a", ".post-title a"],
    },
    {
        "name":     "Ilankai Tamil Events",
        "url":      "https://www.ilangaitamilsangam.com/events",
        "selectors": ["h2 a", "h3 a", ".tribe-event a"],
    },
]

# Bing search — more bot-friendly than DuckDuckGo
SEARCH_QUERIES = [
    "tamil cultural events 2026",
    "bharatanatyam carnatic concert 2026",
    "tamil food festival 2026",
    "kollywood dance show 2026",
]


def _bing_search(query: str) -> list[dict]:
    try:
        resp = requests.get(
            "https://www.bing.com/search",
            params={"q": query, "count": "8"},
            headers=HEADERS,
            timeout=12,
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for r in soup.select("li.b_algo")[:5]:
            title_el = r.select_one("h2 a")
            snippet  = r.select_one(".b_caption p")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if len(title) < 8:
                continue
            results.append({
                "title":   title,
                "url":     title_el.get("href", ""),
                "snippet": snippet.get_text(strip=True) if snippet else "",
                "source":  "Bing search",
            })
        return results
    except Exception:
        return []


def _scrape_site(site: dict) -> list[dict]:
    try:
        resp = requests.get(site["url"], headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        seen = set()
        for sel in site["selectors"]:
            for el in soup.select(sel)[:6]:
                title = el.get_text(strip=True)
                href  = el.get("href", site["url"])
                if len(title) < 8 or title.lower() in seen:
                    continue
                seen.add(title.lower())
                results.append({
                    "title":   title,
                    "url":     href if href.startswith("http") else site["url"],
                    "snippet": "",
                    "source":  site["name"],
                })
        return results
    except Exception:
        return []


def gather_events() -> list[dict]:
    found = []
    seen  = set()

    # 1. Bing search
    for q in SEARCH_QUERIES:
        for r in _bing_search(q):
            key = r["title"].lower()[:50]
            if key not in seen:
                seen.add(key)
                found.append(r)

    # 2. Direct Tamil sites
    for site in TAMIL_SITES:
        for r in _scrape_site(site):
            key = r["title"].lower()[:50]
            if key not in seen:
                seen.add(key)
                found.append(r)

    return found[:35]


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
