# STCI Collector Contract

Ground implementation in the repository's current `BaseSource`, observation
schema, pipeline, and tests. Do not paste a generic class stub that cannot run.

## Required mapping

Each normalized observation must satisfy the current schema, including:

- deterministic observation ID;
- schema version, provider, model ID, and display name;
- numeric non-negative input and output rates in USD per one million tokens;
- effective date and UTC collection timestamp;
- stable source URL, approved source tier, currency, and collection method;
- only schema-approved optional properties.

Treat caching, batch, image, audio, per-request, and provider-specific charges as
distinct dimensions. Do not fold them into input/output token rates unless the
approved methodology defines the transformation.

## Implementation rules

1. Reuse the current base class and request/session conventions.
2. Set a finite timeout and preserve HTTP status/error context without tokens.
3. Validate the response envelope before iterating records.
4. Convert decimal price strings deliberately; reject non-finite and negative
   values rather than silently coercing them.
5. Preserve provider model identity and deterministic normalization.
6. Fail closed on response-shape or unit drift. Count and report rejected rows.
7. Keep secrets in the approved runtime secret mechanism, never fixtures.
8. Make network tests mocked and deterministic.

## Test matrix

| Case | Expected result |
|---|---|
| Valid representative response | Exact schema-valid observations |
| Missing price field | Documented skip or explicit validation failure |
| Zero price | Behavior matches approved inclusion policy |
| Invalid numeric value | Rejected without crashing the full run |
| Negative or non-finite value | Rejected |
| Empty response | Successful empty result or explicit source failure, by contract |
| Auth failure | Sanitized error; no retry loop |
| Rate limit | Honor official retry guidance and stop at the retry bound |
| Timeout/server error | Bounded failure with source context |
| Schema field change | Fail closed and retain a redacted diagnostic sample |

Run focused unit tests, the full Python suite, and the fixture dry-run. A live
collection is a separate approved operation because it uses external services
and may write raw or normalized data.
