import json
import os
import uuid
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from flask import Flask, jsonify, request, abort, render_template, redirect, url_for
from flask_cors import CORS
from digest import send_digest


load_dotenv()

app = Flask(__name__)
CORS(app)

SEED_PATH    = Path(__file__).parent.parent / "TamilEvents" / "TamilEvents" / "Resources" / "SeedData.json"
ADMIN_PATH   = Path(__file__).parent / "admin_events.json"
PENDING_PATH = Path(__file__).parent / "pending_events.json"
ADMIN_KEY    = os.getenv("ADMIN_KEY", "")


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

def load_pending():
    try:
        return json.loads(PENDING_PATH.read_text())
    except Exception:
        return []

def save_pending(events):
    PENDING_PATH.write_text(json.dumps(events, indent=2))

def deduplicate(events):
    seen, unique = set(), []
    for e in events:
        key = (e.get("title", "").lower(), e.get("date", ""))
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique

def friendly_time(raw_time):
    if not raw_time:
        return ""
    try:
        from datetime import datetime
        t = datetime.strptime(raw_time, "%H:%M")
        return t.strftime("%-I:%M %p")
    except Exception:
        return raw_time

def display_time(start_time, end_time):
    if start_time and end_time:
        return f"{start_time} - {end_time}"
    return start_time or end_time or ""

def parse_locations(form):
    primary = {
        "location": form.get("location", "").strip(),
        "address":  form.get("address", "").strip(),
        "city":     form.get("city", "").strip(),
        "country":  form.get("country", "").strip(),
    }

    locations = []
    if any(primary.values()):
        locations.append(primary)

    for line in form.get("additional_locations", "").splitlines():
        parts = [p.strip() for p in line.split("|")]
        if not any(parts):
            continue
        while len(parts) < 4:
            parts.append("")
        locations.append({
            "location": parts[0],
            "address":  parts[1],
            "city":     parts[2],
            "country":  parts[3],
        })

    return locations

def event_from_form(form, event_id=None):
    locations = parse_locations(form)
    primary = locations[0] if locations else {
        "location": "",
        "address": "",
        "city": "",
        "country": "",
    }
    start_time_raw = form.get("start_time") or form.get("time", "")
    end_time_raw   = form.get("end_time", "")
    start_time     = friendly_time(start_time_raw)
    end_time       = friendly_time(end_time_raw)

    return {
        "id":             event_id or str(uuid.uuid4()),
        "title":          form.get("title", ""),
        "description":    form.get("description", ""),
        "date":           form.get("date", ""),
        "time":           display_time(start_time, end_time),
        "start_time":     start_time,
        "end_time":       end_time,
        "start_time_raw": start_time_raw,
        "end_time_raw":   end_time_raw,
        "city":           primary.get("city", ""),
        "country":        primary.get("country", ""),
        "location":       primary.get("location", ""),
        "address":        primary.get("address", ""),
        "locations":      locations,
        "image":          form.get("image", ""),
        "url":            form.get("url", ""),
        "category":       form.get("category", "Cultural"),
        "source":         "admin",
        "is_free":        form.get("is_free") == "true",
        "organizer":      form.get("organizer", ""),
    }


# ── Public API (used by iOS app) ──────────────────────────────────────────────

@app.route("/events", methods=["GET"])
def events():
    all_events = load_admin_events()

    if not all_events:
        all_events = load_seed()

    return jsonify(deduplicate(all_events))


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


# ── User event submission ──────────────────────────────────────────────────────

@app.route("/submit", methods=["POST"])
def user_submit():
    data = request.get_json(silent=True)
    if not data or not data.get("title") or not data.get("date"):
        return jsonify({"error": "Missing required fields"}), 400

    pending = load_pending()
    pending.append({
        "id":          str(uuid.uuid4()),
        "title":       data.get("title", ""),
        "description": data.get("description", ""),
        "date":        data.get("date", ""),
        "time":        data.get("time", ""),
        "city":        data.get("city", ""),
        "country":     data.get("country", ""),
        "location":    data.get("location", ""),
        "address":     "",
        "image":       "",
        "url":         "",
        "category":    data.get("category", "Cultural"),
        "source":      "user_submission",
        "is_free":     False,
        "organizer":   data.get("organizer", ""),
        "contact":     data.get("contact", ""),
        "status":      "pending",
    })
    save_pending(pending)
    return jsonify({"status": "received"}), 200


@app.route("/admin/approve/<event_id>", methods=["POST"])
def admin_approve(event_id):
    key = request.form.get("admin_key", "")
    if key != ADMIN_KEY:
        abort(401)

    pending = load_pending()
    match   = next((e for e in pending if e["id"] == event_id), None)
    if not match:
        abort(404)

    match.pop("contact", None)
    match.pop("status",  None)
    match["source"] = "admin"

    events = load_admin_events()
    events.append(match)
    save_admin_events(events)
    save_pending([e for e in pending if e["id"] != event_id])

    return redirect(f"/admin?key={key}&msg=Event+approved+and+published!")


@app.route("/admin/reject/<event_id>", methods=["POST"])
def admin_reject(event_id):
    key = request.form.get("admin_key", "")
    if key != ADMIN_KEY:
        abort(401)

    pending = load_pending()
    save_pending([e for e in pending if e["id"] != event_id])
    return redirect(f"/admin?key={key}&msg=Submission+rejected.")


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
                           pending=load_pending(),
                           admin_key=key,
                           message=request.args.get("msg"))


@app.route("/admin/add", methods=["POST"])
def admin_add():
    key = request.form.get("admin_key", "")
    if key != ADMIN_KEY:
        abort(401)

    events = load_admin_events()
    events.append(event_from_form(request.form))
    save_admin_events(events)

    return redirect(f"/admin?key={key}&msg=Event+added+successfully!")


@app.route("/admin/edit/<event_id>", methods=["POST"])
def admin_edit(event_id):
    key = request.form.get("admin_key", "")
    if key != ADMIN_KEY:
        abort(401)

    events = load_admin_events()
    for idx, event in enumerate(events):
        if event.get("id") == event_id:
            updated = event_from_form(request.form, event_id=event_id)
            updated["source"] = event.get("source", "admin")
            events[idx] = updated
            save_admin_events(events)
            return redirect(f"/admin?key={key}&msg=Event+updated.")

    abort(404)


@app.route("/admin/delete/<event_id>", methods=["POST"])
def admin_delete(event_id):
    key = request.form.get("admin_key", "")
    if key != ADMIN_KEY:
        abort(401)

    events  = load_admin_events()
    updated = [e for e in events if e["id"] != event_id]
    save_admin_events(updated)

    return redirect(f"/admin?key={key}&msg=Event+deleted.")


@app.route("/admin/test-email")
def test_email():
    import requests as req
    api_key = os.getenv("RESEND_API_KEY", "")
    result  = {"resend_key_set": bool(api_key), "resend_key_length": len(api_key)}
    if not api_key:
        result["status"] = "RESEND_API_KEY not set"
        return jsonify(result)
    try:
        resp = req.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "from":    "Tamil Events <onboarding@resend.dev>",
                "to":      ["tamilevents00@gmail.com"],
                "subject": "Tamil Events — test email",
                "html":    "<p>Test from Tamil Events backend. Email is working!</p>",
            },
            timeout=15,
        )
        result["http_status"] = resp.status_code
        result["status"] = "SUCCESS" if resp.status_code in (200, 201) else f"FAILED: {resp.text}"
    except Exception as e:
        result["status"] = f"ERROR: {e}"
    return jsonify(result)


@app.route("/admin/send-digest", methods=["POST"])
def admin_send_digest():
    key = request.form.get("admin_key", "")
    if key != ADMIN_KEY:
        abort(401)
    ok, msg = send_digest()
    status  = "success" if ok else "error"
    return redirect(f"/admin?key={key}&msg={msg.replace(' ', '+')}&digest={status}")


# ── Daily scheduler ────────────────────────────────────────────────────────────

def _scheduled_digest():
    send_digest()

try:
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(_scheduled_digest, "cron", hour=8, minute=0)
    scheduler.start()
except Exception:
    pass


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)
