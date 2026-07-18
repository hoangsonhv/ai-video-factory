# 10 — TECH DEBT (Technical Debt Register)

**Purpose:** A transparent, prioritized ledger of known shortcuts, deferrals, and compromises — what we consciously chose not to do yet, why it's acceptable for now, the risk it carries, and the trigger that will force us to pay it down. Visible debt is manageable debt.

**Owner:** Technical Lead.

**When to update:** When debt is incurred (a deliberate shortcut is taken), paid down (resolved), or re-assessed (risk changes). Every debt item should trace to an ADR, a sprint, or a backlog entry.

---

## Sections

1. How We Track Debt
2. Debt Item Format
3. Register
4. Deferred-by-Design (ADR-backed) vs. Incidental Debt
5. Paid-Down Log

---

## 1. How We Track Debt

- Each item has an ID (`TD-XXX`), a severity, an owner, an incurred date, a rationale, a risk, and a **payoff trigger** (the condition under which it must be addressed).
- Severity: `High` (risk to correctness/architecture), `Medium` (maintainability/perf), `Low` (cosmetic/convenience).
- Debt that is *deliberate and ADR-backed* is distinguished from *incidental* debt (accidental shortcuts).
- Items reference the relevant ADR/sprint/backlog entry.

## 2. Debt Item Format

```
### TD-XXX — <Title>
- Severity:
- Incurred: <date / sprint>
- Owner:
- Category: deferred-by-design | incidental
- Description:
- Rationale (why acceptable now):
- Risk if unaddressed:
- Payoff trigger:
- Related: <ADR / sprint / backlog>
```

## 3. Register

### TD-001 — No automated packaging/release pipeline yet
- **Severity:** Medium
- **Incurred:** Sprint 000
- **Owner:** Technical Lead
- **Category:** incidental
- **Description:** The project runs from an editable install; there is no built, versioned distributable or release automation.
- **Rationale:** Foundation and pipeline stages take priority; local dev install suffices pre-1.0.
- **Risk if unaddressed:** Harder, error-prone 1.0 release; inconsistent environments.
- **Payoff trigger:** Sprint 020 (v1.0 release hardening).
- **Related:** Roadmap Sprint 020.

### TD-002 — SQLite single-writer limits future concurrency
- **Severity:** Low (now), Medium (post-1.0)
- **Incurred:** Sprint 000
- **Owner:** Technical Lead
- **Category:** deferred-by-design
- **Description:** SQLite supports the single-machine, single-writer MVP but not concurrent multi-project writers.
- **Rationale:** ADR-003 — zero-ops, transactional, ideal for MVP; entity/ORM separation keeps a swap contained.
- **Risk if unaddressed:** Blocks parallel multi-project execution at scale.
- **Payoff trigger:** When concurrent multi-project runs or remote workers are scheduled (post-1.0).
- **Related:** ADR-003, Backlog (post-1.0 scale).

### TD-003 — No cost tracking/metering for provider calls
- **Severity:** Medium
- **Incurred:** Sprint 000
- **Owner:** Technical Lead
- **Category:** incidental
- **Description:** Provider usage/cost is not yet recorded per run/stage.
- **Rationale:** Correct pipeline behavior precedes cost analytics.
- **Risk if unaddressed:** No visibility into per-video cost; hard to optimize spend.
- **Payoff trigger:** Sprint 019 (cost/perf logging).
- **Related:** Roadmap Sprint 019.

### TD-004 — Prompt A/B evaluation is manual (golden tests only)
- **Severity:** Low
- **Incurred:** Sprint 000
- **Owner:** Technical Lead
- **Category:** deferred-by-design
- **Description:** Prompt quality is guarded by structural golden tests, not automated quality scoring.
- **Rationale:** Structural validation is sufficient for MVP; automated quality scoring is heavy.
- **Risk if unaddressed:** Slower prompt iteration; subjective quality regressions.
- **Payoff trigger:** When prompt iteration becomes a bottleneck (post-1.0).
- **Related:** `06_PROMPT_RULES.md`, ADR-005.

### TD-005 — No retry jitter/circuit-breaker beyond basic backoff
- **Severity:** Medium
- **Incurred:** Sprint 000 (anticipated at Sprint 007)
- **Owner:** Technical Lead
- **Category:** incidental
- **Description:** The provider decorator stack starts with retry/backoff + rate limiting; jittered backoff and circuit breaking are not yet implemented.
- **Rationale:** Basic resilience covers MVP failure modes; advanced patterns add complexity.
- **Risk if unaddressed:** Thundering-herd retries against a degraded provider.
- **Payoff trigger:** Sprint 016 (resilience hardening) if observed in practice.
- **Related:** ADR-005, Roadmap Sprint 016.

### TD-006 — Single filesystem asset store (no remote/object storage)
- **Severity:** Low
- **Incurred:** Sprint 000
- **Owner:** Technical Lead
- **Category:** deferred-by-design
- **Description:** `AssetStorage` writes to the local filesystem only.
- **Rationale:** MVP is single-machine; local storage is simplest and behind a port.
- **Risk if unaddressed:** Blocks distributed/remote execution.
- **Payoff trigger:** When remote workers or cloud storage are scheduled (post-1.0).
- **Related:** Architecture Document §2.3 (AssetStorage port).

## 4. Deferred-by-Design vs. Incidental Debt

- **Deferred-by-design** items (TD-002, TD-004, TD-006) are conscious scope boundaries backed by ADRs/non-goals. They are acceptable indefinitely until their payoff trigger fires.
- **Incidental** items (TD-001, TD-003, TD-005) are shortcuts to be paid down within the roadmap; each has a scheduled sprint trigger.

Keeping these categories distinct prevents "non-goals" from being mistaken for neglect.

## 5. Paid-Down Log

> Move items here when resolved. Newest first.

_(none yet — project at Sprint 000)_

### Example paid-down entry (format to follow)
```
### TD-003 — Cost tracking — PAID DOWN
- Resolved: Sprint 019
- Resolution: Per-stage duration + provider cost recorded to logs and run summary.
- Verified by: cost fields present in structured logs; `factory status` shows per-run cost.
```
