import subprocess
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

MONTH_NAMES = {
    "01": "January",
    "02": "February",
    "03": "March",
    "04": "April",
    "05": "May",
    "06": "June",
    "07": "July",
    "08": "August",
    "09": "September",
    "10": "October",
    "11": "November",
    "12": "December",
}


def get_current_version(repo_path: str = ".") -> str:
    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        capture_output=True,
        text=True,
        cwd=repo_path,
    )
    return result.stdout.strip() or "dev"


def get_commits(max_count: int = 100, repo_path: str = ".") -> list[dict]:
    sep = "\x1f"
    rec_sep = "\x1e"
    fmt = f"--format={sep.join(['%H', '%h', '%s', '%b', '%an', '%ai'])}{rec_sep}"

    result = subprocess.run(
        ["git", "log", fmt, f"--max-count={max_count}"],
        capture_output=True,
        text=True,
        cwd=repo_path,
    )

    commits = []
    for entry in result.stdout.split(rec_sep):
        entry = entry.strip()
        if not entry:
            continue
        parts = (entry + sep * 6).split(sep)
        full_hash = parts[0].strip()
        short_hash = parts[1].strip()
        subject = parts[2].strip()
        body = parts[3].strip()
        author = parts[4].strip()
        date_str = parts[5].strip()

        if not full_hash:
            continue

        stat_result = subprocess.run(
            ["git", "show", "--stat", "--format=", full_hash],
            capture_output=True,
            text=True,
            cwd=repo_path,
        )

        stat_lines = [l for l in stat_result.stdout.splitlines() if "|" in l]
        summary = (
            stat_result.stdout.splitlines()[-1].strip()
            if stat_result.stdout.strip()
            else ""
        )
        tag_result = subprocess.run(
            ["git", "tag", "--points-at", full_hash],
            capture_output=True,
            text=True,
            cwd=repo_path,
        )
        tag = tag_result.stdout.strip()

        commits.append(
            {
                "full_hash": full_hash,
                "short_hash": short_hash,
                "subject": subject or "(no message)",
                "body": body,
                "author": author,
                "date": date_str[:10],  # "2025-03-15"
                "month_key": date_str[:7],  # "2025-03"
                "day": date_str[8:10],  # "15"
                "stat_lines": stat_lines,
                "summary": summary,
                "tag": tag,
            }
        )

    return commits


def group_by_month(commits: list[dict]) -> list[tuple[str, list[dict]]]:
    groups: dict[str, list[dict]] = {}
    for c in commits:
        groups.setdefault(c["month_key"], []).append(c)
    return list(groups.items())  # preserves insertion (newest-first) order


def fmt_month_label(key: str) -> str:
    year, month = key.split("-")
    return f"{MONTH_NAMES.get(month, month)} {year}"


def render_stat(stat_lines: list[str], summary: str) -> str:
    if not summary:
        return ""
    files_html = "\n".join(f"<li>{line}</li>" for line in stat_lines)
    return f"""
        <details>
          <summary class="cl-stat">{summary}</summary>
          <ul class="cl-files">{files_html}</ul>
        </details>"""


# <span class="cl-author">{c["author"]}</span>
def render_commit(c: dict, is_last: bool) -> str:
    body_html = f'<p class="cl-body">{c["body"]}</p>' if c["body"] else ""
    stat_html = render_stat(c["stat_lines"], c["summary"])
    bottom_line = "" if is_last else '<div class="cl-line"></div>'
    tag_html = f'<span class="cl-tag">{c["tag"]}</span>' if c["tag"] else ""

    return f"""
      <div class="cl-item">
        <div class="cl-spine">
          <div class="cl-dot"></div>
          {bottom_line}
        </div>
        <div class="cl-card">
          <div class="cl-card-head">
            <span class="cl-hash">{c["short_hash"]}</span>
            <span class="cl-day">{c["date"]}</span>
            {tag_html}
          </div>
          <p class="cl-subject">{c["subject"]}</p>
          {body_html}
          {stat_html}
        </div>
      </div>"""


def render_page(commits: list[dict]) -> str:
    groups = group_by_month(commits)

    groups_html = ""
    for month_key, month_commits in groups:
        items_html = ""
        for i, c in enumerate(month_commits):
            is_last_in_group = i == len(month_commits) - 1
            items_html += render_commit(c, is_last=is_last_in_group)

        groups_html += f"""
      <div class="cl-group">
        <div class="cl-month-label">{fmt_month_label(month_key)}</div>
        <div class="cl-items">{items_html}</div>
      </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Changelog</title>
  <style>
    :root {{
      --bg:        #fdf6e3;
      --surface:   #ffffff;
      --border:    #e8e0cc;
      --muted:     #93a1a1;
      --text:      #586e75;
      --heading:   #073642;
      --accent:    #1D9E75;
      --accent-lt: #e1f5ee;
      --hash-bg:   #eee8d5;
      --hash-fg:   #cb4b16;
      --mono:      "SFMono-Regular", "Consolas", "Liberation Mono", monospace;
    }}

    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg:       #1c1c1c;
        --surface:  #262626;
        --border:   #383838;
        --muted:    #6b7280;
        --text:     #d1d5db;
        --heading:  #f3f4f6;
        --accent:   #34d399;
        --accent-lt:#064e3b;
        --hash-bg:  #2e2e2e;
        --hash-fg:  #fb923c;
      }}
    }}

    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
      font-size: 15px;
      line-height: 1.6;
      padding: 3rem 1rem 6rem;
    }}

    .page {{
      max-width: 740px;
      margin: 0 auto;
    }}

    /* ── Page header ── */
    .page-header {{
      margin-bottom: 3rem;
    }}
    .page-header h1 {{
      font-size: 1.75rem;
      font-weight: 600;
      color: var(--heading);
      margin-bottom: 0.25rem;
    }}
    .page-header p {{
      font-size: 0.875rem;
      color: var(--muted);
    }}

    /* ── Month group ── */
    .cl-group {{
      margin-bottom: 2.5rem;
    }}
    .cl-month-label {{
      font-size: 0.7rem;
      font-weight: 600;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 0.75rem;
      padding-left: 26px;
    }}

    /* ── Timeline item ── */
    .cl-item {{
      display: flex;
      gap: 0;
    }}

    /* spine: dot + vertical line */
    .cl-spine {{
      display: flex;
      flex-direction: column;
      align-items: center;
      width: 26px;
      flex-shrink: 0;
      padding-top: 15px;      /* aligns dot with card title row */
    }}
    .cl-dot {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: var(--surface);
      border: 2px solid var(--accent);
      flex-shrink: 0;
      position: relative;
      z-index: 1;
    }}
    .cl-line {{
      width: 2px;
      background: var(--border);
      flex: 1;
      min-height: 12px;
      margin-top: 2px;
    }}

    /* card */
    .cl-card {{
      flex: 1;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 11px 14px;
      margin: 6px 0 10px 0;
      transition: border-color 0.15s;
    }}
    .cl-card:hover {{
      border-color: var(--accent);
    }}

    .cl-card-head {{
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 5px;
    }}
    .cl-hash {{
      font-family: var(--mono);
      font-size: 0.7rem;
      background: var(--hash-bg);
      color: var(--hash-fg);
      padding: 2px 6px;
      border-radius: 4px;
    }}
    .cl-day {{
      font-size: 0.78rem;
      color: var(--muted);
    }}
    .cl-author {{
      font-size: 0.78rem;
      color: var(--muted);
      margin-left: auto;
    }}

    .cl-subject {{
      font-size: 0.9rem;
      font-weight: 600;
      color: var(--heading);
      margin-bottom: 4px;
    }}
    .cl-body {{
      font-size: 0.83rem;
      color: var(--muted);
      white-space: pre-wrap;
      margin-bottom: 6px;
    }}

    /* stat / files */
    details {{ margin-top: 6px; }}
    summary.cl-stat {{
      cursor: pointer;
      font-size: 0.78rem;
      color: var(--accent);
      list-style: none;
      display: inline;
      user-select: none;
    }}
    summary.cl-stat:hover {{ text-decoration: underline; }}
    .cl-files {{
      margin-top: 6px;
      padding-left: 0;
      list-style: none;
    }}
    .cl-files li {{
      font-family: var(--mono);
      font-size: 0.72rem;
      color: var(--muted);
      padding: 3px 0;
      border-bottom: 1px solid var(--border);
      white-space: pre;
      overflow-x: auto;
    }}
    .cl-files li:last-child {{ border-bottom: none; }}
    .cl-back {{
    display: inline-block;
    font-size: 0.82rem;
    color: var(--accent);
    text-decoration: none;
    margin-bottom: 0.75rem;
    }}
    .cl-back:hover {{text-decoration: underline; }} 
    .cl-tag {{
        font-size: 0.7rem;
        font-weight: 600;
        background: #e1f5ee;
        color: #0f6e56;
        padding: 2px 7px;
        border-radius: 20px;
        border: 1px solid #5DCAA5;
        }}
  </style>
</head>
<body>
  <div class="page">
    <a href="/" class="cl-back">← Back to Recipe-App</a>   <!-- 加这行 -->
    <h1>Changelog</h1>
    <p>Showing {len(commits)} most recent commits &mdash; auto-generated from git history</p>

    {groups_html}
  </div>
</body>
</html>"""


@router.get("/changelog", response_class=HTMLResponse)
async def changelog(n: int = 100):
    """
    Render a timeline-style changelog page from git history.

    Query params:
      n  — max number of commits to show (default 100)
    """
    commits = get_commits(max_count=n)
    return render_page(commits)


@router.get("/api/version")
async def version():
    return {"version": get_current_version()}
