# Zombie Agent — Web-Presence Augmentation Addendum

> Companion to `zombie_agent_build_manual_v2.md`, `zombie_agent_v3_correctness_and_polish.md`, `zombie_agent_lobby_addendum.md`, and `zombie_agent_corp_pa_addendum.md`. Adds a per-candidate web-presence probe (probe 8) using the Wayback Machine Availability API and lightweight live HTTP HEAD checks. Read v2 + v3 first; this only documents the delta.

> **v3 alignment note.** This probe slots into v3 §D1's precedence chain at the AMBIGUOUS-side (CHECK 13), not as a primary verdict driver. It is a tie-breaker for borderline candidates, not a refutation engine. v3 §D8 (REFUTED is final) still applies — a positive web-presence signal cannot flip a CHECK 2b REFUTED to VERIFIED.

---

## 1. What this adds

The seven existing probes (1–7) are all **government-side**: they ask whether the state's records show the entity as alive. Web-presence is the first **recipient-side** probe — it asks whether the entity is *projecting* aliveness publicly.

The story shifts from

> "$2.4M to {entity}, no T3010 since 2022, status 3 in CORP"

to

> "$2.4M to {entity}, no T3010 since 2022, status 3 in CORP, **and the website hasn't been updated since 2021-09 — last archived snapshot Sep 2021, domain still resolves but serves a parked-domain page.**"

Web silence is the public-facing equivalent of registry silence. It does not by itself prove a zombie — small charities can be alive and absent from the web, large corporations can have zombie subsidiaries with active websites — but combined with at least one government-side death signal, it is a strong dual-confirmation that "the entity has stopped operating" rather than just "the entity has stopped filing paperwork."

This is the **first signal in the entire pipeline that does not depend on a Canadian government source.** That matters for differentiation: the demo can claim it cross-references public-sector and private-sector evidence, not just public-sector records against each other.

---

## 2. Data shape, in one screen

### Wayback Machine Availability API

- **Base URL:** `http://archive.org/wayback/available`
- **Auth:** none (anonymous, no API key)
- **Rate limits:** undocumented but generous — Internet Archive has hosted this for ~15 years against constant traffic. Treat as practically unlimited for hackathon-scale usage (5–10 candidates per demo run).
- **Query:** `?url={domain}&timestamp={YYYYMMDD}`
- **Response shape:**
  ```json
  { "archived_snapshots": { "closest": {
        "available": true,
        "url": "https://web.archive.org/web/20210904.../https://example.org/",
        "timestamp": "20210904120000",
        "status": "200" } } }
  ```
  Returns `{"archived_snapshots":{}}` when nothing matches.

### Live HTTP HEAD probe (no third-party API)

A single `curl -sIL --max-time 5` against the candidate domain. Returns one of:

| Outcome | Meaning |
|---|---|
| `200` with content-type `text/html` and a non-trivial Content-Length | Domain is live and serving a page |
| `200` but Content-Length < 1KB or content-type points to a parked-domain landing | Domain is registered but parked |
| Connection timeout / DNS failure | Domain is offline or never existed |
| `30x` redirecting to a generic registrar landing | Parked / for-sale |

The HEAD probe is the cheap pre-check before paying the Wayback round-trip. If the domain doesn't even resolve, we know the answer.

### Domain candidate generation

The candidate's legal name → set of plausible domains. For *"Canada World Youth"*:

```
canada-world-youth.org
canadaworldyouth.org
canadaworldyouth.ca
canadaworldyouth.com
cwy-jcm.org           # bilingual abbreviation pattern, low priority
```

Generation rule (in priority order, stop at first hit):
1. Lowercase, strip non-alphanumeric, join with `-` → `.org`, `.ca`, `.com`
2. Lowercase, strip non-alphanumeric, no separator → `.org`, `.ca`, `.com`
3. First letter of each significant word → `.org`, `.ca`, `.com` (only if the entity name has 3+ words)

Cap at 6 candidate domains per entity to keep the probe budget bounded.

### Coverage reality check

| Entity type | Domain hit-rate (estimated) |
|---|---:|
| FED grant recipients ≥ $1M | ~85% have at least one resolvable domain |
| FED grant recipients $100K–$1M | ~60% |
| Charities only (CRA designation C, ≥ $500K) | ~75% |
| Sole-proprietorship / individual recipients | ~10% |

Web-presence is **medium-recall, high-precision** — big-ticket recipients almost always have a website, but small ones often don't. The probe must distinguish "no domain found" (the entity is small and never had one) from "domain dark since 2021" (the entity went silent). Use the latter as a death signal; the former as a no-op.

---

## 3. The new probe

The probe lives as a new in-process MCP tool, not a new schema. It runs on the verifier subagent's allow-list alongside `mcp__postgres__execute_sql`.

### Tool definition (Python, in `zombie-agent/src/mcp_servers/web_presence.py`)

```python
import asyncio
import re
import httpx
from claude_agent_sdk import tool, create_sdk_mcp_server

@tool(
    "probe_web_presence",
    "Check whether an entity's likely website domains resolve and whether they "
    "have recent Wayback Machine snapshots. Returns a structured result usable "
    "for AMBIGUOUS tie-breaking. Cap at 1 call per candidate.",
    {
        "legal_name": str,
        "last_grant_year": int,    # used to compute the gone_dark threshold
    },
)
async def probe_web_presence(args):
    name = args["legal_name"]
    threshold_year = args["last_grant_year"]

    domains = generate_candidate_domains(name)[:6]
    async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
        results = await asyncio.gather(
            *[probe_one(client, d) for d in domains],
            return_exceptions=True,
        )

    live = [r for r in results if isinstance(r, dict) and r["resolves"]]
    if not live:
        return {"verdict": "no_domain_found", "domains_tried": domains}

    # Pick the most authoritative live domain (200, biggest payload).
    best = max(live, key=lambda r: (r["status"] == 200, r["content_length"]))

    # Wayback lookup for the chosen domain.
    way = await wayback_latest(client, best["domain"])
    last_snapshot_year = way["year"] if way else None

    gone_dark = (
        last_snapshot_year is not None
        and last_snapshot_year < threshold_year
    )

    return {
        "verdict": (
            "active"     if last_snapshot_year and last_snapshot_year >= threshold_year else
            "gone_dark"  if gone_dark else
            "no_snapshot"
        ),
        "domain":              best["domain"],
        "live_status":         best["status"],
        "parked_likely":       best["content_length"] < 1024,
        "last_snapshot_year":  last_snapshot_year,
        "last_snapshot_url":   way["url"] if way else None,
    }

def generate_candidate_domains(name: str) -> list[str]:
    """Lowercased, stripped → with-hyphens and no-separator forms × {.org, .ca, .com}."""
    slug = re.sub(r"[^a-z0-9 ]+", "", name.lower()).strip()
    words = slug.split()
    if not words:
        return []
    hyphenated = "-".join(words)
    glued = "".join(words)
    domains = []
    for stem in (hyphenated, glued):
        for tld in (".org", ".ca", ".com"):
            domains.append(stem + tld)
    if len(words) >= 3:
        initials = "".join(w[0] for w in words if w)
        for tld in (".org", ".ca", ".com"):
            domains.append(initials + tld)
    return list(dict.fromkeys(domains))  # dedupe, preserve order

async def probe_one(client, domain: str) -> dict:
    try:
        r = await client.head(f"https://{domain}", timeout=5.0)
        return {
            "domain": domain,
            "resolves": True,
            "status": r.status_code,
            "content_length": int(r.headers.get("content-length", 0)),
        }
    except Exception:
        return {"domain": domain, "resolves": False, "status": 0, "content_length": 0}

async def wayback_latest(client, domain: str) -> dict | None:
    try:
        r = await client.get(
            "http://archive.org/wayback/available",
            params={"url": domain, "timestamp": "20260101"},
            timeout=5.0,
        )
        data = r.json()
        c = data.get("archived_snapshots", {}).get("closest")
        if not c or not c.get("available"):
            return None
        ts = c.get("timestamp", "")
        return {
            "year": int(ts[:4]) if len(ts) >= 4 else None,
            "url": c.get("url"),
        }
    except Exception:
        return None

web_presence_mcp = create_sdk_mcp_server(
    name="web_presence",
    version="0.1.0",
    tools=[probe_web_presence],
)
```

### Wiring into `agent.py`

Add to `mcp_servers` and to the verifier's tool allow-list. Keep the orchestrator OUT — only the verifier should call this probe, to bound it at one call per candidate. Add to `ClaudeAgentOptions`:

```python
mcp_servers={
    "postgres": postgres_mcp,
    "ui_bridge": ui_bridge_mcp,
    "web_presence": web_presence_mcp,   # NEW
},
agents={
    "verifier": AgentDefinition(
        ...,
        tools=[
            "mcp__postgres__execute_sql",
            "mcp__web_presence__probe_web_presence",  # NEW
        ],
        ...
    ),
},
```

### Verdict interpretation

| Probe verdict | Meaning |
|---|---|
| `active` | Last snapshot >= last_grant_year. The entity has been online since the grant ended. **Tilts AMBIGUOUS toward REFUTED.** |
| `gone_dark` | Domain resolves but last snapshot < last_grant_year. The entity *had* a website, then stopped maintaining it. **Tilts AMBIGUOUS toward VERIFIED — strongest soft signal.** |
| `no_snapshot` | Domain resolves but Wayback never captured it (or only pre-incorporation). Inconclusive — could be a tiny entity that never had archive coverage. |
| `no_domain_found` | None of the 6 candidate domains resolve. Inconclusive on its own — small charities often never had a domain. Combined with a positive registry death signal, this is a "fully invisible" entity — strong final-card framing. |

---

## 4. How the verifier uses it

Web-presence is **CHECK 13 in v3's precedence chain — at the AMBIGUOUS-side, not the primary VERIFIED/REFUTED side**. The verifier already has decisive checks for live agreements (CHECK 2b), recent CORP filings (CHECK 9), and recent PA payments (CHECK 10). Web-presence runs *after* those have determined the candidate is in the AMBIGUOUS or borderline-VERIFIED zone.

### Updated precedence chain (v3 + corp-pa addendum + this addendum)

```
1.  CHECK 5  (vw_agreement_current total < $1M)                  → REFUTED
2.  CHECK 0  (designation A or B)                                → REFUTED
3.  CHECK 9  (CORP Active + recent annual return)                → REFUTED
4.  CHECK 1  (T3010 filing window still open)                    → REFUTED
5.  CHECK 7  (entity rebranded)                                  → REFUTED
6.  CHECK 2b (FED agreement_end_date >= 2024-01-01)              → REFUTED
7.  CHECK 3  (any AB payment > 0 in FY2024-25 / FY2025-26)       → REFUTED
8.  CHECK 10 (PA recent payment)                                 → REFUTED
9.  CHECK 11 (CORP Dissolved or Dissolution Pending)             → VERIFIED
10. CHECK 8  (field_1570 = TRUE)                                 → VERIFIED
11. CHECK 12 (PA empty + ≥$100K + ≥12mo old)                     → VERIFIED
12. CHECK 6  (govt_share_of_rev < 70)                            → AMBIGUOUS
13. CHECK 13 (web-presence probe — AMBIGUOUS tie-breaker)        → AMBIGUOUS-lean-VERIFIED if `gone_dark`,
                                                                    AMBIGUOUS-lean-REFUTED if `active`,
                                                                    no change otherwise
14. otherwise (death signal fired AND nothing above triggered)   → VERIFIED
```

**Why CHECK 13 is at this position.**

- Above CHECK 12 would let web-silence flip an empty-PA candidate from VERIFIED to AMBIGUOUS, which is a precision *loss* — PA-empty + agreement ≥ $100K is already a strong dollar-trail signal that doesn't need web confirmation.
- Below CHECK 6 means it only fires when the verifier has already concluded "the registry-side evidence is mixed." That's exactly when a recipient-side signal helps.
- CHECK 13 **never overturns** a verdict from CHECKs 1–12. It only colors the AMBIGUOUS bucket toward one side or the other, and lets the orchestrator decide whether to spend a rebuttal-turn query on the candidate.

### Append to the verifier prompt

```
 13. If the verdict so far is AMBIGUOUS, call probe_web_presence(legal_name,
     last_grant_year) ONCE per candidate. The result colors the AMBIGUOUS
     verdict but does not flip it to VERIFIED or REFUTED on its own:

     - verdict="gone_dark"        → tilt AMBIGUOUS toward VERIFIED. Surface
                                    the last_snapshot_year in the verdict
                                    reason. Tell the orchestrator: "consider
                                    a rebuttal-turn defending VERIFIED."
     - verdict="active"           → tilt AMBIGUOUS toward REFUTED. Surface
                                    the last_snapshot_year. Tell the
                                    orchestrator: "consider conceding."
     - verdict="no_snapshot"      → no change.
     - verdict="no_domain_found"  → no change UNLESS the entity is
                                    explicitly registered as a charity in
                                    CRA — in which case "no public web
                                    presence" is mildly suggestive but
                                    still not decisive.

     Do NOT call probe_web_presence on candidates already marked VERIFIED
     or REFUTED by CHECKs 1–12. The probe budget is one call per AMBIGUOUS
     candidate, no exceptions.
```

---

## 5. How the orchestrator uses it

### Step C — defending an AMBIGUOUS verdict (v2 §7 iterative-exploration loop)

When the verifier returns AMBIGUOUS with web-presence verdict `gone_dark`, the orchestrator's rebuttal-turn budget should prioritize:

1. **Pull the historical snapshot to confirm.** A single fetch of the Wayback URL the probe returned. If the snapshot landing page mentions a wind-down ("we are no longer accepting clients", "operations ended", "thank you for X years") that is itself a publishable evidence string. Cap at one fetch per candidate.

2. **Cross-reference the snapshot date to the agreement timeline.** If the snapshot's last update is within 30 days of the agreement end date, that's "the website went silent at the same moment the funding stopped" — surface as a finding.

The orchestrator does NOT need its own web-presence MCP. The verifier has already paid the round-trip; the orchestrator just consumes the verdict from the verifier's output.

### Step B — candidate ranking

If the orchestrator pre-enriches Step A candidates with a one-shot web-presence batch (within v3 §E4 pre-materialised candidate table), it gets a 4th tie-breaker after `(corp_status, pa_empty, originals)`:

```sql
-- Inside Step A pre-materialisation (v3 §E4):
ORDER BY
  (corp_status_code IN (3, 11))::int DESC,    -- CORP death first
  (pa_total_paid IS NULL)::int DESC,          -- PA empty next
  (web_last_snapshot_year < grant_end_year)::int DESC,  -- web gone dark
  originals DESC                              -- dollar tie-break
```

The web column is populated by a one-shot script that calls `probe_web_presence` for each candidate (~5 candidates × ~3s wall = 15s) and stores the result in the same JSONL/temp table v3 §E4 generates.

---

## 6. Briefing card surface

Two new fields on `publish_finding`:

```json
{
  "web_status": "gone_dark",
  "web_last_snapshot_year": 2021,
  "web_last_snapshot_url": "https://web.archive.org/web/20210904.../https://example.org/"
}
```

UI rendering, beneath the CORP and PA chips:

- **Web status chip:** small icon + year. `🌐 dark since 2021` (red), `🌐 active 2024` (green), `🌐 not found` (gray, hidden by default — only show on click-to-expand). Click opens the snapshot URL in a new tab — let the audience see the historical homepage themselves.

For the v3 §E1 dossier panel, add a **sub-view 6 — Web archive snapshot**: an iframe embedding the most recent Wayback snapshot. (Wayback snapshots are designed to be embedded.) Two sub-views per page is plenty; only render this one when `web_status` is `gone_dark` and the demo benefits from showing it.

---

## 7. Connecting and deps

- **No new database schema.** Web-presence is a live probe, not a stored table.
- **One new pip dependency:** `httpx` (the verifier's existing stack uses it already if v3 §E2 was implemented).
- **No new env var, no new credentials.** Wayback is anonymous.
- **Network egress required.** The agent's container must allow outbound HTTPS to `archive.org` and arbitrary external HTTPS hosts. If the demo is behind a corporate firewall, pre-warm by running the probe against the 5 demo candidates the morning of and caching the results to disk — fall back to the cache if live probes time out.

---

## 8. Setup checklist

```bash
# 1. Add httpx if not already installed
cd zombie-agent && uv add httpx

# 2. Create the new MCP server file (paste the §3 code into):
#    zombie-agent/src/mcp_servers/web_presence.py

# 3. Wire into agent.py mcp_servers and verifier tools (see §3)

# 4. Smoke-test the probe directly
cd zombie-agent && uv run python -c "
import asyncio
from src.mcp_servers.web_presence import probe_web_presence
async def main():
    print(await probe_web_presence({
        'legal_name': 'Canada World Youth',
        'last_grant_year': 2022,
    }))
asyncio.run(main())
"
# Expect: { "verdict": "gone_dark" or "active", "domain": "...", "last_snapshot_year": <int> }

# 5. Pre-warm cache for the demo candidates (saves ~15s of probe wall-time)
cd zombie-agent && uv run python scripts/prewarm_web_probe.py \
  --candidates Canada\ World\ Youth,Interagency\ Coalition\ on\ AIDS,Learning\ Partnership
```

---

## 9. Things to watch for during the demo

- **The probe is one call per AMBIGUOUS candidate, hard-capped.** Do not let the verifier loop on it. The budget is a single tool call per candidate; further calls are a bug.
- **DNS failures are not zombie signals.** A domain that doesn't resolve at probe time may have just been temporarily mis-served, the registrar might be doing maintenance, etc. Wayback is the authoritative signal — if archive.org has snapshots through 2024, the entity *was* online recently regardless of today's DNS.
- **Domain-name guessing is brittle.** `Canadian Energy Research Institute` → `cer.org` (wrong — CER is the Canadian Energy Regulator). The probe's 6-domain cap is intentional precision-over-recall; never expand it. False-positive matches against unrelated organizations sharing common acronyms is the worst failure mode.
- **Wayback can show archived 404s.** The `closest` snapshot may be a 404 page if Wayback crawled the domain post-takedown. Read `closest.status` — `200` is what we want; `404`/`5xx` snapshots should be treated as `no_snapshot`.
- **Active social media but dead website is real.** A small charity may have no website but an active Facebook page. The probe currently doesn't check social platforms — Twitter/X, Facebook, LinkedIn all rate-limit anonymous lookups aggressively. Out of scope. Mention as a known limitation if a judge asks.
- **Do not over-feature in the pitch.** Web-presence is a tie-breaker, not the headline. The headline is still SDTC dissolved by Parliament — the web-presence layer just makes the dossier panel more visceral. Keep it as supporting evidence, not as the lede.
- **CC-BY licensing for Wayback snapshots.** Internet Archive content is reusable but cite it. Each snapshot URL embedded in the dossier should display the snapshot date in the surrounding chrome — don't pretend you're showing a live page.

---

## 10. The combined demo punchline (slide 2 candidates, refreshed)

The §10 candidates from the corp-pa addendum gain a fourth attribute. For the **Canada World Youth** verifier walk specifically (the v3 §8.2 stable VERIFIED set):

```
Step A surfaces:        Canada World Youth (BN 118973999)
CHECK 5  (≥$1M)         pass — $3.07M
CHECK 0  (designation)  pass — designation C
CHECK 9  (CORP active)  silent — let me note: provincially incorporated
                        (Quebec), no federal CORP match
CHECK 1  (T3010 open)   silent — last fpe 2023-03-31
CHECK 7  (rebrand)      silent
CHECK 2b (live agreem.) silent — agreements wrapped pre-2024
CHECK 3  (AB payment)   silent
CHECK 10 (PA recent)    silent
CHECK 11 (CORP died)    silent (no federal CORP record)
CHECK 8  (field_1570)   FIRES — self-dissolution attested
CHECK 12 (PA empty)     would fire (PA empty), but CHECK 8 already
                        fires — verdict locked at VERIFIED
CHECK 13 (web)          ENRICHES — last Wayback snapshot 2023-06,
                        domain canadaworldyouth.org now serves a
                        registrar-parked page

Verdict: VERIFIED
Briefing chips:  ✓ Self-dissolved (T3010)  ✓ PA empty  🌐 dark since 2023
Headline: "$3.07M to a charity that self-dissolved March 2023, where
          government funding was 81% of revenue, and whose website
          went dark June 2023."
```

The web-presence chip turns the dossier panel from *"the government records say they're gone"* into *"and you can see they're gone — here is the last Wayback snapshot of their homepage."* That is the recipient-side confirmation the v2 plan was missing.

---

## 11. Optional: higher-precision paths (post-hackathon)

1. **Common Crawl integration.** The Common Crawl monthly dumps are a free bulk source of indexed pages. A pre-build step could populate a `web.entity_domains` table with first-seen and last-seen dates per domain. ~4 hours of work, would let the agent skip the Wayback round-trip entirely. Out of scope for the hackathon; high value for v3 of the dataset.
2. **Domain WHOIS history.** Services like SecurityTrails / WhoisXMLAPI sell historical WHOIS feeds — when did the registrant change, did the domain expire and get re-registered. Useful for distinguishing "the entity dissolved" from "the entity rebranded and the domain got squatted." Paid only.
3. **LinkedIn company-presence check.** A LinkedIn page with `<10 employees, last post >2 years ago` is a strong soft signal. LinkedIn bans scraping aggressively; only viable via their paid Marketing Solutions API.
4. **GitHub / open-source activity.** For tech-adjacent recipients (cleantech, biotech, software), an active GitHub org with commits within 6 months of the probe is a strong liveness signal. Easy to check, free API. Worth a 30-minute spike for the cleantech demo zombies (D-Wave, Xanadu, Variation Biotechnologies).
5. **Government-of-Canada link rot inventory.** ISED publishes a quarterly broken-link audit of grant-recipient websites linked from program pages. If the FED program page that funded the recipient now 404s on the recipient link, that *is* a federal-government-side death signal. Out of band but free.
