"""MerchantOS: shared navigation, typography, and financial UI primitives."""
from __future__ import annotations

import html
import os
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import streamlit as st


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def app_urls() -> dict[str, str]:
    host = os.getenv("MERCHANTOS_HOST", "localhost")
    return {
        key: os.getenv(env, f"http://{host}:{os.getenv(port_env, port)}")
        for key, env, port_env, port in [
            ("home", "MERCHANTOS_HOME_URL", "PORT_HOME", "8501"),
            ("agent1", "MERCHANTOS_AGENT1_URL", "PORT_AGENT1", "8502"),
            ("agent2", "MERCHANTOS_AGENT2_URL", "PORT_AGENT2", "8503"),
            ("agent3", "MERCHANTOS_AGENT3_URL", "PORT_AGENT3", "8504"),
        ]
    }


def icon(name: str) -> str:
    paths = {
        "home": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
        "agent1": '<path d="M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6Z"/><path d="m8 12 3 3 5-6"/>',
        "agent2": '<path d="M4 3h16v18l-4-2-4 2-4-2-4 2Z"/><path d="M8 7h8M8 11h8M8 15h4"/>',
        "agent3": '<path d="M6 3h9l4 4v14H6Z"/><path d="M14 3v5h5M9 12h7M9 16h5"/>',
        "arrow": '<path d="M4 12h15m-6-6 6 6-6 6"/>',
    }
    return f'<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{paths.get(name, paths["arrow"])}</svg>'


def inject_theme(accent: str = "") -> None:
    css = Path(__file__).with_name("styles.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def nav(active: str) -> None:
    items = [("home", "Overview"), ("agent1", "KYC & fund holds"), ("agent2", "Reconciliation"), ("agent3", "Escalation")]
    urls = app_urls()
    with st.sidebar:
        st.markdown('<a class="brand" href="' + esc(urls["home"]) + '" target="_self"><span class="brand-mark"><i></i><i></i><i></i></span>merchant<span class="brand-os">os</span></a>', unsafe_allow_html=True)
        st.markdown('<div class="workspace"><span class="workspace-avatar">M</span><div><strong>' + esc(os.getenv("MERCHANT_WORKSPACE_NAME", "Merchant workspace")) + '</strong><small>' + esc(os.getenv("MERCHANT_REGION", "India")) + ' · ' + esc(os.getenv("MERCHANT_CURRENCY", "INR")) + '</small></div></div><div class="rail-label">WORKSPACE</div>', unsafe_allow_html=True)
        links = "".join(f'<a href="{esc(urls[key])}" target="_self" class="rail-link {"active" if key == active else ""}" {"aria-current=page" if key == active else ""}>{icon(key)}<span>{label}</span>{"<b></b>" if key == active else ""}</a>' for key, label in items)
        st.markdown(f'<nav class="rail-nav" aria-label="Main navigation">{links}</nav>', unsafe_allow_html=True)
        st.markdown('<div class="rail-note"><span class="rail-label">YOUR RECOVERY DESK</span><p>A clear record.<br>A considered next step.</p><span>Diagnose → Reconcile → Resolve</span></div>', unsafe_allow_html=True)
        with st.expander("Workspace guide"):
            st.caption("KYC: identify a restriction and prepare documents. Reconciliation: inspect a payout report. Escalation: assemble correspondence from your case details.")
        st.markdown('<div class="rail-bottom"><span class="small-mark">M</span><span>MerchantOS<br><small>Payment operations</small></span></div>', unsafe_allow_html=True)
    label = dict(items)[active]
    st.markdown(f'<div class="topline"><div>Workspace <span>/</span> <strong>{label}</strong></div><div class="topline-meta"><span class="currency">' + esc(os.getenv("MERCHANT_CURRENCY", "INR")) + '</span><span>{date.today():%d %b %Y}</span></div></div>', unsafe_allow_html=True)


def hero(eyebrow: str, title: str, description: str) -> None:
    st.markdown(f'<header class="page-heading"><div class="eyebrow">{esc(eyebrow)}</div><h1>{esc(title)}</h1><p>{esc(description)}</p></header>', unsafe_allow_html=True)


def section_title(title: str, description: str = "") -> None:
    st.markdown(f'<div class="section-heading"><h2>{esc(title)}</h2><span>{esc(description)}</span></div>', unsafe_allow_html=True)


def metric(label: str, value: str, subtitle: str = "", color: str = "") -> None:
    st.markdown(f'<div class="metric"><div>{esc(label)}</div><strong>{esc(value)}</strong><small>{esc(subtitle)}</small></div>', unsafe_allow_html=True)


def badge(text: str, tone: str = "info") -> str:
    return f'<span class="badge {esc(tone)}"><i></i>{esc(text)}</span>'


@contextmanager
def panel(title: str = "", subtitle: str = "", key: str | None = None):
    with st.container(border=True, key=key):
        if title:
            st.markdown(f'<div class="panel-heading"><h3>{esc(title)}</h3><p>{esc(subtitle)}</p></div>', unsafe_allow_html=True)
        yield


def steps(labels: list[str], current: int) -> None:
    rows = "".join(
        f'<div class="journey-step {"complete" if i < current else "current" if i == current else ""}"><span>{"✓" if i < current else str(i + 1).zfill(2)}</span><div>{esc(label)}<small>{"Complete" if i < current else "In progress" if i == current else "Up next"}</small></div></div>'
        for i, label in enumerate(labels)
    )
    st.markdown(f'<div class="journey">{rows}</div>', unsafe_allow_html=True)


def note(title: str, body: str) -> None:
    st.markdown(f'<aside class="context-note"><span class="note-star">✳</span><h3>{esc(title)}</h3><p>{esc(body)}</p></aside>', unsafe_allow_html=True)


def footer() -> None:
    st.markdown('<div class="page-footer"><span>merchantos <span class="footer-dot">/</span> Made for merchant operations</span><span>Guidance, not legal representation</span></div>', unsafe_allow_html=True)
