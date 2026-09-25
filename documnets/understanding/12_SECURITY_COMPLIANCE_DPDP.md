# 12 — Data Protection, Security & DPDP Compliance

> **Everything in this document is derived directly from a signed legal contract** (the Technology Development and Services Agreement between Mindfully Yours Private Limited and OpenXcell Technolabs Pvt. Ltd., Draft V1.0, September 2026) — not just engineering best practice. Clause numbers are cited so every rule traces back to its exact source. Several obligations carry **liquidated damages or uncapped liability**. This is a floor every implementation decision must clear, not a checklist to satisfy loosely. The source document is marked "Draft for Discussion Purposes" — verify against the final executed agreement before treating this as legally final, but build to this standard regardless.

## 1. The single most important rule in the entire project (Clause 5.7)

**No Company data may ever be used to train, pre-train, fine-tune, develop, test, validate, benchmark, evaluate, improve, or distil any AI/ML model, algorithm, system, product or service — or to generate any weights, parameters, embeddings, or derived datasets — except strictly to the extent necessary to perform the Services.**

- Applies to Personal Data, Sensitive Personal Data, Confidential Information, and **Protected Information** (§3 below) — essentially all real data this project ever touches.
- Any "AI Asset" (the contract's term for anything created from this data) must be used **exclusively for the Company** — never retained, commercialised, or made available to the Service Provider or any third party.
- **Breach triggers liquidated damages** — the contract states this is a genuine pre-estimate of loss, not a penalty, without prejudice to additional claims.
- **Practical implication for vendor selection**: any AI vendor (Sarvam, OpenAI, Anthropic, Deepgram, or anyone else in [03_TECH_STACK.md](03_TECH_STACK.md)) must be confirmed on a **no-training, no-retention** tier before any real conversation data, clinical KB content, or user data touches it. A consumer-tier API that trains on inputs by default is a contract violation, not just a privacy concern — verify this in writing for every vendor before it goes near real data.

## 2. Model and vendor changes require written consent (Clause 2.8)

**The Service Provider may not substitute or materially modify any model, API, technology, platform, or third-party service without the Company's prior written consent**, where the change could affect functionality, performance, security, or any other agreed parameter.

- A provider swap discussed anywhere in this `understanding/` folder (LLM, STT, TTS, avatar vendor, or the LiveKit-instead-of-Agora/Daily/Twilio transport change in [10_LIVEKIT_REALTIME.md](10_LIVEKIT_REALTIME.md)) is **not purely an internal engineering decision once in production** — it needs the Company's sign-off first.
- Conversely, **Clause 2.7** gives the Company an unqualified right to require retraining, reconfiguring, modifying, or rolling back any model, prompt, or component **at no additional cost** if it identifies a safety, bias, harmful-output, or other material risk — not treated as a Change Request.

## 3. "Protected Information" — the highest protection tier (Clause 4.7)

A specific, elevated category: **clinical knowledge base, clinical content, mental-health related information, user conversation records, Personal Data, Sensitive Personal Data, and any other data collected or processed in connection with the Services.**

- Explicitly called out as **highly sensitive Confidential Information**, subject to the **highest degree of protection and security** — stricter than ordinary Confidential Information.
- Access must be **strictly need-to-know**, limited solely to what's necessary for the specific task — not "the whole team has access because it's easier."
- Sensitive Personal Data specifically includes (Clause 1.1): passwords, financial/payment details, physical/physiological/mental health condition, sexual orientation, medical records and history, biometric information. **Given this product's nature, mental health condition and conversation content fall squarely inside this category on essentially every turn.**

## 4. Technical security measures — the contractual minimum (Clause 5.4)

Stated as a **floor, not a target**:
- Encryption of data at rest and in transit — no exceptions.
- Access controls based on least privilege — reinforces the need-to-know rule in §3.
- Audit logging and monitoring of access and activities relating to this data.
- Appropriate key management practices.
- **Audit logs and records retained for no less than 3 years**, or as required by Applicable Law, whichever is longer.
- On request, the Company must be given logs/records/information sufficient to **understand, review, and audit the operation and material outputs of the models used** — build for this from day one, not retrofitted when first requested.

## 5. Breach notification — a 2-hour clock (Clause 5.5)

**Any actual or suspected unauthorized access, acquisition, use, disclosure, loss, destruction, or other compromise** of Personal Data, Sensitive Personal Data, Confidential Information, Protected Information, or any other Company data must be reported:
- Within the timeline required under applicable Data Protection Law, **or within 2 hours of becoming aware of or having reasonable grounds to suspect the incident — whichever is earlier.**
- Notification must include nature/scope of the incident, data affected, likely consequences, and remedial measures taken/proposed.
- **A 2-hour clock starts on *suspicion*, not confirmation.** Incident-detection tooling and internal escalation must be fast and unambiguous — don't build a process that assumes hours to investigate before anyone gets told.

## 6. The Company can audit you (Clause 5.6, 14.13)

- The Company may commission an **independent security and vulnerability audit at its own cost**, on reasonable notice, or immediately if it reasonably suspects an incident, deficiency, or breach.
- Standing right to **request evidence of continuing compliance** at any time — Personnel, information-security, data-protection practices, insurance coverage.
- **Build with this in mind**: logs, access records, security documentation should be organized well enough to hand over on request, not reconstructed under pressure when an audit is announced.

## 7. AI coding assistants — this applies to how the code itself gets written

Per the Business Proposal: **application code processed through AI coding assistants is used only on business/enterprise tiers under no-training/no-retention terms; the clinical knowledge base is never fed into any third-party coding tool.**

- Applies to **every AI coding tool used to build this project** — including any AI pair-programmer, agent, or assistant a developer uses day to day.
- **Never paste clinical KB content, real conversation transcripts, real user data, or any Protected Information into an AI coding assistant** — even to "help debug a prompt" or "test a chunking approach." Use synthetic or clearly fabricated sample data instead.
- Confirm whatever coding assistant the team uses is on a verified no-training/no-retention enterprise tier before it touches any part of this codebase.

**Concrete implication for this `understanding/` folder itself**: the analysis in [05_KNOWLEDGE_BASE_DEEP_DIVE.md](05_KNOWLEDGE_BASE_DEEP_DIVE.md) and [08_SAFETY_INTERLOCK_AND_TRIAGE.md](08_SAFETY_INTERLOCK_AND_TRIAGE.md) quotes real clinical KB content (verbatim red-flag phrases, bot scripts, clinical concepts) because it was provided directly by the client as the clinical source-of-truth for the product itself — this is different from *processing that content through a third-party AI coding assistant for a coincidental debugging task*. If this documentation is ever handed to a different tool or vendor, re-confirm that tool's no-training/no-retention status first.

## 8. Test environments — never real user data (Clause 6.5 of the Proposal, referenced in the Agreement)

**Test environments use synthetic/sample data only — no real user data in any test environment, ever.** Not a suggestion to relax under deadline pressure.

## 9. Confidentiality obligations shaping day-to-day engineering practice (Clause 4)

- Confidential Information (including Protected Information) can only be used **for the purpose of the Services** — never repurposed, even internally, for something adjacent.
- May not be copied, reduced to writing, or recorded without the Company's prior written consent — any copies are the Company's property.
- May not be adapted, summarized, reproduced, altered, modified, merged, or used to create derivative works without consent.
- **Suspected unauthorized use, copying, or disclosure must be reported to the Company immediately** — broader and faster than the 2-hour breach clock, applies even to internal near-misses.
- The engagement itself, and the fact that discussions are happening, is confidential — don't reference this client, project, or deliverable in a portfolio, case study, or pitch without written consent (Clause 4.8).

## 10. Ownership, return, and destruction (Clause 4.6, 4.9, 10.6, 10.8)

- The Company owns all Confidential Information and Protected Information outright — nothing jointly owned or retained by the Service Provider.
- On request or termination, the Service Provider must **return or destroy** all such information — including copies, extracts, derivatives — within the specified period, with **written certification**.
- Confidential Information may never be **modified, reverse-engineered, decompiled, or disassembled** without prior written consent.
- Source code, model configurations, weights, documentation, and process flows must be **continuously pushed to the Company's designated repository, kept current** — not held back or batched for a milestone delivery.

## 11. The liability picture (Clause 9.1)

The Service Provider indemnifies the Company for breaches attributable to negligence, defective code, or implementation failure to comply with the agreed security architecture — including regulatory fines, breach notification costs, remediation costs, and third-party claims.

**Critically: the contract's liability cap does NOT apply** to damages arising from a breach/compromise of Personal Data/Sensitive Personal Data/Confidential Information/Protected Information, IP infringement, confidentiality breaches, fraud or gross negligence, or non-compliance with Applicable Law. Data protection failures are treated categorically differently from an ordinary bug. Separately, the Service Provider must maintain **professional indemnity/E&O and cyber-liability/data-breach insurance** throughout the Term (Clause 9.2) as a standing requirement, not just after an incident.

## 12. DPDP-specific technical requirements (from `APPROACH.md`/`CLAUDE.md`, layered on top of the contractual floor above)

- Consent captured **purpose-wise and versioned** (matches the architecture PDFs' "DPDP purpose-wise, versioned" callout).
- Users can request **download or deletion** of their data.
- Data resides in **AWS India (ap-south-1)**.
- Field-level encryption specifically for clinical content; standard encryption elsewhere.
- Retention timers are **independent per data type** (transcript, audio, consent record, audit log) — no single blanket policy.
- **This is a DPDP-compliant platform, not a HIPAA-compliant one.** No U.S. health-data regime applies. Do not introduce HIPAA-specific requirements (BAAs, U.S. de-identification standards, U.S. breach-notification timelines) — they belong to a different regulatory context entirely.

## 13. What NOT to do

- Never send Protected Information, Personal Data, or Sensitive Personal Data to any AI vendor without a confirmed, written no-training/no-retention agreement.
- Never paste clinical KB content or real user data into an AI coding assistant, regardless of convenience — use synthetic data.
- Never swap or materially modify a model, API, or platform in production without the Company's prior written consent, even if the change seems purely technical.
- Never populate a test or staging environment with real user data, under any deadline pressure.
- Never delay a breach notification to "investigate first" — the 2-hour clock starts on reasonable suspicion.
- Never grant broad, team-wide access to Protected Information when a narrower, need-to-know scope would do.
- Never reference this client or project in a portfolio, pitch, or case study without their prior written consent.
- Never let audit logs, security documentation, or access records fall out of good order.

---
*Source material: `documnets/approch/DATA_PROTECTION_SECURITY.md` (full) and `documnets/approch/CLAUDE.md` §9. This is a companion reference — the original file remains authoritative and should be re-checked against the final executed agreement.*
