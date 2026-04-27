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


@app.route("/admin/test-email")
def test_email():
    import smtplib, os
    user = os.getenv("GMAIL_USER", "")
    pwd  = os.getenv("GMAIL_APP_PASSWORD", "")
    result = {
        "gmail_user_set":     bool(user),
        "gmail_user":         user,
        "password_set":       bool(pwd),
        "password_length":    len(pwd),
    }
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(user, pwd)
            result["login"] = "SUCCESS"
    except smtplib.SMTPAuthenticationError as e:
        result["login"] = f"AUTH FAILED: {e}"
    except Exception as e:
        result["login"] = f"ERROR: {e}"
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

scheduler = BackgroundScheduler(timezone="UTC")
scheduler.add_job(_scheduled_digest, "cron", hour=8, minute=0)  # 8am UTC daily
scheduler.start()


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)
