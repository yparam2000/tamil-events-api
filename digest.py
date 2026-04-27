import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")      # optional — serper.dev free 2500/mo
DIGEST_FROM    = os.getenv("DIGEST_FROM", "Tamil Events <onboarding@resend.dev>")
DIGEST_TO      = os.getenv("DIGEST_EMAIL", "tamilevents00@gmail.com")
ADMIN_KEY      = os.getenv("ADMIN_KEY", "")

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection":      "keep-alive",
}

CITIES = [
    "Toronto", "London", "Sydney", "Melbourne",
    "Singapore", "Dubai", "Kuala Lumpur", "Chennai",
]

SEARCH_QUERIES = [
    "Tamil events {city} 2026",
    "Bharatanatyam carnatic concert {city} 2026",
    "Tamil cultural festival {city} 2026",
    "Kollywood music show {city} 2026",
]

ALLEVENTS_SLUGS = {
    "Toronto":      "toronto",
    "London":       "london",
    "Sydney":       "sydney",
    "Melbourne":    "melbourne",
    "Singapore":    "singapore",
    "Dubai":        "dubai",
    "Kuala Lumpur": "kuala-lumpur",
    "Chennai":      "chennai",
}

EVENTBRITE_SLUGS = {
    "Toronto":      "canada--toronto",
    "London":       "united-kingdom--london",
    "Sydney":       "australia--sydney",
    "Melbourne":    "australia--melbourne",
    "Singapore":    "singapore--singapore",
    "Dubai":        "united-arab-emirates--dubai",
    "Kuala Lumpur": "malaysia--kuala-lumpur",
    "Chennai":      "india--chennai",
}


# ── Search engines ─────────────────────────────────────────────────────────────

def _serper_search(query: str, city: str) -> list[dict]:
    """Google search via Serper.dev — requires SERPER_API_KEY (free 2500/mo)."""
    if not SERPER_API_KEY:
        return []
    try:
        resp = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            json={"q": query, "num": 8},
            timeout=12,
        )
        results = []
        for r in resp.json().get("organic", [])[:6]:
            title = r.get("title", "")
            if len(title) < 8:
                continue
            results.append({
                "title":   title,
                "url":     r.get("link", ""),
                "snippet": r.get("snippet", ""),
                "city":    city,
                "source":  "Google",
            })
        return results
    except Exception:
        return []


def _ddg_search(query: str, city: str) -> list[dict]:
    """DuckDuckGo lite HTML search — no API key, works from servers."""
    try:
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query, "kl": "us-en"},
            headers=HEADERS,
            timeout=14,
        )
        soup    = BeautifulSoup(resp.text, "html.parser")
        results = []
        for r in soup.select("div.result")[:6]:
            title_el   = r.select_one("a.result__a")
            snippet_el = r.select_one("a.result__snippet")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if len(title) < 8:
                continue
            href = title_el.get("href", "")
            # DDG wraps URLs — extract real URL from uddg param
            if "uddg=" in href:
                from urllib.parse import urlparse, parse_qs, unquote
                qs   = parse_qs(urlparse(href).query)
                href = unquote(qs.get("uddg", [href])[0])
            results.append({
                "title":   title,
                "url":     href,
                "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                "city":    city,
                "source":  "DuckDuckGo",
            })
        return results
    except Exception:
        return []


# ── Event site scrapers ────────────────────────────────────────────────────────

def _allevents_city(city: str) -> list[dict]:
    slug = ALLEVENTS_SLUGS.get(city)
    if not slug:
        return []
    url = f"https://allevents.in/{slug}/tamil"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=14)
        if resp.status_code != 200:
            return []
        soup    = BeautifulSoup(resp.text, "html.parser")
        results = []
        seen    = set()
        for el in soup.select("h3.event-title, .event-title a, li.item h3, "
                              "h2.title a, .title a, h3 a")[:10]:
            title = el.get_text(strip=True)
            if len(title) < 8 or title.lower() in seen:
                continue
            seen.add(title.lower())
            link = el if el.name == "a" else el.find("a")
            href = link.get("href", url) if link else url
            results.append({
                "title":   title,
                "url":     href if href.startswith("http") else url,
                "snippet": "",
                "city":    city,
                "source":  "AllEvents.in",
            })
        return results
    except Exception:
        return []


def _eventbrite_city(city: str) -> list[dict]:
    slug = EVENTBRITE_SLUGS.get(city)
    if not slug:
        return []
    results = []
    seen    = set()
    for kw in ["tamil", "bharatanatyam", "carnatic"]:
        url = f"https://www.eventbrite.com/d/{slug}/{kw}--events/"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=14)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            for el in soup.select("h3.eds-event-card__formatted-name--is-clamped, "
                                  "h3.Typography_root__487rx, "
                                  "div[data-testid='event-card'] h3, "
                                  "article h3, .event-title")[:6]:
                title = el.get_text(strip=True)
                if len(title) < 8 or title.lower() in seen:
                    continue
                seen.add(title.lower())
                parent = el.find_parent("a") or el.find_parent("article")
                href   = parent.get("href", url) if parent else url
                if href and not href.startswith("http"):
                    href = "https://www.eventbrite.com" + href
                results.append({
                    "title":   title,
                    "url":     href or url,
                    "snippet": "",
                    "city":    city,
                    "source":  "Eventbrite",
                })
        except Exception:
            continue
    return results


def _tamilculture_ca() -> list[dict]:
    try:
        resp = requests.get("https://www.tamilculture.ca/events", headers=HEADERS, timeout=14)
        if resp.status_code != 200:
            return []
        soup    = BeautifulSoup(resp.text, "html.parser")
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
                "snippet": "",
                "city":    "Toronto",
                "source":  "TamilCulture.ca",
            })
        return results
    except Exception:
        return []


def _tamilevents_uk() -> list[dict]:
    try:
        resp = requests.get("https://www.tamilevents.co.uk", headers=HEADERS, timeout=14)
        if resp.status_code != 200:
            return []
        soup    = BeautifulSoup(resp.text, "html.parser")
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
                "snippet": "",
                "city":    "London",
                "source":  "TamilEvents UK",
            })
        return results
    except Exception:
        return []


# ── Gather all events ──────────────────────────────────────────────────────────

def gather_events() -> list[dict]:
    found = []
    seen  = set()

    def _add(items):
        for r in items:
            key = r["title"].lower()[:60]
            if key not in seen:
                seen.add(key)
                found.append(r)

    # 1. Search engines — per city
    for city in CITIES:
        for q_template in SEARCH_QUERIES[:2]:   # 2 queries per city to keep it fast
            q = q_template.format(city=city)
            if SERPER_API_KEY:
                _add(_serper_search(q, city))
            else:
                _add(_ddg_search(q, city))

    # 2. AllEvents.in — great South Asian coverage
    for city in CITIES:
        _add(_allevents_city(city))

    # 3. Eventbrite per city
    for city in CITIES:
        _add(_eventbrite_city(city))

    # 4. Tamil-specific sites
    _add(_tamilculture_ca())
    _add(_tamilevents_uk())

    return found[:60]


# ── Email HTML ─────────────────────────────────────────────────────────────────

SOURCE_COLORS = {
    "Google":         "#4285F4",
    "DuckDuckGo":     "#DE5833",
    "Eventbrite":     "#F05537",
    "AllEvents.in":   "#00B894",
    "TamilCulture.ca":"#7233CC",
    "TamilEvents UK": "#7233CC",
}

CITY_FLAGS = {
    "Toronto":      "🇨🇦",
    "London":       "🇬🇧",
    "Sydney":       "🇦🇺",
    "Melbourne":    "🇦🇺",
    "Singapore":    "🇸🇬",
    "Dubai":        "🇦🇪",
    "Kuala Lumpur": "🇲🇾",
    "Chennai":      "🇮🇳",
}


def _build_html(events: list[dict], admin_url: str) -> str:
    today = datetime.now().strftime("%B %-d, %Y")
    admin = f"https://{admin_url}/admin?key={ADMIN_KEY}"

    # Group by city
    by_city: dict[str, list[dict]] = {}
    for e in events:
        city = e.get("city", "Other")
        by_city.setdefault(city, []).append(e)

    if not by_city:
        content = f"""
        <div style="padding:48px 32px;text-align:center;color:#6e6e73">
          <div style="font-size:40px;margin-bottom:16px">🔍</div>
          <div style="font-size:16px;font-weight:600;color:#333;margin-bottom:8px">No events found today</div>
          <div style="font-size:14px;margin-bottom:24px">The search didn't turn up results — try again tomorrow or add events manually.</div>
          <a href="{admin}" style="background:#7233CC;color:white;padding:12px 24px;
             border-radius:10px;font-size:14px;font-weight:600;text-decoration:none;display:inline-block">
            Open Admin Panel
          </a>
        </div>"""
    else:
        sections = ""
        for city in CITIES + [c for c in by_city if c not in CITIES]:
            city_events = by_city.get(city, [])
            if not city_events:
                continue
            flag = CITY_FLAGS.get(city, "🌍")
            cards = ""
            for e in city_events:
                url     = e.get("url") or "#"
                snippet = e.get("snippet", "")
                src     = e.get("source", "")
                color   = SOURCE_COLORS.get(src, "#888")
                cards += f"""
                <div style="border:1px solid #eee;border-radius:10px;padding:14px 16px;
                            margin-bottom:10px;background:white">
                  <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px">
                    <div style="flex:1;min-width:0">
                      <a href="{url}" style="font-size:14px;font-weight:600;color:#1a1a2e;
                         text-decoration:none;line-height:1.4;display:block">{e['title']}</a>
                      {"<div style='font-size:12px;color:#6e6e73;margin-top:4px;line-height:1.4'>" + snippet[:120] + "</div>" if snippet else ""}
                      <div style="margin-top:8px">
                        <span style="background:{color}20;color:{color};font-size:11px;font-weight:600;
                               padding:3px 8px;border-radius:20px;display:inline-block">{src}</span>
                      </div>
                    </div>
                    <div style="flex-shrink:0">
                      <a href="{admin}" style="background:#7233CC;color:white;padding:8px 14px;
                         border-radius:8px;font-size:12px;font-weight:600;text-decoration:none;
                         white-space:nowrap;display:inline-block">
                        + Add
                      </a>
                    </div>
                  </div>
                </div>"""

            sections += f"""
            <div style="margin-bottom:28px">
              <div style="font-size:13px;font-weight:700;color:#6e6e73;text-transform:uppercase;
                          letter-spacing:0.8px;margin-bottom:12px;padding-bottom:8px;
                          border-bottom:2px solid #f0f0f5">
                {flag} {city} &nbsp;<span style="font-weight:400;font-size:12px;color:#aaa">
                  {len(city_events)} event{"s" if len(city_events) != 1 else ""} found</span>
              </div>
              {cards}
            </div>"""

        content = f'<div style="padding:24px 28px">{sections}</div>'

    total = sum(len(v) for v in by_city.values()) if by_city else 0

    return f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,sans-serif;
             background:#f0f0f5;-webkit-font-smoothing:antialiased">
  <div style="max-width:660px;margin:28px auto 40px">

    <!-- Header -->
    <div style="background:linear-gradient(135deg,#7233CC 0%,#F27A10 100%);
                border-radius:16px 16px 0 0;padding:28px 32px 24px">
      <div style="font-size:24px;font-weight:800;color:white;letter-spacing:-0.5px">
        🎭 Tamil Events Digest
      </div>
      <div style="font-size:13px;color:rgba(255,255,255,0.80);margin-top:4px">{today}</div>
    </div>

    <!-- Summary bar -->
    <div style="background:#1a1a2e;padding:14px 32px;display:flex;align-items:center;
                justify-content:space-between">
      <div style="color:white;font-size:14px;font-weight:600">
        {total} potential events found across {len(by_city)} {"cities" if len(by_city) != 1 else "city"}
      </div>
      <a href="{admin}" style="background:#7233CC;color:white;padding:8px 16px;border-radius:8px;
         font-size:12px;font-weight:600;text-decoration:none">Open Admin →</a>
    </div>

    <!-- Body -->
    <div style="background:#f8f8fc;border-radius:0 0 16px 16px;overflow:hidden">
      {content}

      <!-- Footer -->
      <div style="padding:16px 32px;font-size:11px;color:#aaa;border-top:1px solid #eee;
                  background:white;text-align:center">
        Tamil Events daily digest · sent every day at 8am UTC ·
        <a href="{admin}" style="color:#7233CC;text-decoration:none;font-weight:600">Admin Panel</a>
      </div>
    </div>

  </div>
</body>
</html>"""


# ── Send ───────────────────────────────────────────────────────────────────────

def send_digest() -> tuple[bool, str]:
    if not RESEND_API_KEY:
        return False, "RESEND_API_KEY not set in environment variables"

    admin_url = os.getenv("RAILWAY_PUBLIC_DOMAIN", "web-production-13ce5.up.railway.app")
    events    = gather_events()
    today     = datetime.now().strftime("%B %-d")
    subject   = f"🎭 Tamil Events Digest — {today} ({len(events)} events found)"

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
