from __future__ import annotations

import datetime as dt
import os
import smtplib
from email.mime.text import MIMEText

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, render_template, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///todo.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(80), default="personal")
    frequency = db.Column(db.String(20), default="daily")
    due_date = db.Column(db.Date)
    progress = db.Column(db.Integer, default=0)
    completed = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow)


class TaskLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id"), nullable=False)
    done_on = db.Column(db.Date, nullable=False)
    note = db.Column(db.String(200), default="completed")


FREQUENCIES = {"daily", "weekly", "monthly", "once"}


def task_to_dict(task: Task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "category": task.category,
        "frequency": task.frequency,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "progress": task.progress,
        "completed": task.completed,
        "notes": task.notes or "",
        "sort_order": task.sort_order,
    }


def goal_to_dict(goal: Goal | None) -> dict:
    if not goal:
        return {}
    total_days = (goal.end_date - goal.start_date).days or 1
    elapsed = max(0, (dt.date.today() - goal.start_date).days)
    timeline_progress = max(0, min(100, int((elapsed / total_days) * 100)))
    return {
        "id": goal.id,
        "title": goal.title,
        "description": goal.description or "",
        "start_date": goal.start_date.isoformat(),
        "end_date": goal.end_date.isoformat(),
        "timeline_progress": timeline_progress,
    }


def dashboard_payload() -> dict:
    tasks = Task.query.all()
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t.completed])
    avg_progress = int(sum(t.progress for t in tasks) / total_tasks) if total_tasks else 0

    today = dt.date.today()
    seven_days_ago = today - dt.timedelta(days=6)
    logs = (
        db.session.query(TaskLog.done_on, func.count(TaskLog.id))
        .filter(TaskLog.done_on >= seven_days_ago)
        .group_by(TaskLog.done_on)
        .all()
    )
    log_map = {d.isoformat(): c for d, c in logs}
    daily_series = []
    for i in range(7):
        day = seven_days_ago + dt.timedelta(days=i)
        daily_series.append({"date": day.isoformat(), "count": log_map.get(day.isoformat(), 0)})

    return {
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "completion_rate": int((completed_tasks / total_tasks) * 100) if total_tasks else 0,
        "avg_progress": avg_progress,
        "daily_series": daily_series,
    }


def send_email_reminder(message: str) -> bool:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    to_email = os.getenv("REMINDER_EMAIL")
    if not all([smtp_host, smtp_user, smtp_pass, to_email]):
        return False

    msg = MIMEText(message)
    msg["Subject"] = "Daily Task Reminder"
    msg["From"] = smtp_user
    msg["To"] = to_email

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
    return True


def send_telegram_reminder(message: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False

    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": message},
        timeout=10,
    )
    response.raise_for_status()
    return True


def send_whatsapp_reminder(message: str) -> bool:
    phone = os.getenv("WHATSAPP_PHONE")
    api_key = os.getenv("WHATSAPP_API_KEY")
    if not phone or not api_key:
        return False

    requests.get(
        "https://api.callmebot.com/whatsapp.php",
        params={"phone": phone, "text": message, "apikey": api_key},
        timeout=10,
    ).raise_for_status()
    return True


def reminder_message() -> str:
    pending = Task.query.filter_by(completed=False).order_by(Task.sort_order.asc()).all()
    top_items = "\n".join([f"- {task.title} ({task.frequency})" for task in pending[:8]])
    return (
        "Your daily focus tasks:\n"
        f"{top_items if top_items else '- All done, great work!'}\n\n"
        "Keep going on your 3-month goal."
    )


def send_daily_reminders() -> dict:
    message = reminder_message()
    results = {}
    for channel, sender in {
        "email": send_email_reminder,
        "telegram": send_telegram_reminder,
        "whatsapp": send_whatsapp_reminder,
    }.items():
        try:
            results[channel] = sender(message)
        except Exception:
            results[channel] = False
    return results


@app.route("/")
def index():
    return render_template("index.html")


@app.get("/api/tasks")
def get_tasks():
    tasks = Task.query.order_by(Task.completed.asc(), Task.sort_order.asc(), Task.id.asc()).all()
    return jsonify([task_to_dict(t) for t in tasks])


@app.post("/api/tasks")
def create_task():
    payload = request.get_json(force=True)
    frequency = payload.get("frequency", "daily")
    if frequency not in FREQUENCIES:
        return jsonify({"error": "Invalid frequency"}), 400

    max_order = db.session.query(func.max(Task.sort_order)).scalar() or 0
    task = Task(
        title=payload["title"].strip(),
        category=payload.get("category", "personal").strip() or "personal",
        frequency=frequency,
        due_date=dt.date.fromisoformat(payload["due_date"]) if payload.get("due_date") else None,
        notes=payload.get("notes", "").strip(),
        sort_order=max_order + 1,
    )
    db.session.add(task)
    db.session.commit()
    return jsonify(task_to_dict(task)), 201


@app.patch("/api/tasks/<int:task_id>")
def update_task(task_id: int):
    task = Task.query.get_or_404(task_id)
    payload = request.get_json(force=True)

    for field in ["title", "category", "notes"]:
        if field in payload:
            setattr(task, field, str(payload[field]).strip())

    if "frequency" in payload and payload["frequency"] in FREQUENCIES:
        task.frequency = payload["frequency"]

    if "due_date" in payload:
        task.due_date = dt.date.fromisoformat(payload["due_date"]) if payload["due_date"] else None

    if "progress" in payload:
        task.progress = max(0, min(100, int(payload["progress"])))

    if "completed" in payload:
        task.completed = bool(payload["completed"])
        if task.completed and task.progress < 100:
            task.progress = 100

    db.session.commit()
    return jsonify(task_to_dict(task))


@app.delete("/api/tasks/<int:task_id>")
def delete_task(task_id: int):
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    return jsonify({"status": "deleted"})


@app.post("/api/tasks/reorder")
def reorder_tasks():
    payload = request.get_json(force=True)
    ordered_ids = payload.get("ordered_ids", [])
    for index, task_id in enumerate(ordered_ids):
        task = Task.query.get(task_id)
        if task:
            task.sort_order = index
            task.completed = bool(payload.get("completed", False))
    db.session.commit()
    return jsonify({"status": "ok"})


@app.post("/api/tasks/<int:task_id>/log")
def log_task(task_id: int):
    task = Task.query.get_or_404(task_id)
    done_on = request.json.get("done_on", dt.date.today().isoformat())
    log = TaskLog(task_id=task.id, done_on=dt.date.fromisoformat(done_on))
    db.session.add(log)
    if task.progress < 100:
        task.progress = min(100, task.progress + 10)
    db.session.commit()
    return jsonify({"status": "logged"})


@app.get("/api/dashboard")
def dashboard():
    return jsonify(dashboard_payload())


@app.get("/api/goal")
def get_goal():
    goal = Goal.query.order_by(Goal.id.desc()).first()
    return jsonify(goal_to_dict(goal))


@app.post("/api/goal")
def upsert_goal():
    payload = request.get_json(force=True)
    goal = Goal.query.order_by(Goal.id.desc()).first()
    if not goal:
        goal = Goal(
            title=payload["title"].strip(),
            description=payload.get("description", "").strip(),
            start_date=dt.date.fromisoformat(payload["start_date"]),
            end_date=dt.date.fromisoformat(payload["end_date"]),
        )
        db.session.add(goal)
    else:
        goal.title = payload["title"].strip()
        goal.description = payload.get("description", "").strip()
        goal.start_date = dt.date.fromisoformat(payload["start_date"])
        goal.end_date = dt.date.fromisoformat(payload["end_date"])

    db.session.commit()
    return jsonify(goal_to_dict(goal))


@app.post("/api/reminders/test")
def test_reminders():
    return jsonify(send_daily_reminders())


def seed_defaults() -> None:
    if Task.query.count() > 0:
        return
    defaults = [
        ("Drink green tea", "daily", "wellness"),
        ("Yoga", "daily", "fitness"),
        ("Gym", "daily", "fitness"),
        ("10k steps", "daily", "fitness"),
        ("Bike wash", "weekly", "lifestyle"),
        ("Finish one book", "weekly", "learning"),
    ]
    for idx, (title, frequency, category) in enumerate(defaults):
        db.session.add(Task(title=title, frequency=frequency, category=category, sort_order=idx + 1))
    db.session.commit()


with app.app_context():
    db.create_all()
    seed_defaults()

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(send_daily_reminders, "cron", hour=8, minute=0)
scheduler.start()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
