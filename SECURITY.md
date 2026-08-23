# Security

## Threat model

See [docs/DESIGN.md §8](docs/DESIGN.md#8-threat-model) for the full threat model: prompt injection via observed on-chain state, state changes without a genuinely successful read, premature fund reclaim, authorization boundaries on every write method, and unbounded-cost defenses.

## Scope

This contract holds real escrowed GEN on behalf of funders and grantees. There are no admin keys, no upgradeability, and no privileged third-party role — `register_tranche` and `withdraw_unallocated` are funder-only for the funder's own program; `reclaim_stale_tranche` is funder-only and time-gated; `verify_milestone` is funder-or-grantee-only for their own tranche. No party other than a program's own funder and grantee can affect that program's funds or verification outcomes.

Fund movement (`emit_transfer`) only ever follows a `SATISFIED` outcome independently agreed by GenLayer consensus, or an explicit funder-initiated `withdraw_unallocated`/`reclaim_stale_tranche` call touching only that funder's own unallocated or reclaimable balance. There is no code path by which a party can move funds that were never theirs to move.

## Reporting a vulnerability

If you find a security issue in this contract, please open a GitHub issue on this repository describing the problem. Do not include exploit code targeting live deployments in a public issue — describe the class of vulnerability and its impact, and a fix will be coordinated privately if needed.
