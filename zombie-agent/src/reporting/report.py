"""Generate a self-contained HTML audit report from a RunState snapshot.

Visual language mirrors the live dashboard: Inter font, same CSS variables,
same status-pill colours. Print media query strips backgrounds and avoids
page-breaks inside cards.
"""

import html
import re
from typing import Any

from src.reporting.run_store import RunState


def _e(s: Any) -> str:
    return html.escape(str(s)) if s is not None else ""


def _fmt_cad(v: Any) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "N/A"
    if f >= 1_000_000:
        return f"${f / 1_000_000:.2f}M"
    if f >= 1_000:
        return f"${f / 1_000:.0f}K"
    return f"${f:,.0f}"


def _fmt_pct(v: Any) -> str:
    try:
        return f"{float(v) * 100:.0f}%"
    except (TypeError, ValueError):
        return "N/A"


_BANKRUPTCY_DISCLOSURE = (
    '<div style="margin-top:14px;padding:8px 12px;background:#F9FAFB;border:1px solid #E5E7EB;'
    'border-radius:6px;font-size:11px;color:#9CA3AF;line-height:1.5;">'
    "<strong>Bankruptcy registry coverage:</strong> not in this dataset. Downstream bankruptcies "
    "typically appear as “dissolved” / “struck” events in the Alberta non-profit "
    "registry or as T3010 self-dissolution (field_1570&nbsp;=&nbsp;TRUE), both of which are observable."
    "</div>"
)

_STATUS_COLOURS = {
    "verified": ("#059669", "#D1FAE5", "#065F46"),
    "challenged": ("#7C3AED", "#EDE9FE", "#4C1D95"),
    "pending": ("#D97706", "#FEF3C7", "#78350F"),
    "refuted": ("#9CA3AF", "#F3F4F6", "#374151"),
}


def _pill(status: str) -> str:
    border_c, bg, fg = _STATUS_COLOURS.get(status, ("#9CA3AF", "#F3F4F6", "#374151"))
    return (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:999px;'
        f"font-size:11px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;"
        f"background:{bg};color:{fg};border:1px solid {border_c}20;"
        f'">{_e(status)}</span>'
    )


def _section_header(title: str) -> str:
    return (
        f'<h2 style="font-size:13px;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:.08em;color:#6B7280;margin:32px 0 14px;'
        f'padding-bottom:8px;border-bottom:1px solid #E5E7EB;">'
        f"{_e(title)}</h2>"
    )


def _sub_header(title: str) -> str:
    return (
        f'<div style="font-size:11px;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:.07em;color:#9CA3AF;margin:18px 0 7px;">'
        f"{_e(title)}</div>"
    )


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return '<p style="font-size:13px;color:#9CA3AF;font-style:italic;">No data available.</p>'
    ths = "".join(
        f'<th style="padding:8px 12px;text-align:left;font-size:11px;font-weight:600;'
        f'text-transform:uppercase;letter-spacing:.06em;color:#6B7280;'
        f'border-bottom:2px solid #E5E7EB;white-space:nowrap;">{_e(h)}</th>'
        for h in headers
    )
    trs = ""
    for i, row in enumerate(rows):
        bg = "#F9FAFB" if i % 2 else "#FFFFFF"
        tds = "".join(
            f'<td style="padding:8px 12px;font-size:13px;border-bottom:1px solid #F3F4F6;'
            f'vertical-align:top;">{_e(c)}</td>'
            for c in row
        )
        trs += f'<tr style="background:{bg};">{tds}</tr>'
    return (
        '<div style="overflow-x:auto;margin-bottom:4px;">'
        '<table style="width:100%;border-collapse:collapse;font-size:13px;">'
        f"<thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table></div>"
    )


def _coerce_trail(v: Any) -> list:
    """Normalise a sql_trail value to a proper Python list.

    The agent should pass a list, but sometimes emits a semicolon-joined
    string instead. Calling list() on a string produces individual characters,
    so we handle both cases explicitly.
    """
    if isinstance(v, list):
        return v
    if isinstance(v, str) and v.strip():
        parts = [p.strip() for p in re.split(r"[;\n]+", v)]
        # De-dup while preserving order, drop empties
        seen: set = set()
        result = []
        for p in parts:
            if p and p not in seen:
                seen.add(p)
                result.append(p)
        return result
    return []


def _clean_trail_item(step: Any) -> str:
    """Normalise a sql_trail entry to a display string.

    The agent labels queries with a leading SQL comment (-- Step N: ...).
    Strip that prefix so the report shows clean text.
    """
    s = str(step).strip() if not isinstance(step, str) else step.strip()
    # Strip leading SQL comment markers: "-- Step 1:", "-- Step A1:", etc.
    if s.startswith("--"):
        s = s[2:].strip()
    return s


def _reasoning_chain(sql_trail: Any) -> str:
    raw = _coerce_trail(sql_trail)
    items = [_clean_trail_item(s) for s in raw if s]
    if not items:
        return ""
    lis = "".join(
        f'<li style="padding:3px 0;font-size:12px;color:#374151;">{_e(step)}</li>'
        for step in items
    )
    return (
        _sub_header("Reasoning Chain")
        + f'<ol style="padding-left:20px;line-height:1.6;">{lis}</ol>'
    )


def _verified_card(finding: dict, dossier: dict | None) -> str:
    name = _e(finding.get("entity_name") or finding.get("bn") or "Unknown Entity")
    bn = _e(finding.get("bn", ""))
    status = finding.get("verifier_status", "verified")
    funding = _fmt_cad(finding.get("total_funding_cad"))
    last_year = _e(finding.get("last_known_year", ""))
    dep_pct = _fmt_pct(finding.get("govt_dependency_pct"))
    evidence = _e(finding.get("evidence_summary", ""))
    verifier_notes = _e(finding.get("verifier_notes", ""))
    sql_trail_finding = _coerce_trail(finding.get("sql_trail", []))

    headline = ""
    death_text = ""
    funding_table = ""
    dep_table = ""
    overhead_block = ""
    sql_trail_dossier: list = []

    if dossier:
        headline = _e(dossier.get("headline", ""))
        death_text = _e(dossier.get("death_event_text", ""))
        sql_trail_dossier = _coerce_trail(dossier.get("sql_trail", []))

        fe = dossier.get("funding_events") or []
        if fe:
            fe_rows = [
                [
                    r.get("year", ""),
                    r.get("dept", ""),
                    r.get("program", ""),
                    _fmt_cad(r.get("amount_cad")),
                    r.get("start_date", ""),
                    r.get("end_date", ""),
                ]
                for r in fe
            ]
            funding_table = _sub_header("Funding Timeline") + _table(
                ["Year", "Dept", "Program", "Amount", "Start", "End"], fe_rows
            )

        dh = dossier.get("dependence_history") or []
        if dh:
            dh_rows = [
                [
                    r.get("fiscal_year", ""),
                    _fmt_pct(r.get("govt_share_pct")),
                    _fmt_cad(r.get("total_govt_cad")),
                    _fmt_cad(r.get("revenue_cad")),
                ]
                for r in dh
            ]
            dep_table = _sub_header("Government Dependency History") + _table(
                ["Fiscal Year", "Govt Share %", "Govt CAD", "Total Revenue"], dh_rows
            )

        oh = dossier.get("overhead_snapshot") or {}
        if oh:
            overhead_block = (
                _sub_header("Overhead Snapshot")
                + _table(
                    ["Fiscal Year", "Overhead %", "Programs CAD", "Admin & Fundraising"],
                    [
                        [
                            oh.get("fiscal_year", ""),
                            _fmt_pct(oh.get("strict_overhead_pct")),
                            _fmt_cad(oh.get("programs_cad")),
                            _fmt_cad(oh.get("admin_fundraising_cad")),
                        ]
                    ],
                )
            )

    combined_trail = sql_trail_dossier + [
        s for s in sql_trail_finding if s not in sql_trail_dossier
    ]

    title_line = (
        f'<div style="font-size:16px;font-weight:700;color:#111827;margin-bottom:4px;line-height:1.3;">'
        f"{name}</div>"
        + (
            f'<div style="font-size:13px;color:#374151;font-style:italic;margin-bottom:8px;line-height:1.4;">'
            f"{headline}</div>"
            if headline else ""
        )
    )
    meta_line = (
        f'<div style="font-size:12px;color:#6B7280;margin-bottom:12px;display:flex;'
        f'align-items:center;gap:12px;flex-wrap:wrap;">'
        f'<span>BN: {bn}</span>'
        f'{"<span>Last active: " + last_year + "</span>" if last_year else ""}'
        f'<span style="font-weight:700;color:#DC2626;">{funding}</span>'
        f'<span>Govt dependency: {dep_pct}</span>'
        f"{_pill(status)}</div>"
    )
    death_line = (
        f'<div style="background:#FEF2F2;border:1px solid #FECACA;border-radius:6px;'
        f'padding:8px 12px;font-size:13px;color:#991B1B;margin-bottom:14px;">'
        f"&#9888;&nbsp;{death_text}</div>"
        if death_text
        else ""
    )

    evidence_block = ""
    if evidence:
        evidence_block = (
            _sub_header("What Was Found")
            + f'<p style="font-size:13px;color:#374151;line-height:1.6;margin-bottom:4px;">{evidence}</p>'
        )
    verifier_block = ""
    if verifier_notes:
        verifier_block = (
            _sub_header("Independent Verification")
            + f'<p style="font-size:13px;color:#374151;line-height:1.6;font-style:italic;margin-bottom:4px;">{verifier_notes}</p>'
        )

    return (
        '<div style="background:#FFFFFF;border:1px solid #E5E7EB;border-radius:10px;'
        'padding:20px;margin-bottom:16px;page-break-inside:avoid;">'
        + title_line
        + meta_line
        + death_line
        + evidence_block
        + verifier_block
        + funding_table
        + dep_table
        + overhead_block
        + _reasoning_chain(combined_trail)
        + _BANKRUPTCY_DISCLOSURE
        + "</div>"
    )


def _challenged_card(finding: dict) -> str:
    name = _e(finding.get("entity_name") or finding.get("bn") or "Unknown Entity")
    bn = _e(finding.get("bn", ""))
    status = finding.get("verifier_status", "challenged")
    funding = _fmt_cad(finding.get("total_funding_cad"))
    last_year = _e(finding.get("last_known_year", ""))
    dep_pct = _fmt_pct(finding.get("govt_dependency_pct"))
    evidence = _e(finding.get("evidence_summary", ""))
    verifier_notes = _e(finding.get("verifier_notes", ""))
    sql_trail = _coerce_trail(finding.get("sql_trail", []))

    meta_line = (
        f'<div style="font-size:12px;color:#6B7280;margin-bottom:12px;display:flex;'
        f'align-items:center;gap:12px;flex-wrap:wrap;">'
        f'<span>BN: {bn}</span>'
        f'{"<span>Last active: " + last_year + "</span>" if last_year else ""}'
        f'<span style="font-weight:700;color:#DC2626;">{funding}</span>'
        f'<span>Govt dependency: {dep_pct}</span>'
        f"{_pill(status)}</div>"
    )
    evidence_block = (
        _sub_header("What Was Found")
        + f'<p style="font-size:13px;color:#374151;line-height:1.6;">{evidence}</p>'
        if evidence
        else ""
    )
    verifier_block = (
        _sub_header("Independent Verification")
        + f'<p style="font-size:13px;color:#374151;line-height:1.6;font-style:italic;">{verifier_notes}</p>'
        if verifier_notes
        else ""
    )
    return (
        '<div style="background:#FFFFFF;border:1px solid #E5E7EB;border-radius:10px;'
        'padding:20px;margin-bottom:16px;page-break-inside:avoid;">'
        f'<div style="font-size:15px;font-weight:700;color:#111827;margin-bottom:6px;">{name}</div>'
        + meta_line
        + evidence_block
        + verifier_block
        + _reasoning_chain(sql_trail)
        + _BANKRUPTCY_DISCLOSURE
        + "</div>"
    )


def _funnel_section(universe: dict) -> str:
    if not universe:
        return (
            '<p style="font-size:13px;color:#9CA3AF;font-style:italic;">'
            "Methodology funnel data not yet available — run the investigation first.</p>"
        )
    pre = universe.get("n_universe_pre_gate", "?")
    after_found = universe.get("n_after_foundation_filter", "?")
    after_live = universe.get("n_after_live_agreement_filter", "?")
    after_ncharity = universe.get("n_after_non_charity_filter", "?")
    final = universe.get("n_final_candidates", "?")

    def row(label: str, count: Any, note: str = "") -> str:
        note_span = (
            f'<span style="font-size:11px;color:#9CA3AF;margin-left:6px;">{_e(note)}</span>'
            if note
            else ""
        )
        return (
            f'<div style="display:flex;align-items:baseline;gap:8px;padding:6px 0;'
            f'border-bottom:1px solid #F3F4F6;">'
            f'<span style="font-size:20px;font-weight:700;color:#1D6AE5;'
            f'font-variant-numeric:tabular-nums;min-width:42px;text-align:right;">{_e(count)}</span>'
            f'<span style="font-size:13px;color:#374151;">{_e(label)}{note_span}</span>'
            f"</div>"
        )

    narrative = universe.get("narrative", "")
    narrative_block = (
        f'<blockquote style="border-left:3px solid #1D6AE5;padding:10px 16px;'
        f'margin:16px 0 0;background:#EFF6FF;border-radius:0 6px 6px 0;'
        f'font-size:13px;color:#1E40AF;line-height:1.6;">{_e(narrative)}</blockquote>'
        if narrative
        else ""
    )

    return (
        '<div style="background:#FFFFFF;border:1px solid #E5E7EB;border-radius:10px;'
        'padding:20px;margin-bottom:16px;">'
        + row(
            "federal recipients receiving ≥ $1M in committed funding",
            pre,
        )
        + row("after excluding Designation A/B foundations", after_found, "foundation gate")
        + row(
            "after excluding entities with active federal agreements",
            after_live,
            "live-agreement gate",
        )
        + row(
            "after excluding non-charity entities (municipal, hospital, university…)",
            after_ncharity,
            "non-charity gate",
        )
        + row("final zombie candidates surfaced for verification", final)
        + narrative_block
        + "</div>"
    )


def _summary_bar(findings: dict) -> str:
    counts: dict[str, int] = {"verified": 0, "challenged": 0, "pending": 0, "refuted": 0}
    total_risk = 0.0
    for f in findings.values():
        st = f.get("verifier_status", "pending")
        counts[st] = counts.get(st, 0) + 1
        try:
            total_risk += float(f.get("total_funding_cad") or 0)
        except (TypeError, ValueError):
            pass

    total = sum(counts.values())
    colours = {
        "verified": "#059669",
        "challenged": "#7C3AED",
        "pending": "#D97706",
        "refuted": "#9CA3AF",
    }
    segments = ""
    for st, colour in colours.items():
        pct = counts[st] / total * 100 if total else 0
        if pct > 0:
            segments += (
                f'<div style="flex:{pct};background:{colour};height:100%;'
                f'border-radius:4px;min-width:4px;" title="{st}: {counts[st]}"></div>'
            )

    legend = ""
    for st, colour in colours.items():
        if counts[st]:
            legend += (
                f'<span style="display:inline-flex;align-items:center;gap:5px;'
                f'font-size:12px;font-weight:500;color:#111827;">'
                f'<span style="width:8px;height:8px;border-radius:50%;background:{colour};'
                f'display:inline-block;"></span>'
                f"{counts[st]} {st.capitalize()}</span>"
            )

    return (
        '<div style="background:#FFFFFF;border:1px solid #E5E7EB;border-radius:10px;'
        'padding:20px;margin-bottom:16px;display:flex;align-items:center;gap:24px;flex-wrap:wrap;">'
        f'<div style="text-align:center;min-width:100px;">'
        f'<div style="font-size:28px;font-weight:700;color:#DC2626;'
        f'font-variant-numeric:tabular-nums;">{_fmt_cad(total_risk)}</div>'
        f'<div style="font-size:11px;text-transform:uppercase;letter-spacing:.08em;'
        f'color:#6B7280;margin-top:4px;font-weight:600;">Total Funding at Risk</div></div>'
        '<div style="flex:1;min-width:200px;">'
        '<div style="display:flex;height:10px;border-radius:6px;overflow:hidden;'
        f'background:#E5E7EB;gap:2px;margin-bottom:10px;">{segments}</div>'
        f'<div style="display:flex;gap:14px;flex-wrap:wrap;">{legend}</div>'
        f'<div style="font-size:12px;color:#9CA3AF;margin-top:6px;">'
        f"{total} leads surfaced total</div>"
        "</div></div>"
    )


def _executive_brief(findings: dict, universe: dict) -> str:
    """One-paragraph plain-language summary derived entirely from findings data."""
    all_f = list(findings.values())
    if not all_f:
        return ""

    counts: dict[str, int] = {"verified": 0, "challenged": 0, "pending": 0, "refuted": 0}
    verified_funding = 0.0
    total_funding = 0.0
    for f in all_f:
        st = f.get("verifier_status", "pending")
        counts[st] = counts.get(st, 0) + 1
        amt = float(f.get("total_funding_cad") or 0)
        total_funding += amt
        if st == "verified":
            verified_funding += amt

    n_total = len(all_f)
    n_verified = counts["verified"]
    n_refuted = counts["refuted"]
    n_final = universe.get("n_final_candidates") if universe else None

    verified_line = (
        f"<strong>{n_verified} {"lead was" if n_verified == 1 else "leads were"} independently "
        f"verified</strong>, representing a combined {_fmt_cad(verified_funding)} in committed "
        f"federal funding to organizations that no longer appear active on the public record."
        if n_verified > 0
        else "No leads have been independently verified yet."
    )

    refuted_line = (
        f" {n_refuted} {"candidate was" if n_refuted == 1 else "candidates were"} correctly "
        f"excluded by the methodology (public/private foundations, live agreements, or open "
        f"T3010 filing windows) — these exclusions are the methodology working as intended, "
        f"not failures."
        if n_refuted > 0
        else ""
    )

    funnel_line = (
        f" The search space covered {n_final} final candidate{"s" if (n_final or 0) != 1 else ""} "
        f"after passing all hard gates."
        if n_final is not None
        else ""
    )

    return (
        '<div style="background:#FFFFFF;border:1px solid #E5E7EB;border-radius:10px;'
        'padding:20px;margin-bottom:16px;font-size:14px;color:#374151;line-height:1.7;">'
        f"{verified_line}{refuted_line}{funnel_line}"
        "</div>"
    )


def _methodology_box() -> str:
    return (
        '<div style="background:#F9FAFB;border:1px solid #E5E7EB;border-radius:10px;'
        'padding:20px;margin-bottom:4px;font-size:13px;color:#374151;line-height:1.7;">'
        "<strong>Zombie Recipient</strong> — a federally funded charity that has since "
        "dissolved, had its registration revoked, or stopped filing T3010 returns, "
        "yet received federal commitments within the investigation window.<br><br>"
        "<strong>Datasets:</strong> FED Grants &amp; Contributions (fed schema), "
        "CRA T3010 charity filings (cra schema), Alberta non-profit registry (ab schema). "
        "Queried in read-only mode against the hackathon Postgres database.<br><br>"
        "<strong>Filing-window note:</strong> CRA gives charities 6 months after fiscal "
        "year-end to file. The 2024 filing window may still be open — entities in that "
        "window are excluded from the candidate list and will appear as Refuted if surfaced.<br><br>"
        "<strong>Status meanings:</strong> "
        "<em>Verified</em> — both the primary investigator and the independent verifier "
        "confirmed the zombie signal. "
        "<em>Challenged</em> — initially flagged, contested by the verifier, then "
        "re-examined and re-confirmed. "
        "<em>Pending</em> — surfaced but not yet verified. "
        "<em>Refuted</em> — correctly excluded (foundation, live agreement, "
        "filing window open, or rebrand).<br><br>"
        "<strong>Disclaimer:</strong> This report contains investigative audit leads, "
        "not legal conclusions. Every lead warrants follow-up by a qualified auditor. "
        'Use language like &ldquo;signals consistent with a dormant funded recipient&rdquo; and '
        '&ldquo;public-record gaps that warrant follow-up&rdquo; when acting on these leads.'
        "</div>"
    )


def _compact_table(findings_list: list[dict], include_notes: bool = True) -> str:
    headers = ["Entity", "BN", "Funding", "Govt Dep."]
    if include_notes:
        headers.append("Notes")
    rows = []
    for f in findings_list:
        name = f.get("entity_name") or f.get("bn") or "Unknown"
        bn = f.get("bn", "")
        funding = _fmt_cad(f.get("total_funding_cad"))
        dep = _fmt_pct(f.get("govt_dependency_pct"))
        row: list[Any] = [name, bn, funding, dep]
        if include_notes:
            row.append(f.get("verifier_notes") or "—")
        rows.append(row)
    return _table(headers, rows)


def generate_html(state: RunState, is_running: bool = False) -> str:
    has_findings = bool(state.findings)

    if not has_findings:
        if is_running:
            heading = "Investigation in progress"
            body = "First findings will appear here shortly — this page auto-refreshes every 5 seconds."
            refresh = 5
        else:
            heading = "No findings recorded yet"
            body = "Open the dashboard to start the investigation — this page auto-refreshes every 10 seconds."
            refresh = 10
        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta http-equiv="refresh" content="{refresh}"/>
<title>Zombie Recipients — Audit Report</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet"/>
<style>
body{{font-family:'Inter',system-ui,sans-serif;background:#F0F2F5;display:flex;
align-items:center;justify-content:center;height:100vh;margin:0;color:#6B7280;flex-direction:column;gap:12px;}}
h1{{font-size:16px;font-weight:600;color:#111827;}}
p{{font-size:13px;}}
</style>
</head>
<body>
<h1>{heading}</h1>
<p>{body}</p>
</body>
</html>"""

    # ── Classify findings ────────────────────────────────────────────
    verified = sorted(
        [f for f in state.findings.values() if f.get("verifier_status") == "verified"],
        key=lambda f: float(f.get("total_funding_cad") or 0),
        reverse=True,
    )
    challenged = [
        f for f in state.findings.values() if f.get("verifier_status") == "challenged"
    ]
    pending = [
        f for f in state.findings.values() if f.get("verifier_status") == "pending"
    ]
    refuted = [
        f for f in state.findings.values() if f.get("verifier_status") == "refuted"
    ]

    # ── Status badge ─────────────────────────────────────────────────
    if state.is_complete:
        badge_bg, badge_fg, badge_text = "#D1FAE5", "#065F46", "COMPLETE"
    else:
        badge_bg, badge_fg, badge_text = "#FEF3C7", "#78350F", "IN PROGRESS"

    # ── Meta footer ──────────────────────────────────────────────────
    meta = state.run_meta
    footer_parts = []
    if meta.get("duration_ms"):
        try:
            secs = int(meta["duration_ms"]) // 1000
            footer_parts.append(f"Duration: {secs}s")
        except (TypeError, ValueError):
            pass
    if meta.get("num_turns"):
        footer_parts.append(f"Turns: {meta['num_turns']}")
    if meta.get("total_cost_usd") is not None:
        try:
            footer_parts.append(f"Cost: ${float(meta['total_cost_usd']):.4f}")
        except (TypeError, ValueError):
            pass

    # ── Verified cards ───────────────────────────────────────────────
    verified_html = "".join(
        _verified_card(f, state.dossiers.get(f.get("bn", ""))) for f in verified
    )
    if not verified_html:
        verified_html = (
            '<p style="font-size:13px;color:#9CA3AF;font-style:italic;">No verified leads.</p>'
        )

    # ── Challenged cards ─────────────────────────────────────────────
    challenged_html = ""
    if challenged:
        challenged_html = (
            _section_header("Challenged Leads")
            + '<p style="font-size:13px;color:#6B7280;margin-bottom:14px;">'
            'These leads were initially flagged, contested by the independent verifier, '
            "then re-examined and re-confirmed through additional SQL evidence.</p>"
            + "".join(_challenged_card(f) for f in challenged)
        )

    # ── Pending table ─────────────────────────────────────────────────
    pending_html = ""
    if pending:
        pending_html = (
            _section_header("Pending Leads")
            + '<p style="font-size:13px;color:#6B7280;margin-bottom:14px;">'
            "Surfaced by the methodology but not yet verified.</p>"
            + _compact_table(pending, include_notes=False)
        )

    # ── Refuted table ────────────────────────────────────────────────
    refuted_html = ""
    if refuted:
        refuted_html = (
            _section_header("Refuted Leads")
            + '<p style="font-size:13px;color:#6B7280;margin-bottom:14px;">'
            "Correctly excluded by the methodology. Common reasons: Designation A/B foundation, "
            "live federal agreement, T3010 filing window still open, or confirmed rebrand.</p>"
            + _compact_table(refuted, include_notes=True)
        )

    refresh_tag = '' if state.is_complete else '<meta http-equiv="refresh" content="8"/>'

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
{refresh_tag}
<title>Zombie Recipients — Audit Report</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet"/>
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
  background: #F0F2F5; color: #111827;
  font-size: 14px; line-height: 1.5;
}}
.page {{ max-width: 900px; margin: 0 auto; padding: 32px 24px 64px; }}

/* Header */
.report-header {{
  background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 10px;
  padding: 24px 28px; margin-bottom: 24px;
  display: flex; align-items: flex-start; justify-content: space-between; gap: 16px;
  flex-wrap: wrap;
}}
.report-title {{ font-size: 20px; font-weight: 700; color: #111827; margin-bottom: 4px; }}
.report-subtitle {{ font-size: 12px; color: #9CA3AF; font-weight: 500; letter-spacing: .06em; text-transform: uppercase; }}
.report-meta {{ font-size: 12px; color: #6B7280; margin-top: 6px; }}
.status-badge {{
  display: inline-block; padding: 4px 12px; border-radius: 999px;
  font-size: 11px; font-weight: 700; letter-spacing: .07em; text-transform: uppercase;
  background: {badge_bg}; color: {badge_fg};
  flex-shrink: 0;
}}

/* Footer */
.report-footer {{
  margin-top: 40px; padding-top: 16px; border-top: 1px solid #E5E7EB;
  font-size: 11px; color: #9CA3AF; line-height: 1.6;
}}

@media print {{
  body {{ background: #fff; }}
  .page {{ padding: 0; }}
  .report-header {{ page-break-inside: avoid; }}
  div[style*="page-break-inside:avoid"] {{ page-break-inside: avoid; }}
}}
</style>
</head>
<body>
<div class="page">

  <!-- Header -->
  <div class="report-header">
    <div>
      <div class="report-title">Zombie Recipients — Accountability Audit Report</div>
      <div class="report-subtitle">AI For Accountability &middot; Ottawa 2026</div>
      <div class="report-meta">Generated: {_e(state.run_date)}</div>
    </div>
    <div class="status-badge">{_e(badge_text)}</div>
  </div>

  <!-- Executive Overview -->
  {_section_header("Executive Overview")}
  {_summary_bar(state.findings)}
  {_executive_brief(state.findings, state.universe)}
  {_section_header("Methodology Funnel")}
  {_funnel_section(state.universe)}

  <!-- How to read -->
  {_section_header("How to Read This Report")}
  {_methodology_box()}

  <!-- Verified leads -->
  {_section_header("Verified Audit Leads")}
  {verified_html}

  {challenged_html}
  {pending_html}
  {refuted_html}

  <!-- Footer -->
  <div class="report-footer">
    {" &middot; ".join(footer_parts) if footer_parts else ""}
    {"<br/>" if footer_parts else ""}
    Data source: CRA T3010 (2020–2024), FED Grants &amp; Contributions, AB Non-Profit Registry.
    Read-only access via the hackathon PostgreSQL database. All figures trace to SQL queries
    executed during this session. This report contains investigative audit leads, not legal
    conclusions. Produced by the Zombie Recipients AI agent (Claude Opus 4.7 + Claude Agent SDK).
  </div>

</div>
</body>
</html>"""
