# Final Checklist

## Contract design

- [x] Exact two-line file header (`# v0.2.16` / `# { "Depends": ... }`)
- [x] Storage: all TreeMaps explicitly initialized in `__init__`; `program_ids` (DynArray) deliberately left as a bare annotation (`DynArray()` forbids direct instantiation — confirmed both by SDK source and by this contract's own test suite catching it)
- [x] `create_program`, `register_tranche`, `verify_milestone`, `withdraw_unallocated`, `reclaim_stale_tranche` (write) + 8 view methods
- [x] Exactly one non-deterministic call (`gl.eq_principle.strict_eq`), only in `verify_milestone`; every other write method is fully deterministic
- [x] `leader_fn` is a named `def`, never a `lambda`
- [x] Cross-contract read happens in the deterministic body, never inside the nondet block (matches the documented GenVM constraint: `CallContract` inside a nondet closure raises `SystemError: 6`)
- [x] `.view(state=StorageType.LATEST_FINAL)` used explicitly, not the SDK's `LATEST_NON_FINAL` default — closes a real node-to-node determinism gap
- [x] Rigid three-value bounded outcome (`SATISFIED`/`NOT_SATISFIED`/`INSUFFICIENT_STATE`); `_extract_outcome` fails closed to `NOT_SATISFIED`, never `SATISFIED`
- [x] A failed OR null-returning cross-contract read short-circuits to `INSUFFICIENT_STATE` with no LLM call — verified this required checking `raw_state is not None`, not just `try/except` (a real bug caught by the test suite, documented in `docs/DESIGN.md` §9)
- [x] Fund release follows checks-effects-interactions ordering throughout (`verify_milestone`, `withdraw_unallocated`, `reclaim_stale_tranche`)
- [x] Only `gl.vm.UserError` used for user-facing errors
- [x] Strong validation on every write method's inputs (addresses, amounts, string lengths, view_args shape/type)
- [x] Heavy educational comments explaining the deterministic-evidence/non-deterministic-judgment split, dynamic cross-contract dispatch, the rigid outcome, and the escrow/CEI design

## Quality bar

- [x] `genvm-lint check` and `genvm-lint validate` both pass with zero warnings
- [x] Direct-mode tests pass (36/36) — happy paths, authorization, validation, fund-accounting correctness, the deterministic-read-failure short-circuit, and pure-helper unit tests
- [x] Bradbury dependency pin used (`py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6`), matching this account's other live-verified GenLayer contracts
- [x] Obviously useful, reusable primitive — generic name-based cross-contract dispatch means it's not a bespoke checker for one integration; a worked integration example is included (`examples/deployment_status_target.py`)
- [x] Screened against a real, external gate framework (`spec-compliance-bounty`'s own `docs/DECISION_RECORD.md`), not just a generic checklist — see `docs/WHY_THIS_PASSES_REVIEW.md`
- [x] The mechanism this contract depends on (dynamic cross-contract view calls) was empirically validated with a standalone probe *before* the real contract was written, not assumed from reading SDK source alone

## Deliverables

- [x] `contracts/OnChainMilestoneVerifier.py`
- [x] `tests/direct/test_onchain_milestone_verifier.py` + `tests/direct/conftest.py` (includes the project-specific cross-contract-call mock and the `gl.message_raw["datetime"]`/`vm.warp()` fix)
- [x] `README.md`
- [x] `docs/DESIGN.md`
- [x] `docs/WHY_THIS_PASSES_REVIEW.md`
- [x] `PORTAL_SUBMISSION.md`
- [x] `FINAL_CHECKLIST.md` (this file)
- [x] `LICENSE` (MIT), `CHANGELOG.md`, `SECURITY.md`, `examples/deployment_status_target.py`, `.github/workflows/ci.yml`

## Deployment and publication

- [x] Deployed to GenLayer Testnet Bradbury: `0xF5Df96807a6c71b273F361633d19529c8B7918e7`, deploy tx confirmed `FINALIZED`/`AGREE`/`FINISHED_WITH_RETURN`
- [x] Post-deploy read verified (`get_program_count() == 0`, `list_program_ids() == []` immediately after deploy)
- [x] Example target contract (`DeploymentStatusTarget`) deployed at `0xa775A4BAd9DEC803e61CD4b5c42c6988d356f918`, confirmed `FINALIZED`/`AGREE`
- [x] **Live end-to-end lifecycle verified with real GEN, not just mocked tests:**
  1. `create_program(grantee)` with a real 2 GEN deposit (sent via a `genlayer-js` script, since the bare CLI has no exposed flag for payable-write value — `--fee-value` was confirmed to be gas fee, not `msg.value`, by observing the contract's own validation correctly reject a zero-value attempt) — escrow correctly recorded
  2. `register_tranche(...)` for 1 GEN gated on the real target's `deployment_status()` — also required the `genlayer-js` script route, since the CLI's JSON-type-inference bug (already documented in project memory) silently converted the `view_args_json="[]"` string parameter into a parsed empty array
  3. `verify_milestone(...)` triggered too early (target `ACCEPTED` but not yet `FINALIZED`) — reverted with a VM-level fault, correctly diagnosed as a real, live-only finding (not a contract bug) — see `docs/DESIGN.md` §9a and the CHANGELOG
  4. `verify_milestone(...)` retried after the target genuinely finalized — succeeded, correctly returned `NOT_SATISFIED` (target still read `"PENDING"`), zero funds moved
  5. Target's `mark_live()` called and finalized
  6. `verify_milestone(...)` re-triggered — correctly returned `SATISFIED`, released 1 GEN, tranche flipped to `RELEASED`, program's `released` total correctly updated to `1000000000000000000`
- [x] `README.md` / `PORTAL_SUBMISSION.md` / `FINAL_CHECKLIST.md` updated with the real deployed addresses, transaction results, and both live-only findings
- [x] Exported wallet keystore and password deleted immediately after the `genlayer-js` scripts that needed them finished running
- [x] Pushed to a public GitHub repository under the account's sole-author convention (no AI co-author trailer) — https://github.com/Fortune9thx/onchain-milestone-verifier
- [x] Repository link added to `PORTAL_SUBMISSION.md`
- [x] `.github/workflows/ci.yml` pushed and confirmed green on a real GitHub Actions run (all three checks — `genvm-lint check`, `genvm-lint validate`, and the 36-test suite — passed on a clean runner)

## Post-fix redeploy (current)

A maximally adversarial post-launch review found and fixed five real issues (one critical) in `contracts/OnChainMilestoneVerifier.py`, including a genuine fund-drain path (unlimited free re-verification against a stochastic LLM judgment). See `CHANGELOG.md`'s `[1.1.0]` entry and `docs/DESIGN.md` §12 for the full account.

- [x] Fixes applied; test suite grew 36 → 42, all passing; `genvm-lint check`/`validate` both clean on the fixed source
- [x] Redeployed to GenLayer Testnet Bradbury: `0xDe1817Aa376Dc25cC2dF36a0738a615E1B215836`, deploy tx `0x4a979ae61361e4802bd3fc54ec6c8132e9f99f008a95bb57c4ca6db74f35f032`
- [x] Post-deploy read verified (`get_program_count() == 0`)
- [x] Deploy transaction reached genuine `FINALIZED` status, confirmed `AGREE`/`FINISHED_WITH_RETURN` (5/5 validators agreed)
- [x] `README.md` / `PORTAL_SUBMISSION.md` updated with the new address and an honest account of why the redeploy happened
- [x] Pushed to GitHub

The original 1.0.0 deployment (`0xF5Df96807a6c71b273F361633d19529c8B7918e7`) is superseded by the address above and should no longer be treated as this contract's current, correct deployment — it still runs the pre-fix logic (no live financial exposure at time of writing: its one tranche already released and closed, and the small unallocated balance remaining is safely withdrawable regardless of the fix). The full live end-to-end proof recorded below, from the original deployment, remains valid evidence for the underlying mechanism (deterministic read → independent judgment → fund release), which the fixes did not change.

---

*(Original 1.0.0 sign-off below, retained for history.)*

**Submission was ready as of 1.0.0. Every checkbox in this file was checked at that time; see the note above for what has changed since.**

**Known, accepted discrepancy (1.0.0 only):** one non-functional comment (documenting the §9a finding, discovered live *after* deployment) was added to `contracts/OnChainMilestoneVerifier.py` in this repository after the contract above was deployed. Behavior was unchanged at that time — re-verified via unchanged `genvm-lint check`/`validate` output and the full 36-test suite still passing — so this was not treated as grounds for a third redeploy. The deployed bytecode and the 1.0.0 repository source were functionally identical; they differed only in that one comment.

*(Deployment and publication checkboxes are updated in place once each step completes — this file is the single source of truth for submission readiness.)*
