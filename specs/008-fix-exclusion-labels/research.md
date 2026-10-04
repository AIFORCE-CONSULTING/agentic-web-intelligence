# Research: Correct Report Exclusion Labels

## Decision: Keep exclusion derivation in `AgenticResearchStore.report_exclusions`

**Rationale:** Existing report packages already ask `AgenticResearchStore` for
excluded sources before saving an immutable report package. ADR 0014 and ADR
0016 place final-report package construction and report exclusions in the
platform, not the model. Keeping the logic here preserves one owner and avoids a
second reporting path.

**Alternatives considered:**

- Add UI-side mapping from candidate preflight status to display labels. Rejected
  because the report endpoint should carry the durable operator-facing reason.
- Ask the local model to explain exclusions. Rejected because exclusion reasons
  are platform facts and the model must not infer authority, trust, or workflow
  outcomes.
- Add a new report-exclusion service. Rejected because the existing store method
  already owns exclusion creation and persistence.

## Decision: Use stored source outcomes in priority order

**Rationale:** The reason should reflect the earliest decisive platform outcome
that prevented a source from contributing to report findings. A local trust
block or access failure happens before summary and topic relevance, so those
must not fall through to "not relevant" wording.

**Priority order:**

1. Local trust-policy block.
2. Human review required without current acceptance.
3. Publisher access denied when the stored preflight reason clearly indicates
   access rejection such as HTTP 403.
4. Unreachable or no usable evidence captured.
5. Summary failed.
6. Evidence insufficient.
7. Not relevant to planned topics, only after usable evidence and summary exist.

**Alternatives considered:**

- Treat all failed preflight as unreachable. Rejected because trust-policy block
  and publisher access denial need different operator interpretation.
- Treat HTTP 403 as blocked by trust policy. Rejected because publisher access
  denial is not the same decision as a local trust-policy block.

## Decision: Preserve existing report inclusion behavior

**Rationale:** The bug is the explanation attached to excluded sources. The same
sources should be included in report findings as before, because eligibility,
summary creation, and topic relevance are separate platform decisions.

**Alternatives considered:**

- Re-run extraction or relevance when an exclusion looks suspicious. Rejected as
  outside scope and likely to create new workflow behavior.
- Recompute historical report exclusions at read time. Rejected because stored
  reports are immutable snapshots.

## Decision: No ADR required

**Rationale:** The change does not create or move an architectural boundary. It
refines an existing deterministic reason derivation inside the stored report
package. ADR 0014 and ADR 0016 already describe platform-owned report packages
and report exclusions.

**Alternatives considered:**

- Amend ADR 0014. Deferred unless implementation reveals a changed boundary.
