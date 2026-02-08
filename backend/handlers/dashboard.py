from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape
import json
from typing import Any
from zoneinfo import ZoneInfo

from services.supabase_service import SupabaseService


def normalize_phone_number(value: str) -> str:
    if not value:
        return ""
    trimmed = value.strip()
    if trimmed.startswith("whatsapp:"):
        trimmed = trimmed.replace("whatsapp:", "", 1)
    cleaned = "".join(ch for ch in trimmed if ch.isdigit() or ch == "+")
    return cleaned


def build_day_sections(
    supabase: SupabaseService,
    user: dict,
    days: int = 7,
) -> list[dict[str, Any]]:
    tz_name = user.get("timezone") or "UTC"
    tz = _safe_timezone(tz_name)
    today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    sections: list[dict[str, Any]] = []
    for index in range(days):
        day_start = today - timedelta(days=index)
        day_end = day_start + timedelta(days=1)
        start_iso = day_start.astimezone(timezone.utc).isoformat()
        end_iso = day_end.astimezone(timezone.utc).isoformat()
        label = day_start.strftime("%A, %b %d")
        sections.append(
            {
                "index": index + 1,
                "label": label,
                "date": day_start.strftime("%Y-%m-%d"),
                "is_today": index == 0,
                "pomodoro": _fetch_pomodoro(supabase, user["id"], start_iso, end_iso, tz),
                "tasks": _fetch_tasks(supabase, user["id"], start_iso, end_iso, tz),
                "calories": _fetch_calories(supabase, user["id"], start_iso, end_iso, tz),
            }
        )
    return sections


def render_login(error: str | None = None) -> str:
    error_html = ""
    if error:
        error_html = f"<div class='alert'>{escape(error)}</div>"
    body = f"""
    <main class="card shell">
      <div class="brand">
        <span class="dot"></span>
        <span>Tomatose!</span>
      </div>
      <h1>Your WhatsApp Productivity Dashboard</h1>
      <p class="muted">Enter your name and phone number to open your daily dashboard.</p>
      {error_html}
      <form class="form" action="/dashboard/view" method="get">
        <label>
          <span>Name</span>
          <input name="name" placeholder="Tushar" autocomplete="name" />
        </label>
        <label>
          <span>Phone number</span>
          <input name="phone" placeholder="+1 555 123 4567" autocomplete="tel" required />
        </label>
        <input type="hidden" name="tz" id="tz" />
        <button type="submit">Open dashboard</button>
      </form>
      <p class="hint">Tip: Use the same phone number you chat with on WhatsApp.</p>
    </main>
    """
    return _base_html("Tomatose! | Dashboard Login", body, include_tz_script=True)


def render_dashboard(user: dict, sections: list[dict[str, Any]]) -> str:
    name = escape(user.get("name") or "there")
    tz = _safe_timezone(user.get("timezone") or "UTC")
    tz_name = escape(tz.key)
    now_local = datetime.now(tz)
    today_label = now_local.strftime("%A, %b %d")
    current_tz = user.get("timezone") or "UTC"
    header = f"""
    <header class="hero">
      <div>
        <div class="brand">
          <span class="dot"></span>
          <span>Tomatose!</span>
        </div>
        <h1>Welcome back, {name}.</h1>
        <p class="muted">Timezone: {tz_name} · Day-wise view of focus, tasks, and calories.</p>
      </div>
      <div class="hero-card">
        <div class="stat">
          <span>Today</span>
          <strong>{today_label}</strong>
        </div>
        <div class="stat">
          <span>Last updated</span>
          <strong>{now_local.strftime("%I:%M %p").lstrip("0")}</strong>
        </div>
      </div>
    </header>
    """
    tz_sync = f"""
    <script>
      (function () {{
        try {{
          var localTz = Intl.DateTimeFormat().resolvedOptions().timeZone;
          var currentTz = {json.dumps(current_tz)};
          var params = new URLSearchParams(window.location.search);
          if (!params.has("tz") && localTz && localTz !== currentTz) {{
            params.set("tz", localTz);
            window.location.replace(window.location.pathname + "?" + params.toString());
          }}
        }} catch (e) {{}}
      }})();
    </script>
    """
    day_blocks = "\n".join([_render_day(section) for section in sections])
    body = f"""
    <main class="shell">
      {header}
      {day_blocks}
    </main>
    {tz_sync}
    """
    return _base_html("Tomatose! | Dashboard", body)


def _render_day(section: dict[str, Any]) -> str:
    label = escape(section["label"])
    date = escape(section["date"])
    today_tag = "<span class='pill'>Today</span>" if section.get("is_today") else ""
    pomodoro_html = _render_pomodoro(section["pomodoro"])
    tasks_html = _render_tasks(section["tasks"])
    calories_html = _render_calories(section["calories"])
    return f"""
    <section class="day">
      <div class="day-header">
        <h2>{label}</h2>
        <span>{date} {today_tag}</span>
      </div>
      <div class="grid">
        <article class="tile">{pomodoro_html}</article>
        <article class="tile">{tasks_html}</article>
        <article class="tile">{calories_html}</article>
      </div>
    </section>
    """


def _render_pomodoro(data: dict[str, Any]) -> str:
    total = data["total_minutes"]
    count = data["count"]
    items = data["items"]
    list_html = "<p class='muted'>No focus sessions logged.</p>"
    if items:
        rows = "".join(
            [
                f"<li><strong>{escape(item['time'])}</strong> · {escape(item['label'])} "
                f"<span class='pill'>{item['minutes']}m</span></li>"
                for item in items
            ]
        )
        list_html = f"<ul class='list'>{rows}</ul>"
    return f"""
    <div class="tile-head">
      <h3>Pomodoro</h3>
      <span class="pill">{total}m · {count} sessions</span>
    </div>
    {list_html}
    """


def _render_tasks(data: dict[str, Any]) -> str:
    created = data["created"]
    completed = data["completed"]
    created_html = "<p class='muted'>No new tasks.</p>"
    if created:
        rows = "".join(
            [
                f"<li>{escape(task['title'])} "
                f"<span class='pill {('done' if task['completed'] else 'pending')}'>"
                f"{'done' if task['completed'] else 'open'}</span></li>"
                for task in created
            ]
        )
        created_html = f"<ul class='list'>{rows}</ul>"
    completed_html = "<p class='muted'>No tasks completed.</p>"
    if completed:
        rows = "".join(
            [
                f"<li>{escape(task['title'])} <span class='pill done'>{escape(task['time'])}</span></li>"
                for task in completed
            ]
        )
        completed_html = f"<ul class='list'>{rows}</ul>"
    return f"""
    <div class="tile-head">
      <h3>Tasks</h3>
      <span class="pill">{len(created)} created · {len(completed)} completed</span>
    </div>
    <div class="stack">
      <div>
        <p class="label">Created</p>
        {created_html}
      </div>
      <div>
        <p class="label">Completed</p>
        {completed_html}
      </div>
    </div>
    """


def _render_calories(data: dict[str, Any]) -> str:
    total = data["total_calories"]
    protein = data["protein"]
    carbs = data["carbs"]
    fat = data["fat"]
    meals = data["meals"]
    meals_html = "<p class='muted'>No meals logged.</p>"
    if meals:
        rows = "".join(
            [
                f"<li>{escape(meal['desc'])} "
                f"<span class='pill'>{meal['calories']} cal</span></li>"
                for meal in meals
            ]
        )
        meals_html = f"<ul class='list'>{rows}</ul>"
    return f"""
    <div class="tile-head">
      <h3>Calories</h3>
      <span class="pill">{total} cal</span>
    </div>
    <p class="muted">Macros: {protein}g protein · {carbs}g carbs · {fat}g fat</p>
    {meals_html}
    """


def _fetch_pomodoro(
    supabase: SupabaseService,
    user_id: str,
    start_iso: str,
    end_iso: str,
    tz: ZoneInfo,
) -> dict[str, Any]:
    sessions = supabase._execute(
        supabase.client.table("pomodoro_sessions")
        .select("*")
        .eq("user_id", user_id)
        .eq("session_type", "work")
        .gte("start_time", start_iso)
        .lte("start_time", end_iso)
        .order("start_time", desc=False)
    )
    total_minutes = 0
    items: list[dict[str, Any]] = []
    for session in sessions:
        start = _parse_iso(session["start_time"]).astimezone(tz)
        end_time = session.get("end_time")
        minutes = session.get("planned_duration_minutes") or 0
        if end_time:
            end = _parse_iso(end_time).astimezone(tz)
            minutes = int((end - start).total_seconds() / 60)
        total_minutes += max(minutes, 0)
        label = session.get("what_did_you_do") or "Focus session"
        items.append(
            {
                "time": start.strftime("%I:%M %p").lstrip("0"),
                "label": label,
                "minutes": max(minutes, 0),
            }
        )
    return {"total_minutes": total_minutes, "count": len(sessions), "items": items}


def _fetch_tasks(
    supabase: SupabaseService,
    user_id: str,
    start_iso: str,
    end_iso: str,
    tz: ZoneInfo,
) -> dict[str, Any]:
    created = supabase._execute(
        supabase.client.table("tasks")
        .select("*")
        .eq("user_id", user_id)
        .gte("created_at", start_iso)
        .lte("created_at", end_iso)
        .order("created_at", desc=False)
    )
    completed = supabase._execute(
        supabase.client.table("tasks")
        .select("*")
        .eq("user_id", user_id)
        .eq("completed", True)
        .gte("completed_at", start_iso)
        .lte("completed_at", end_iso)
        .order("completed_at", desc=False)
    )
    created_items = [
        {"title": task.get("title") or "Untitled", "completed": bool(task.get("completed"))}
        for task in created
    ]
    completed_items = []
    for task in completed:
        completed_at = task.get("completed_at")
        time_label = ""
        if completed_at:
            time_label = _parse_iso(completed_at).astimezone(tz).strftime("%I:%M %p").lstrip("0")
        completed_items.append({"title": task.get("title") or "Untitled", "time": time_label})
    return {"created": created_items, "completed": completed_items}


def _fetch_calories(
    supabase: SupabaseService,
    user_id: str,
    start_iso: str,
    end_iso: str,
    tz: ZoneInfo,
) -> dict[str, Any]:
    logs = supabase._execute(
        supabase.client.table("calorie_logs")
        .select("*")
        .eq("user_id", user_id)
        .gte("logged_at", start_iso)
        .lte("logged_at", end_iso)
        .order("logged_at", desc=False)
    )
    total_calories = 0
    total_protein = 0.0
    total_carbs = 0.0
    total_fat = 0.0
    meals = []
    for log in logs:
        calories = int(log.get("calories") or 0)
        total_calories += calories
        total_protein += float(log.get("protein_g") or 0)
        total_carbs += float(log.get("carbs_g") or 0)
        total_fat += float(log.get("fat_g") or 0)
        desc = log.get("meal_description") or "Meal"
        meals.append({"desc": desc, "calories": calories})
    return {
        "total_calories": total_calories,
        "protein": int(total_protein),
        "carbs": int(total_carbs),
        "fat": int(total_fat),
        "meals": meals,
    }


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _safe_timezone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("UTC")


def _base_html(title: str, body: str, include_tz_script: bool = False) -> str:
    tz_script = ""
    if include_tz_script:
        tz_script = """
        <script>
          (function () {
            try {
              var tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
              var input = document.getElementById("tz");
              if (input && tz) {
                input.value = tz;
              }
            } catch (e) {}
          })();
        </script>
        """
    return f"""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>{escape(title)}</title>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
        <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=IBM+Plex+Sans:wght@400;600&display=swap" rel="stylesheet" />
        <style>
          :root {{
            --ink: #1b1b1b;
            --muted: #6c6c6c;
            --bg: #f7f4ef;
            --card: #ffffff;
            --accent: #0f766e;
            --accent-soft: #ccfbf1;
            --shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
          }}
          * {{
            box-sizing: border-box;
          }}
          body {{
            margin: 0;
            font-family: "IBM Plex Sans", sans-serif;
            color: var(--ink);
            background: radial-gradient(circle at top left, #fff3dc, transparent 45%),
                        radial-gradient(circle at bottom right, #e0f2fe, transparent 55%),
                        var(--bg);
          }}
          h1, h2, h3 {{
            font-family: "Space Grotesk", sans-serif;
            margin: 0 0 8px;
          }}
          h1 {{
            font-size: clamp(28px, 3vw, 38px);
          }}
          h2 {{
            font-size: 22px;
          }}
          h3 {{
            font-size: 18px;
          }}
          p {{
            margin: 0 0 12px;
          }}
          .shell {{
            max-width: 1100px;
            margin: 0 auto;
            padding: 32px 20px 64px;
          }}
          .card {{
            background: var(--card);
            border-radius: 20px;
            padding: 32px;
            box-shadow: var(--shadow);
          }}
          .hero {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 24px;
            margin-bottom: 24px;
          }}
          .hero-card {{
            display: grid;
            gap: 12px;
            background: var(--card);
            border-radius: 18px;
            padding: 16px 20px;
            box-shadow: var(--shadow);
            min-width: 200px;
          }}
          .stat span {{
            display: block;
            color: var(--muted);
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
          }}
          .stat strong {{
            font-size: 18px;
          }}
          .brand {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 12px;
            color: var(--muted);
          }}
          .dot {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: var(--accent);
          }}
          .day {{
            margin-top: 24px;
          }}
          .day-header {{
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            margin-bottom: 12px;
          }}
          .day-header span {{
            color: var(--muted);
          }}
          .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 16px;
          }}
          .tile {{
            background: var(--card);
            border-radius: 18px;
            padding: 16px;
            box-shadow: var(--shadow);
          }}
          .tile-head {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 12px;
          }}
          .pill {{
            background: var(--accent-soft);
            color: var(--accent);
            padding: 4px 10px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 600;
            white-space: nowrap;
          }}
          .pill.done {{
            background: #dcfce7;
            color: #166534;
          }}
          .pill.pending {{
            background: #fef3c7;
            color: #92400e;
          }}
          .list {{
            list-style: none;
            padding: 0;
            margin: 0;
            display: grid;
            gap: 8px;
          }}
          .list li {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            font-size: 14px;
          }}
          .muted {{
            color: var(--muted);
          }}
          .stack {{
            display: grid;
            gap: 12px;
          }}
          .label {{
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--muted);
          }}
          .form {{
            display: grid;
            gap: 16px;
            margin-top: 16px;
          }}
          label {{
            display: grid;
            gap: 6px;
            font-size: 14px;
          }}
          input {{
            border: 1px solid #e5e5e5;
            border-radius: 12px;
            padding: 12px 14px;
            font-size: 16px;
            font-family: "IBM Plex Sans", sans-serif;
          }}
          button {{
            border: none;
            border-radius: 12px;
            background: var(--accent);
            color: #fff;
            padding: 12px 16px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
          }}
          .alert {{
            background: #fee2e2;
            color: #991b1b;
            padding: 10px 12px;
            border-radius: 12px;
            margin-top: 12px;
            font-size: 14px;
          }}
          .hint {{
            margin-top: 12px;
            color: var(--muted);
            font-size: 13px;
          }}
          @media (max-width: 800px) {{
            .hero {{
              flex-direction: column;
              align-items: flex-start;
            }}
            .hero-card {{
              width: 100%;
              grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            }}
          }}
        </style>
      </head>
      <body>
        {body}
        {tz_script}
      </body>
    </html>
    """
