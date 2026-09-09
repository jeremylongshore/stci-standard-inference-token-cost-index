# Source Evaluation Rubric

Use this rubric for a dated evidence packet. Prefer official primary sources;
third-party summaries can identify leads but cannot establish provider terms,
units, or API behavior.

## Evidence table

| Fact class | Required evidence | Result |
|---|---|---|
| Source identity | Official provider/API page and owner | verified / disputed |
| Price fields | Official field definitions or pricing table | verified / ambiguous |
| Units | Currency, token denominator, input/output/cache/batch meaning | verified / ambiguous |
| Effective time | Published effective date or retrieval timestamp | dated / missing |
| Authentication | Official auth documentation | public / credentialed / unknown |
| Rate limit | Official API or response guidance | documented / unknown |
| Automation | Terms covering automated access | allowed / prohibited / unclear |
| Redistribution | Terms covering retained or republished data | allowed / prohibited / unclear |
| Provenance | Stable source URL and collection method | complete / incomplete |
| Reliability | Error semantics, pagination, versioning, changelog | acceptable / gap |

Never infer an `allowed` legal result from a missing restriction. `robots.txt`
communicates crawler preference and does not replace terms, license, or counsel.

## Acceptance decision

- **Accept for implementation:** price fields and units are verified, collection
  is technically reproducible, provenance is complete, and legal/security
  boundaries are approved.
- **Research only:** useful source, but one or more approval questions remain.
- **Reject:** access controls would need bypassing, terms prohibit the intended
  use, units cannot be resolved, or provenance cannot be retained.

## Source-tier reconciliation

Read the current STCI methodology, source-universe documentation, risk register,
and collector implementation together. The repository has historically used
inconsistent labels for aggregators; do not repeat an existing label as fact.
Surface the conflict and obtain an explicit policy decision before changing a
tier or adding data that depends on it.

## Profile contents

Record source owner, URLs, evidence timestamps, auth, legal status, response
shape, pagination, units, normalization mapping, required observation fields,
validation bounds, error and retry behavior, monitoring, fixture provenance,
acceptance decision, approver, and unresolved risks. Use the repository's
numbered source-profile template when it is present.
