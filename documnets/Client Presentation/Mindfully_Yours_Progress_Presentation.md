# Mindfully Yours
## AI Companion — Progress Overview
### Prepared by OpenXcell Technolabs Pvt. Ltd.

---

## What We're Building

Mindfully Yours is an AI companion people can talk to — by voice, text, or an on-screen avatar — about how they're feeling.

It feels like a warm, everyday conversation. Underneath, on every single message, it is quietly checking one thing: **is this person okay, or do they need real help right now?**

---

## Three Rules We Never Break

**1. Grounded, not invented.**
The AI never makes up mental-health advice. It only ever uses what your clinical team has actually written and approved.

**2. Safety is separate from the AI.**
A simple, independent alarm system checks every message for danger — this system cannot be fooled, skipped, or turned off by anything the AI decides.

**3. It should feel human, never like a test.**
No quizzes, no visible scoring. The app quietly understands how serious things are just from natural conversation.

---

## The Big Picture — How the System Is Built

```
 ┌─────────────────────────────┐
 │        MOBILE & WEB APP       │   what the person actually sees and talks to
 └───────────────┬───────────────┘
                 │
 ┌───────────────▼───────────────┐
 │         MAIN BACKEND           │   logins, bookings, everyday app features
 └───────────────┬───────────────┘
                 │
 ┌───────────────▼───────────────┐
 │        AI COMPANION ENGINE     │   the conversation + safety brain (kept separate on purpose)
 └───────────────┬───────────────┘
                 │
 ┌───────────────▼───────────────┐
 │      SECURE DATA STORAGE       │   everything saved safely, in India, as required by law
 └─────────────────────────────────┘
```

The AI Companion Engine is kept as its **own separate piece**, deliberately. That way, nothing happening anywhere else in the app can ever interfere with the safety checks.

---

## How One Conversation Works

```
 Person sends a message
          │
          ▼
 "Have we already answered exactly this before?"  →  instant reply if yes
          │  (no)
          ▼
 SAFETY CHECK  —  always runs, no exceptions, cannot be skipped
          │
          ▼
 Quietly understand what's really being said
          │
          ▼
 Decide: keep chatting normally  /  suggest a professional  /  alert a human immediately
          │
          ▼
 AI writes a warm, natural reply — using only approved material
          │
          ▼
 Reply is sent back (voice, text, or avatar) — and everything is safely logged
```

The safety check step **never gets skipped** — not for speed, not for cost, not ever.

---

## Organizing Our Knowledge — 3 Simple Categories

Everything your clinical team has given us gets sorted into exactly one of three groups:

| Category | In plain words |
|---|---|
| **Teach the tone** | Example conversations that show the AI *how* to talk — warm, calm, natural |
| **Find the right answer** | Real information the AI searches through to understand the person and offer real help |
| **Follow the rules** | Fixed decision rules (like "these signs mean this level of concern") the system checks directly — no guessing |

This keeps everything fast, accurate, and easy to update as your team sends us more material.

---

## What We've Built So Far

| Area | Status |
|---|---|
| Full project understanding & documentation | **Complete** |
| Organizing all knowledge base material received | **Complete** |
| Turning your spreadsheets & documents into usable data | **Complete** |
| Danger-phrase detection (the core safety check) | **Complete** |
| Secure data storage design | **Complete** |
| Full conversation flow — structure & sequencing | **Complete** |
| Silently understanding what a person means | **In progress** |
| Deciding severity automatically | **In progress** |
| Connecting to the AI voice/language provider | **In progress** |
| Full end-to-end testing | **Not started yet** |

---

## A Recent Milestone

Your team's clinical content team recently shared a large batch of working documents — question banks, conversation examples, and self-help materials.

We reviewed every single file and found:
- **Real, ready-to-use self-help tools** (a complete coping-skills workbook) we didn't have before
- A few **small data-quality issues** already cleaned up
- A short list of **simple questions for your clinical team**, to make sure a few of your documents are read exactly the way you intended

---

## What's Next

1. Finalize the connection to our AI voice/language provider
2. Get quick input from your clinical team on a short question list
3. Build the remaining "understanding" logic
4. Full testing before anything goes live

---

## Thank You

**Mindfully Yours — AI Companion**
Prepared by OpenXcell Technolabs Pvt. Ltd.
