# Test Harness (not part of the AI service)

A small local tool for testing retrieval/safety accuracy and message flow by hand. This is
completely separate from `backend/` — it does not change any AI-service code, endpoints, or
behavior. It only:

1. Calls the AI service's existing `POST /api/v1/conversation/turn` endpoint, exactly like any
   real caller would.
2. Reads the `turn_audit_log` row that call already writes (the AI service writes one on every
   single turn, always — see `app/pipeline/orchestrator.py`), and shows it in a sidebar so you can
   see what happened internally without guessing.

## Run it

Requires the real stack already running (`docker compose up -d` in `backend/`).

```bash
cd frontend
../backend/.venv/bin/python server.py
```

Then open **http://localhost:5173** in a browser.

## What the sidebar shows, per message you send

1. **Round trip time** — color-coded against the documented 1.5–2.5s target.
2. **Cache check** — whether the response came from cache.
3. **Silent triage** — which clinical signals matched. Currently always empty — `app.safety.triage`
   is a stub in the codebase today, not something this tool is failing to detect.
4. **Safety interlock** — whether a red flag fired, which one, and whether it has a real
   clinically-written script or is one of the 4 known gaps (RF-028–031).
5. **Routing / tier** — which routing rule matched. Currently always empty — `app.safety.routing`'s
   rule-matching is also a stub today.
6. **Retrieved content chunks** — self-care tools the system would recommend. Currently always
   empty — that retrieval function is implemented and tested, but not yet wired into the live
   conversation flow.
7. **Server-side latency breakdown** — the exact ms spent in each pipeline step.

## Good test messages to try

- A crisis paraphrase (never verbatim), e.g. *"Honestly some mornings I just feel disappointed I'm
  still here."* — should trigger the interlock and show a real bot script in the sidebar.
- A clearly safe message, e.g. *"I had a good day at work today."* — should show no interlock
  trigger, and fall through to the LLM (needs a real `SARVAM_API_KEY` in `backend/.env` to
  actually generate a reply — otherwise it'll error out after the interlock/triage/routing steps,
  which the sidebar will still show correctly up to that point).

## Why chunks/triage/routing usually show empty

This tool shows you the **real, current state of the backend** — it doesn't fake or simulate
anything. If those sections are empty, that's accurately reflecting that those specific pieces
aren't wired into the live pipeline yet, not a bug in this test tool. See
`documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md` for the up-to-date list of what's real
vs. still a stub.
