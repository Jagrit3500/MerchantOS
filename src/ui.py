"""MerchantOS shared navigation, typography, activity, and UI primitives."""
from __future__ import annotations

import html
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

import streamlit as st

from src import config
from src.activity_history import (
    clear_activity_history,
    delete_activity,
    read_activity_counts,
    read_activity_history,
)
from src.auth import get_session_user


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def app_urls() -> dict[str, str]:
    return config.app_urls()


def icon(name: str) -> str:
    paths = {
        "home": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
        "agent1": '<path d="M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6Z"/><path d="m8 12 3 3 5-6"/>',
        "agent2": '<path d="M4 3h16v18l-4-2-4 2-4-2-4 2Z"/><path d="M8 7h8M8 11h8M8 15h4"/>',
        "agent3": '<path d="M6 3h9l4 4v14H6Z"/><path d="M14 3v5h5M9 12h7M9 16h5"/>',
        "logout": '<path d="M10 5H5v14h5M14 8l4 4-4 4M18 12H9"/>',
        "arrow": '<path d="M4 12h15m-6-6 6 6-6 6"/>',
    }
    path = paths.get(name, paths["arrow"])
    return (
        '<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{path}</svg>'
    )


def inject_theme() -> None:
    css = Path(__file__).with_name("styles.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def require_auth(active: str) -> dict:
    """Stop the page at a shared sign-in gate unless a valid session exists."""
    if not config.AUTH_ENABLED:
        user = {"id": 0, "email": "", "display_name": "Local user"}
        st.session_state.merchantos_user = user
        return user
    token = st.context.cookies.get(config.AUTH_COOKIE_NAME)
    user = get_session_user(token)
    if user:
        st.session_state.merchantos_user = user
        return user
    st.session_state.pop("merchantos_user", None)
    params = urlencode({"auth": "signin", "next": app_urls()[active]})
    sign_in_url = f'{app_urls()["landing"]}/?{params}'
    st.markdown(
        '<main class="auth-gate">'
        '<div class="auth-gate-mark"><i></i></div>'
        '<div class="eyebrow">SECURE MERCHANT WORKSPACE</div>'
        '<h1>Sign in to continue.</h1>'
        '<p>Your reconciliation data, case details, and generated documents stay behind your MerchantOS session.</p>'
        f'<a class="same-tab-link auth-gate-action" href="{esc(sign_in_url)}" target="_self">Sign in or create account →</a>'
        '<small>Session access is shared securely across the MerchantOS workspace.</small>'
        '</main>',
        unsafe_allow_html=True,
    )
    st.stop()


def nav(active: str) -> None:
    """Render the compact workspace rail shared by every MerchantOS page."""
    items = [
        ("home", "Overview"),
        ("agent1", "KYC & fund holds"),
        ("agent2", "Reconciliation"),
        ("agent3", "Escalation"),
    ]
    urls = app_urls()
    user = st.session_state.get("merchantos_user", {})
    display_name = user.get("display_name") or config.WORKSPACE_NAME
    email = user.get("email") or f"{config.REGION} · {config.CURRENCY}"
    initial = display_name[:1].upper() if display_name else "M"
    links = "".join(
        f'<a href="{esc(urls[key])}" target="_self" title="{esc(label)}" '
        f'class="rail-link {"active" if key == active else ""}" '
        f'{"aria-current=page" if key == active else ""}>{icon(key)}<span>{esc(label)}</span></a>'
        for key, label in items
    )
    st.markdown(
        '<aside class="merchantos-navigation" aria-label="MerchantOS navigation">'
        f'<a class="brand" href="{esc(urls["landing"])}" target="_self" aria-label="MerchantOS landing page">'
        '<span class="brand-mark"><i></i></span><span class="brand-word">merchant<b>os</b></span></a>'
        '<div class="rail-label">Workspace</div>'
        f'<nav class="rail-nav" aria-label="Main navigation">{links}</nav>'
        '<div class="rail-spacer"></div>'
        f'<div class="workspace"><span class="workspace-avatar">{esc(initial)}</span><div><strong>{esc(display_name)}</strong>'
        f'<small>{esc(email)}</small></div></div>'
        f'<a class="rail-logout" href="{esc(urls["landing"])}/?logout=1" target="_self" title="Sign out">'
        f'{icon("logout")}<span>Sign out</span></a></aside>',
        unsafe_allow_html=True,
    )


def hero(eyebrow: str, title: str, description: str) -> None:
    st.markdown(
        f'<header class="page-heading"><div class="eyebrow">{esc(eyebrow)}</div>'
        f'<h1>{esc(title)}</h1><p>{esc(description)}</p></header>',
        unsafe_allow_html=True,
    )


def section_title(title: str, description: str = "") -> None:
    st.markdown(
        f'<div class="section-heading"><h2>{esc(title)}</h2><span>{esc(description)}</span></div>',
        unsafe_allow_html=True,
    )


def metric(label: str, value: str, subtitle: str = "") -> None:
    st.markdown(
        f'<div class="metric"><div>{esc(label)}</div><strong>{esc(value)}</strong><small>{esc(subtitle)}</small></div>',
        unsafe_allow_html=True,
    )


def activity_history(section: str) -> None:
    """Render deletable, workspace-specific history for the signed-in user."""
    user_id = st.session_state.get("merchantos_user", {}).get("id", "local")
    entries = read_activity_history(user_id, section=section)
    section_names = {
        "agent1": "KYC & holds",
        "agent2": "Reconciliation",
        "agent3": "Escalation",
    }
    entry_count = len(entries)
    confirmation_key = f"show_clear_history_confirmation_{section}"
    with st.container(key=f"activity_history_toolbar_{section}"):
        heading, action = st.columns([4, 1], gap="large", vertical_alignment="bottom")
        with heading:
            st.markdown(
                '<header class="activity-history-header">'
                '<div class="activity-history-title"><h2>Activity history</h2></div></header>',
                unsafe_allow_html=True,
            )
        with action:
            if entries and st.button("Clear history", key=f"clear_history_{section}", width="stretch"):
                st.session_state[confirmation_key] = True

    st.markdown(
        f'<div class="activity-history-summary">{entry_count} recent saved action'
        f'{"s" if entry_count != 1 else ""}<span></span>{esc(section_names.get(section, "Workspace"))}</div>',
        unsafe_allow_html=True,
    )

    if not entries:
        st.info("Completed work in this workspace will appear here.")
        return

    if st.session_state.get(confirmation_key):
        with st.container(border=True, key=f"clear_history_confirmation_{section}"):
            st.warning("Delete every saved item in this workspace? This cannot be undone.")
            cancel, confirm = st.columns(2)
            if cancel.button("Cancel", key=f"cancel_clear_history_{section}", width="stretch"):
                st.session_state[confirmation_key] = False
                st.rerun()
            if confirm.button("Delete all", key=f"confirm_clear_history_{section}", type="primary", width="stretch"):
                deleted = clear_activity_history(user_id, section)
                st.session_state[confirmation_key] = False
                st.toast(f"Deleted {deleted} history item{'s' if deleted != 1 else ''}.")
                st.rerun()

    urls = app_urls()
    for entry in entries:
        try:
            created = datetime.fromisoformat(entry["created_at"]).astimezone().strftime("%d %b %Y · %H:%M")
        except (KeyError, TypeError, ValueError):
            created = "Saved activity"
        with st.container(border=True, key=f'activity_entry_{entry["id"]}'):
            content, remove = st.columns([6, 1], vertical_alignment="center")
            with content:
                workspace_url = urls[entry["section"]]
                if entry["section"] == "agent1" and entry.get("metadata", {}).get("answers"):
                    workspace_url = f'{workspace_url}?{urlencode({"activity": entry["id"]})}'
                st.markdown(
                    f'<a class="activity-card-link" href="{esc(workspace_url)}" target="_self">'
                    f'<span class="activity-mark">{esc(section_names.get(entry["section"], "M")[:1])}</span>'
                    '<span class="activity-copy">'
                    f'<span class="activity-meta"><b>{esc(section_names.get(entry["section"], entry["section"]))}</b>'
                    f'<time>{esc(created)}</time></span>'
                    f'<strong>{esc(entry["title"])}</strong>'
                    f'<small>{esc(entry.get("detail", ""))}</small>'
                    '<em>Open workspace →</em></span></a>',
                    unsafe_allow_html=True,
                )
            with remove:
                if st.button(
                    "Delete",
                    key=f'delete_activity_{entry["id"]}',
                    width="stretch",
                    help="Permanently remove this history item",
                ):
                    delete_activity(user_id, entry["id"])
                    st.toast("History item deleted.")
                    st.rerun()


def activity_heatmap() -> None:
    """Render an aggregate contribution view without exposing detailed history."""
    user_id = st.session_state.get("merchantos_user", {}).get("id", "local")
    counts = read_activity_counts(user_id, config.ACTIVITY_HEATMAP_DAYS)
    section_names = {"agent1": "KYC", "agent2": "Reconciliation", "agent3": "Escalation"}
    daily: dict[date, int] = {}
    by_section = {key: 0 for key in section_names}
    for row in counts:
        try:
            activity_date = date.fromisoformat(row["activity_date"])
        except (KeyError, TypeError, ValueError):
            continue
        count = int(row.get("activity_count") or 0)
        daily[activity_date] = daily.get(activity_date, 0) + count
        if row.get("section") in by_section:
            by_section[row["section"]] += count

    today = datetime.now().astimezone().date()
    first_day = today - timedelta(days=config.ACTIVITY_HEATMAP_DAYS - 1)
    grid_start = first_day - timedelta(days=(first_day.weekday() + 1) % 7)
    grid_end = today + timedelta(days=6 - ((today.weekday() + 1) % 7))
    week_count = ((grid_end - grid_start).days // 7) + 1
    total = sum(daily.values())
    active_days = sum(1 for count in daily.values() if count)
    streak = 0
    cursor = today
    while daily.get(cursor, 0):
        streak += 1
        cursor -= timedelta(days=1)
    most_active_key = max(by_section, key=by_section.get) if total else None
    most_active = section_names.get(most_active_key, "No activity yet")

    section_title("Recovery activity", f"Your last {config.ACTIVITY_HEATMAP_DAYS} days across MerchantOS")
    statistic_columns = st.columns(4)
    statistics = [
        ("Completed actions", str(total), "Across all recovery workflows"),
        ("Active days", str(active_days), "Days with saved activity"),
        ("Current streak", f"{streak} day{'s' if streak != 1 else ''}", "Consecutive active days"),
        (
            "Most active",
            most_active,
            f"{by_section.get(most_active_key, 0)} saved actions" if most_active_key else "Start a workflow",
        ),
    ]
    for column, values in zip(statistic_columns, statistics):
        with column:
            metric(*values)

    levels = config.ACTIVITY_HEATMAP_LEVELS
    cells = []
    month_positions: list[tuple[int, str]] = []
    previous_month = None
    for week in range(week_count):
        week_start = grid_start + timedelta(days=week * 7)
        label_day = week_start + timedelta(days=3)
        if label_day.month != previous_month:
            month_positions.append((week + 1, label_day.strftime("%b")))
            previous_month = label_day.month
        for day_offset in range(7):
            current = week_start + timedelta(days=day_offset)
            count = daily.get(current, 0) if first_day <= current <= today else 0
            level = 0 if count == 0 else 1 + sum(count > threshold for threshold in levels)
            outside = " outside" if current < first_day or current > today else ""
            label = f'{current.strftime("%d %b %Y")} · {count} saved action{"s" if count != 1 else ""}'
            cells.append(
                f'<span class="heat-cell level-{level}{outside}" title="{esc(label)}" aria-label="{esc(label)}"></span>'
            )

    months = "".join(
        f'<span style="grid-column:{position}">{esc(label)}</span>' for position, label in month_positions
    )
    breakdown = "".join(
        f'<span><i class="workflow-dot {key}"></i>{esc(label)} <b>{by_section[key]}</b></span>'
        for key, label in section_names.items()
    )
    heatmap_html = (
        '<div class="heatmap-card"><div class="heatmap-scroll"><div class="heatmap-layout">'
        f'<div class="heatmap-months" style="grid-template-columns:repeat({week_count}, 11px)">{months}</div>'
        '<div class="heatmap-days"><span></span><span>Mon</span><span></span><span>Wed</span><span></span><span>Fri</span><span></span></div>'
        f'<div class="heatmap-grid" style="grid-template-columns:repeat({week_count}, 11px)">{"".join(cells)}</div>'
        '</div></div><div class="heatmap-footer">'
        f'<div class="workflow-breakdown">{breakdown}</div>'
        '<div class="heatmap-legend"><span>Less</span><i class="level-0"></i><i class="level-1"></i>'
        '<i class="level-2"></i><i class="level-3"></i><i class="level-4"></i><span>More</span></div>'
        '</div></div>'
    )
    st.markdown(heatmap_html, unsafe_allow_html=True)
    st.caption("Detailed records stay inside their respective KYC, reconciliation, and escalation workspaces.")


def same_tab_link(label: str, url: str) -> None:
    """Render an application action that replaces the current browser tab."""
    st.markdown(
        f'<a class="same-tab-link" href="{esc(url)}" target="_self">{esc(label)}</a>',
        unsafe_allow_html=True,
    )


def badge(text: str, tone: str = "info") -> str:
    return f'<span class="badge {esc(tone)}"><i></i>{esc(text)}</span>'


@contextmanager
def panel(title: str = "", subtitle: str = "", key: str | None = None):
    with st.container(border=True, key=key):
        if title:
            st.markdown(
                f'<div class="panel-heading"><h3>{esc(title)}</h3><p>{esc(subtitle)}</p></div>',
                unsafe_allow_html=True,
            )
        yield


def steps(labels: list[str], current: int) -> None:
    rows = "".join(
        f'<div class="journey-step {"complete" if i < current else "current" if i == current else ""}">'
        f'<span>{"✓" if i < current else str(i + 1).zfill(2)}</span><div>{esc(label)}'
        f'<small>{"Complete" if i < current else "In progress" if i == current else "Up next"}</small></div></div>'
        for i, label in enumerate(labels)
    )
    st.markdown(f'<div class="journey">{rows}</div>', unsafe_allow_html=True)


def note(title: str, body: str) -> None:
    st.markdown(
        f'<aside class="context-note"><span class="note-star">✳</span><h3>{esc(title)}</h3><p>{esc(body)}</p></aside>',
        unsafe_allow_html=True,
    )


def footer(*args, **kwargs) -> None:
    st.markdown(
        '<div class="page-footer"><span>merchantos <span class="footer-dot">/</span> Recovery operations workspace</span>'
        '<span>Review every generated document before sending</span></div>',
        unsafe_allow_html=True,
    )
