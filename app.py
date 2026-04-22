import json
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, abort, render_template, redirect, url_for
from flask_cors import CORS

from scrapers.eventbrite      import fetch_events as fetch_eventbrite
from scrapers.tamil_culture   import fetch_events as fetch_tamil_culture
from scrapers.tamil_events_uk import fetch_events as fetch_uk
from scrapers.sangam          import fetch_events as fetch_sangam
from scrapers.facebook        import fetch_events as fetch_facebook

load_dotenv()

app = Flask(__name__)
CORS(app)

SEED_PATH   = Path(__file__).parent.parent / "TamilEvents" / "TamilEvents" / "Resources" / "SeedData.json"
ADMIN_PATH  = Path(__file__).parent / "admin_events.json"
ADMIN_KEY   = os.getenv("ADMIN_KEY", "tamilevents-admin-2026")


# ── Storage helpers ────────────────────────────────────────────────────────────

def load_seed():
    try:
        return json.loads(SEED_PATH.read_text())
    except Exception:
        return []

def load_admin_events():
    try:
        return json.loads(ADMIN_PATH.read_text())
    except Exception:
        return []

def save_admin_events(events):
    ADMIN_PATH.write_text(json.dumps(events, indent=2))

def deduplicate(events):
    seen, unique = set(), []
    for e in events:
        key = (e.get("title", "").lower(), e.get("date", ""))
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique


# ── Public API (used by iOS app) ──────────────────────────────────────────────

@app.route("/events", methods=["GET"])
def events():
    all_events  = load_admin_events()
    all_events += fetch_eventbrite()
    all_events += fetch_tamil_culture()
    all_events += fetch_uk()
    all_events += fetch_sangam()
    all_events += fetch_facebook()

    if not all_events:
        all_events = load_seed()

    return jsonify(deduplicate(all_events))


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


# ── Admin web panel ────────────────────────────────────────────────────────────

@app.route("/admin")
def admin_panel():
    key = request.args.get("key", "")
    if key != ADMIN_KEY:
        return """
        <form style="font-family:sans-serif;max-width:320px;margin:80px auto">
          <h2 style="margin-bottom:16px">Tamil Events Admin</h2>
          <input name="key" type="password" placeholder="Admin password"
                 style="width:100%;padding:10px;border:1px solid #ccc;border-radius:8px;font-size:14px"/>
          <button style="margin-top:10px;width:100%;padding:10px;background:#7233CC;
                         color:white;border:none;border-radius:8px;font-size:14px;cursor:pointer">
            Login
          </button>
        </form>""", 401

    return render_template("admin.html",
                           events=load_admin_events(),
                           admin_key=key,
                           message=request.args.get("msg"))


@app.route("/admin/add", methods=["POST"])
def admin_add():
    key = request.form.get("admin_key", "")
    if key != ADMIN_KEY:
        abort(401)

    # Convert time from HH:MM to "HH:MM AM/PM"
    raw_time = request.form.get("time", "")
    try:
        from datetime import datetime
        t = datetime.strptime(raw_time, "%H:%M")
        friendly_time = t.strftime("%-I:%M %p")
    except Exception:
        friendly_time = raw_time

    new_event = {
        "id":          str(uuid.uuid4()),
        "title":       request.form.get("title", ""),
        "description": request.form.get("description", ""),
        "date":        request.form.get("date", ""),
        "time":        friendly_time,
        "city":        request.form.get("city", ""),
        "country":     request.form.get("country", ""),
        "location":    request.form.get("location", ""),
        "address":     request.form.get("address", ""),
        "image":       request.form.get("image", ""),
        "url":         request.form.get("url", ""),
        "category":    request.form.get("category", "Cultural"),
        "source":      "admin",
        "is_free":     request.form.get("is_free") == "true",
        "organizer":   request.form.get("organizer", ""),
    }

    events = load_admin_events()
    events.append(new_event)
    save_admin_events(events)

    return redirect(f"/admin?key={key}&msg=Event+added+successfully!")


@app.route("/admin/delete/<event_id>", methods=["POST"])
def admin_delete(event_id):
    key = request.form.get("admin_key", "")
    if key != ADMIN_KEY:
        abort(401)

    events  = load_admin_events()
    updated = [e for e in events if e["id"] != event_id]
    save_admin_events(updated)

    return redirect(f"/admin?key={key}&msg=Event+deleted.")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)
