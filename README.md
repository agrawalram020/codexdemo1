# GoalFlow Flask Todo App

A single-page, interactive Flask todo dashboard to manage a 3-month goal and recurring tasks.

## Features
- Set and track a 3-month goal timeline.
- Create tasks with frequencies: daily, weekly, monthly, once.
- Drag-and-drop tasks between **To Do** and **Completed** columns.
- Log daily activity progress and view a trend chart.
- Dashboard summary: total tasks, completed tasks, completion rate, average progress.
- Reminder integrations (optional) for Email, Telegram, and WhatsApp.
- Pre-seeded tasks: green tea, yoga, gym, 10k steps, bike wash, finish one book.

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Open http://localhost:5000

## Reminder setup (optional)
Set any of these environment variables before running:

### Email
- `SMTP_HOST`
- `SMTP_PORT` (default: 587)
- `SMTP_USER`
- `SMTP_PASS`
- `REMINDER_EMAIL`

### Telegram
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

### WhatsApp (CallMeBot)
- `WHATSAPP_PHONE`
- `WHATSAPP_API_KEY`

The app also schedules daily reminders at 08:00 server time using APScheduler.
