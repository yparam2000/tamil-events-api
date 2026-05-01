import os
import requests
from datetime import datetime

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
DIGEST_FROM    = os.getenv("DIGEST_FROM", "Tamil Events <onboarding@resend.dev>")
DIGEST_TO      = os.getenv("DIGEST_EMAIL", "tamilevents00@gmail.com")
ADMIN_KEY      = os.getenv("ADMIN_KEY", "")


def _build_html(admin_url: str) -> str:
    today = datetime.now().strftime("%B %d, %Y").replace(" 0", " ")
    admin = f"https://{admin_url}/admin?key={ADMIN_KEY}"

    return f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,sans-serif;
             background:#f0f0f5">
  <div style="max-width:580px;margin:32px auto 48px">

    <!-- Header -->
    <div style="background:linear-gradient(135deg,#7233CC 0%,#F27A10 100%);
                border-radius:16px 16px 0 0;padding:28px 32px 24px">
      <div style="font-size:24px;font-weight:800;color:white;letter-spacing:-0.5px">
        🎭 Tamil Events
      </div>
      <div style="font-size:13px;color:rgba(255,255,255,0.80);margin-top:4px">
        Daily reminder — {today}
      </div>
    </div>

    <!-- Body -->
    <div style="background:white;padding:32px">
      <p style="font-size:16px;font-weight:600;color:#1a1a2e;margin:0 0 8px">
        Time to check for new Tamil events! 👋
      </p>
      <p style="font-size:14px;color:#6e6e73;margin:0 0 28px;line-height:1.6">
        Open the admin panel to add any upcoming events you've spotted —
        concerts, food festivals, cultural shows, temple events, or anything
        your community would love.
      </p>

      <a href="{admin}"
         style="display:inline-block;background:linear-gradient(135deg,#7233CC,#F27A10);
                color:white;font-size:15px;font-weight:700;text-decoration:none;
                padding:14px 32px;border-radius:12px;letter-spacing:0.2px">
        Open Admin Panel →
      </a>

      <div style="margin-top:32px;padding-top:24px;border-top:1px solid #f0f0f5">
        <p style="font-size:13px;font-weight:600;color:#333;margin:0 0 12px">
          Quick tips for adding events:
        </p>
        <ul style="font-size:13px;color:#6e6e73;margin:0;padding-left:20px;line-height:2">
          <li>Use a clear title — e.g. <em>"Tamil New Year Gala — London 2026"</em></li>
          <li>Always add the ticket / RSVP link so users can book</li>
          <li>Pick the right city so users see it in their feed</li>
          <li>Choose an image from the gallery to make the card look great</li>
        </ul>
      </div>
    </div>

    <!-- Footer -->
    <div style="background:#f8f8fc;border-radius:0 0 16px 16px;padding:16px 32px;
                font-size:11px;color:#aaa;text-align:center;border-top:1px solid #eee">
      Tamil Events daily digest · sent every day at 8am UTC ·
      <a href="{admin}" style="color:#7233CC;text-decoration:none;font-weight:600">Admin Panel</a>
    </div>

  </div>
</body>
</html>"""


def send_digest() -> tuple[bool, str]:
    if not RESEND_API_KEY:
        return False, "RESEND_API_KEY not set in environment variables"

    admin_url = os.getenv("RAILWAY_PUBLIC_DOMAIN", "web-production-13ce5.up.railway.app")
    today     = datetime.now().strftime("%B %d").replace(" 0", " ")
    subject   = f"🎭 Tamil Events — add events for {today}"

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
                "html":    _build_html(admin_url),
            },
            timeout=15,
        )
        if resp.status_code in (200, 201):
            return True, "Daily reminder sent"
        return False, f"Resend error {resp.status_code}: {resp.text}"
    except Exception as e:
        return False, f"Send failed: {str(e)}"
