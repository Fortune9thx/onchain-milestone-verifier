# Changelog

All notable changes to this project are documented in this file.

## [1.0.0] - 2026-08-23

Initial release. Deployed to Bradbury at `0xF5Df96807a6c71b273F361633d19529c8B7918e7` and live-verified end-to-end with a real 2 GEN escrow (`create_program` → `register_tranche` → `verify_milestone` → `NOT_SATISFIED` → target `mark_live()` → `verify_milestone` → `SATISFIED` → 1 GEN released).

- `create_program(grantee)` — payable, escrows GEN for a grantee.
- `register_tranche(program_id, amount, milestone_description, target_contract, view_method, view_args_json)` — funder-only, registers a milestone-gated tranche against a program's unallocated escrow.
- `verify_milestone(tranche_id)` — deterministic cross-contract read (`.view(state=StorageType.LATEST_FINAL)`) against the target contract, followed by an independent `gl.eq_principle.strict_eq` judgment (`SATISFIED`/`NOT_SATISFIED`/`INSUFFICIENT_STATE`); releases escrowed GEN to the grantee only on `SATISFIED`. A failed or null-returning read short-circuits to `INSUFFICIENT_STATE` without spending an LLM call.
- `withdraw_unallocated(program_id)` — funder-only, refunds never-allocated escrow.
- `reclaim_stale_tranche(tranche_id)` — funder-only, after a fixed 90-day timeout with no successful verification, reclaims a tranche's allocation.
- Full view surface: `get_program`, `get_tranche`, `get_verification`, `list_program_ids`, `list_tranche_ids`, `list_verification_ids`, `list_tranches_for_grantee`, `get_program_count`.
- 36 direct-mode tests, including a project-specific `_gl_call_hook`-based mock for cross-contract calls (no built-in `gltest` support exists for this); `genvm-lint check`/`validate` both clean.
- A real bug found and fixed during development: a failed cross-contract read does not raise an exception (the installed SDK's `gl_call_generic` returns `None` on failure) — the original `try/except`-only detection missed this, caught by the test suite before deployment. See `docs/DESIGN.md` §9.
- A second real finding, surfaced only by the live deployment itself: querying `LATEST_FINAL` state against a target contract that has been `ACCEPTED` but not yet `FINALIZED` is a VM-level fault, not a catchable Python exception — the whole transaction reverts before any of `verify_milestone`'s own error handling can run. This is an operational sequencing constraint for integrators (wait for the target's write to finalize before verifying against it), not a code defect; documented in `docs/DESIGN.md` §9a.
- CI workflow running lint (check + validate) and tests on every push.
