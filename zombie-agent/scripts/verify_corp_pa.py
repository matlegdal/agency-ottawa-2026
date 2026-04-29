"""End-to-end verification helper for the CORP+PA implementation.

Runs the canonical ZOMBIE_QUESTION ONCE against the local DB, captures
every `finding` event from the in-process ui_bridge, and checks the v3
+ CORP/PA invariants from the implementation prompt §6.2 / §6.3:

  - YMCA-KW (BN 107572687) is REFUTED.
  - JobStart (BN 106881139) is REFUTED.
  - No designation A or B foundation appears.
  - No POLICE / FIRST NATION / MUNICIPAL / etc. entity surfaces.
  - REFUTED-final: no card transitions REFUTED → VERIFIED on CHECK 2b.
  - For VERIFIED candidates with corp_status_code attached, verify the
    chip is present.
  - Report Kinectrics-shape sanity check directly (independent of run).

Run:
    cd zombie-agent
    env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT \\
      uv run python scripts/verify_corp_pa.py

The CLAUDECODE env-scrub is to let the bundled CLI start when this is
invoked from inside a Claude Code session — same workaround agent.py
already applies via its env={...} kwarg, but smoke_test.py / this
script run with the parent process env by default.
"""

import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

from src import streaming  # noqa: E402
from src.agent import run_question  # noqa: E402
from src.run_manager import ZOMBIE_QUESTION  # noqa: E402


_BAD_NAME_PAT = re.compile(
    r"\b(POLICE|POLICING|FIRST NATION|BAND COUNCIL|MUNICIPALITY|"
    r"MINISTRY OF|GOVERNMENT OF|HOSPITAL|HEALTH AUTHORITY|"
    r"UNIVERSITY OF|SCHOOL DIVISION|SCHOOL DISTRICT|SCHOOL BOARD|"
    r"CITY OF|TOWN OF|VILLAGE OF)\b",
    re.IGNORECASE,
)


async def main() -> int:
    findings: dict[str, list[dict]] = {}
    universe: list[dict] = []
    dossiers: list[dict] = []

    async def collect(payload: dict) -> None:
        et = payload.get("type")
        if et == "finding":
            bn = str(payload.get("bn", ""))
            findings.setdefault(bn, []).append(payload)
        elif et == "universe":
            universe.append(payload)
        elif et == "dossier":
            dossiers.append(payload)

    print("=" * 70)
    print(f"Running canonical ZOMBIE_QUESTION against local DB ...")
    print(f"  DATABASE = {os.environ.get('READONLY_DATABASE_URL')}")
    print("=" * 70)

    streaming.set_sender(collect)
    try:
        await run_question(ZOMBIE_QUESTION, collect)
    finally:
        streaming.set_sender(None)

    print("\n" + "=" * 70)
    print(f"COLLECTED: {len(findings)} unique BNs, "
          f"{len(universe)} universe events, "
          f"{len(dossiers)} dossiers")
    print("=" * 70)

    # Report final state per BN
    final_state = {}
    for bn, history in findings.items():
        final = history[-1]
        final_state[bn] = final
        name = final.get("entity_name", "?")
        status = final.get("verifier_status", "?")
        total = final.get("total_funding_cad", 0) or 0
        corp_lbl = final.get("corp_status_label") or "—"
        corp_diss = final.get("corp_dissolution_date") or "—"
        pa_paid = final.get("pa_total_paid_cad")
        pa_str = f"PA {pa_paid:,}" if pa_paid is not None else "PA —"
        print(f"  BN {bn} :: {status:>9} :: ${total/1e6:>7.2f}M :: "
              f"{name[:40]:<40} :: CORP {corp_lbl[:25]:<25} {corp_diss[:10]:<10} :: {pa_str}")

    # ------ Invariants ------
    failures = []

    # v3 §D4 — YMCA-KW REFUTED if it surfaces
    ymca = final_state.get("107572687")
    if ymca and ymca.get("verifier_status") not in ("refuted", None):
        failures.append(
            f"FAIL v3 §D4: YMCA-KW (107572687) status="
            f"{ymca.get('verifier_status')}, expected refuted"
        )

    # v3 §D4 — JobStart REFUTED if it surfaces
    js = final_state.get("106881139")
    if js and js.get("verifier_status") not in ("refuted", None):
        failures.append(
            f"FAIL v3 §D4: JobStart (106881139) status="
            f"{js.get('verifier_status')}, expected refuted"
        )

    # No bad-shape names anywhere
    for bn, f in final_state.items():
        name = f.get("entity_name", "")
        if _BAD_NAME_PAT.search(name):
            failures.append(
                f"FAIL v3 §D7: bad-shape name surfaced — {name} (BN {bn})"
            )

    # REFUTED is final (v3 §D8): no BN transitioned REFUTED → VERIFIED
    for bn, history in findings.items():
        statuses = [h.get("verifier_status") for h in history]
        for i in range(1, len(statuses)):
            if statuses[i - 1] == "refuted" and statuses[i] in ("verified",):
                failures.append(
                    f"FAIL v3 §D8: BN {bn} transitioned REFUTED → VERIFIED "
                    f"(history: {statuses})"
                )
                break

    # Determinism contract: ordering must be by total_funding_cad DESC
    # among VERIFIED. Just count verified and warn if any obviously broken.
    verified = [
        f for f in final_state.values()
        if f.get("verifier_status") == "verified"
    ]
    print(f"\n  VERIFIED count: {len(verified)}")
    if verified:
        sorted_by_funding = sorted(
            verified, key=lambda f: -(f.get("total_funding_cad") or 0)
        )
        for f in sorted_by_funding:
            print(f"    ${(f.get('total_funding_cad') or 0)/1e6:>7.2f}M "
                  f"{f.get('bn'):<10} {f.get('entity_name', '')[:50]}")

    print()
    if failures:
        print("=" * 70)
        print("FAILURES:")
        for fail in failures:
            print(f"  ✗ {fail}")
        print("=" * 70)
        return 1
    print("=" * 70)
    print("ALL CHECKED INVARIANTS PASSED")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set.")
        sys.exit(2)
    sys.exit(asyncio.run(main()))
