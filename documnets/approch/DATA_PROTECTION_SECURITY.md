# Mindfully Yours — Data Protection & Security Rules for AI Development

Companion reference to `APPROACH.md`, `CLAUDE.md`, `LATENCY.md`, `INGESTION.md`, and `LIVEKIT.md`. Unlike those files, **everything below is derived directly from a signed legal contract** (the Technology Development and Services Agreement between Mindfully Yours Private Limited and OpenXcell Technolabs Pvt. Ltd., September 2026), not just engineering best practice. Clause numbers are cited so any rule here can be traced back to its exact contractual source. Several of these obligations carry **liquidated damages** or **uncapped liability** — this is not a "nice to have" checklist.

---

## 1. The single most important rule in this entire file (Clause 5.7)

**No Company data may ever be used to train, pre-train, fine-tune, develop, test, validate, benchmark, evaluate, improve, or distil any AI/ML model, algorithm, system, product or service — or to generate any weights, parameters, embeddings, or derived datasets — except strictly to the extent necessary to perform the Services.**

- This applies to Personal Data, Sensitive Personal Data, Confidential Information, and **Protected Information** (defined in Section 3 below) — i.e., essentially all real data this project ever touches.
- Any "AI Asset" (the contract's term for anything created from this data) must be used **exclusively for the Company** — never retained, commercialised, or made available to the Service Provider or any third party.
- **Breach of this clause triggers liquidated damages** — the contract explicitly states this is a genuine pre-estimate of loss, not a penalty, and is without prejudice to additional claims.
- **Practical implication for vendor selection**: any AI vendor (Sarvam, OpenAI, Anthropic, or anyone else) must be confirmed on a **no-training, no-retention** tier before any real conversation data, clinical KB content, or user data touches it. A consumer-tier API that trains on inputs by default is a contract violation, not just a privacy concern — verify this in writing for every vendor before it goes near real data.

---

## 2. Model and vendor changes require written consent (Clause 2.8)

**The Service Provider may not substitute or materially modify any model, API, technology, platform, or third-party service without the Company's prior written consent**, where the change could affect functionality, performance, security, or any other agreed parameter.

- This means a provider swap discussed in `APPROACH.md`/`LIVEKIT.md` (e.g. changing the LLM, STT, or RTC vendor) is not purely an internal engineering decision once in production — it needs the Company's sign-off first.
- Conversely, **Clause 2.7** gives the Company an unqualified right to require retraining, reconfiguring, modifying, or rolling back any model, prompt, or component **at no additional cost** if it identifies a safety, bias, harmful-output, or other material risk — this is not treated as a Change Request.

---

## 3. What "Protected Information" means, and why it gets the highest protection tier (Clause 4.7)

The contract defines a specific, elevated category: **clinical knowledge base, clinical content, mental-health related information, user conversation records, Personal Data, Sensitive Personal Data, and any other data collected or processed in connection with the Services.**

- This is explicitly called out as **highly sensitive Confidential Information**, subject to the **highest degree of protection and security** under the agreement — a stricter standard than ordinary Confidential Information.
- Access must be **strictly need-to-know**, limited solely to what's necessary to perform the specific task at hand — not "the whole team has access because it's easier."
- Sensitive Personal Data specifically includes (per Clause 1.1): passwords, financial/payment details, physical/physiological/mental health condition, sexual orientation, medical records and history, and biometric information. Given this product's nature, mental health condition and conversation content fall squarely inside this category on essentially every turn.

---

## 4. Technical security measures — the contractual minimum (Clause 5.4)

These are stated as a **floor, not a target** — "at a minimum" is the contract's own language:

- **Encryption of data at rest and in transit** — no exceptions.
- **Access controls based on the principle of least privilege** — this directly reinforces the need-to-know rule in Section 3.
- **Audit logging and monitoring of access and activities** relating to this data.
- **Appropriate key management practices.**
- **Audit logs and records must be retained for no less than 3 years**, or as required by Applicable Law, whichever is longer.
- On request, the Company must be given logs, records, and information sufficient to **understand, review, and audit the operation and material outputs of the models used** — build for this from day one, not retrofitted when first requested.

---

## 5. Breach notification — a 2-hour clock, not a "best effort" window (Clause 5.5)

**Any actual or suspected unauthorized access, acquisition, use, disclosure, loss, destruction, or other compromise** of Personal Data, Sensitive Personal Data, Confidential Information, Protected Information, or any other Company data must be reported:

- Within the timeline required under applicable Data Protection Law, **or within 2 hours of becoming aware of or having reasonable grounds to suspect the incident — whichever is earlier.**
- The notification must include the nature and scope of the incident, the data affected, likely consequences, and remedial measures taken or proposed.
- This means incident-detection tooling and an internal escalation path need to be fast and unambiguous — a 2-hour clock starts on *suspicion*, not confirmation. Don't build a process that assumes hours to investigate before anyone gets told.

---

## 6. The Company can audit you — expect it, don't resist it (Clause 5.6, 14.13)

- The Company may commission an **independent security and vulnerability audit at its own cost**, on reasonable notice, or immediately if it reasonably suspects an incident, deficiency, or breach.
- The Company also has an ongoing, standing right to **request evidence of continuing compliance** at any time — Personnel practices, information-security practices, data-protection practices, insurance coverage.
- **Build with this in mind**: logs, access records, and security documentation should be organized well enough to hand over on request, not reconstructed under pressure when an audit is announced.

---

## 7. AI coding assistants — this applies to how the code itself gets written, not just the product

The Business Proposal is explicit: **application code processed through AI coding assistants is used only on business/enterprise tiers under no-training/no-retention terms; the clinical knowledge base is never fed into any third-party coding tool.**

- This rule applies to **every AI coding tool used to build this project** — including any AI pair-programmer, agent, or assistant a developer uses day to day.
- **Never paste clinical knowledge base content, real conversation transcripts, real user data, or any Protected Information into an AI coding assistant** — even to "help debug a prompt" or "test a chunking approach." Use synthetic or clearly fabricated sample data for that instead.
- Confirm whatever coding assistant the team uses is on a verified no-training/no-retention enterprise tier before it touches any part of this codebase, for the same reason Section 1 applies to model vendors.

---

## 8. Test environments — never real user data (Clause 6.5 of the Proposal, referenced in the Agreement)

**Test environments use synthetic/sample data only — no real user data in any test environment, ever.** This isn't a suggestion to be relaxed under deadline pressure; it's a stated testing standard in the governing documents.

---

## 9. Confidentiality obligations that shape day-to-day engineering practice (Clause 4)

- Confidential Information (which includes Protected Information) can only be used **for the purpose of the Services** — never repurposed, even internally, for something adjacent.
- It may not be copied, reduced to writing, or recorded without the Company's prior written consent — and any copies that do exist are the Company's property, not the Service Provider's.
- It may not be adapted, summarized, reproduced, altered, modified, merged, or used to create derivative works without consent.
- **Suspected unauthorized use, copying, or disclosure must be reported to the Company immediately** — this is a broader, faster-triggering obligation than the formal 2-hour breach clock in Section 5, and applies even to internal near-misses.
- The engagement itself, and the fact that discussions are happening, is confidential — don't reference this client, this project, or any deliverable built for them in a portfolio, case study, or pitch without written consent (Clause 4.8).

---

## 10. Ownership, return, and destruction (Clause 4.6, 4.9, 10.6, 10.8)

- The Company owns all Confidential Information and Protected Information outright — nothing here is jointly owned or Service-Provider-retained.
- On request, or on termination, the Service Provider must **return or destroy** all such information — including all copies, extracts, and derivatives — within the period specified, and **provide written certification** confirming this was done.
- Confidential Information may never be **modified, reverse-engineered, decompiled, or disassembled** without prior written consent.
- Throughout the Term, source code, model configurations, weights, documentation, and process flows must be **continuously pushed to the Company's designated repository, kept current** — not held back or batched for a milestone delivery. Treat the Company's repo as the real source of truth, updated continuously, not a snapshot handed over occasionally.

---

## 11. What happens if this goes wrong — the liability picture (Clause 9.1)

The Service Provider indemnifies the Company for breaches attributable to negligence, defective code, or implementation failure to comply with the agreed security architecture — including **regulatory fines, breach notification costs, remediation costs, and third-party claims.**

**Critically: the contract's liability cap does not apply to** — meaning there is no ceiling on — damages arising from a breach or compromise of Personal Data/Sensitive Personal Data/Confidential Information/Protected Information, IP infringement, confidentiality breaches, fraud or gross negligence, or non-compliance with Applicable Law. This is the clearest possible signal that data protection failures are treated categorically differently from an ordinary bug.

Separately, the Service Provider must maintain **professional indemnity/errors-and-omissions insurance and cyber-liability/data-breach insurance** throughout the Term (Clause 9.2) — this is a standing business requirement, not something to arrange only if an incident occurs.

---

## 12. What NOT to do

- **Never send Protected Information, Personal Data, or Sensitive Personal Data to any AI vendor without a confirmed, written no-training/no-retention agreement** — this is Clause 5.7 and carries liquidated damages, not just reputational risk.
- **Never paste clinical KB content or real user data into an AI coding assistant**, regardless of how convenient it would be for debugging — use synthetic data instead.
- **Never swap or materially modify a model, API, or platform in production without the Company's prior written consent**, even if the change seems purely technical.
- **Never populate a test or staging environment with real user data**, under any deadline pressure.
- **Never delay a breach notification to "investigate first"** — the 2-hour clock starts on reasonable suspicion, not confirmation.
- **Never grant broad, team-wide access to Protected Information** when a narrower, need-to-know scope would do.
- **Never reference this client or project in a portfolio, pitch, or case study** without their prior written consent.
- **Never let audit logs, security documentation, or access records fall out of good order** — assume an audit request can come at any time, per Clause 14.13.

---

*Companion file to `APPROACH.md`, `CLAUDE.md`, `LATENCY.md`, `INGESTION.md`, and `LIVEKIT.md` — derived directly from the Technology Development and Services Agreement between Mindfully Yours Private Limited and OpenXcell Technolabs Pvt. Ltd. (Draft V1.0, September 16, 2026). This file should be reviewed against the final executed agreement before relying on it as authoritative, since the version reviewed here is marked "Draft for Discussion Purposes." Keep all six files in sync if any clause or engineering decision changes.*
