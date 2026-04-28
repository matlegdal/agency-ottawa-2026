# Zombie Recipients agent — workspace

This is the directory the Claude Agent SDK sees as `cwd`. Anything under
`.claude/skills/` is auto-loaded when its description matches the user's
question.

The methodology, data quirks, and zombie-detection recipe live in
`.claude/skills/`. The orchestrator's system prompt and the verifier
subagent's prompt live in `src/system_prompt.py` and `src/verifier.py`
respectively — not here.
