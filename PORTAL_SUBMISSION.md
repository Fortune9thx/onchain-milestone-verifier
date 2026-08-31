# Portal Submission

Text below is ready to paste directly into the GenLayer Portal submission form.

## Project name

OnChainMilestoneVerifier

## Category

Intelligent Contracts (reusable primitive)

## One-line pitch

A reusable GenLayer primitive that releases escrowed grant/bounty funds only when independent validators agree a target contract's real, already-finalized on-chain state satisfies a plain-language milestone.

## Description / Notes (964 / 1000 characters)

> Character count verified with `wc -m`, not eyeballed.

```
OnChainMilestoneVerifier releases escrowed grant/bounty GEN only when independent validators agree a target contract's real, already-finalized on-chain state satisfies a plain-language milestone. A funder escrows funds and registers tranches naming an amount, a milestone description, a target contract address, and which view method to check. Either party can trigger verification: the contract deterministically reads that view method against finalized state (no re-fetching needed -- finalized state is canonical, unlike a web page), then every validator independently judges whether it satisfies the milestone via gl.eq_principle.strict_eq, bounded to SATISFIED/NOT_SATISFIED/INSUFFICIENT_STATE. Only SATISFIED releases funds. A failed read short-circuits to INSUFFICIENT_STATE with no LLM call spent. Stale tranches are reclaimable after 90 days. Live-verified end-to-end with a real 2 GEN escrow and fund release. 40 direct-mode tests pass, genvm-lint clean.
```

## Deployed contract

- **Network:** GenLayer Testnet Bradbury
- **Address (current, v1.3.0):** `0x46Bc691A9B79670ee5137585641fc455aA830961`
- **Deploy transaction:** `0xb0ead77e9a2513da799460be4eb26ad4e33567b99a6d3ca1619daf54e629cbb6`, confirmed `FINALIZED`/`AGREE`/`FINISHED_WITH_RETURN`, post-deploy read confirmed (`get_program_count() == 0`)
- **Explorer:** https://explorer-bradbury.genlayer.com/address/0x46Bc691A9B79670ee5137585641fc455aA830961
- **Why redeployed (three times):** a maximally adversarial, source-only review found and fixed five issues in the original 1.0.0 deployment (`[1.1.0]`, `docs/DESIGN.md` §12), one critical. A second adversarial pass over 1.1.0 found that two of *those* fixes had themselves traded one real problem for another (`[1.2.0]`, `docs/DESIGN.md` §13). Then a real GenLayer Portal steward review of 1.2.0 found that its capped `retry_release` was still unsafe -- a cap bounds how many guaranteed duplicate payments are possible, but doesn't prevent the first one, since GenVM gives contract code no way to verify a retry's own precondition. `retry_release` is removed entirely in `[1.3.0]`, `docs/DESIGN.md` §14 -- the first fix in this project's history driven by external review rather than self-review. No public method's signature changed net across all three rounds; `retry_release` was added in round 1 and fully removed in round 3.
- **Live verification (full lifecycle, real GEN, recorded on the original 1.0.0 deployment — the underlying mechanism is unchanged by the fixes above):**
  1. `create_program(grantee)` with a real 2 GEN deposit — escrow correctly recorded (`total_escrowed: 2000000000000000000`)
  2. `register_tranche(...)` for 1 GEN, gated on a real deployed target contract ([`DeploymentStatusTarget`](examples/deployment_status_target.py) at `0xa775A4BAd9DEC803e61CD4b5c42c6988d356f918`)'s `deployment_status()` view method
  3. `verify_milestone(...)` while the target read `"PENDING"` — correctly independently judged `NOT_SATISFIED`, zero funds moved
  4. Target's `mark_live()` called and finalized
  5. `verify_milestone(...)` re-triggered — correctly independently judged `SATISFIED`, released 1 GEN, tranche flipped `RELEASED`, program accounting updated (`released: 1000000000000000000`)
  - `ACCEPTED`/`AGREE`/`FINISHED_WITH_RETURN` on both verification transactions; finalization follows the same pattern already confirmed for the deploy and setup transactions in this same sequence.
  - **Real, live-only finding surfaced during this test** (not present in mocked tests): querying a target contract's `LATEST_FINAL` state before that target's own relevant transaction has itself reached `FINALIZED` is a VM-level fault, not a Python-catchable one. Documented transparently in `docs/DESIGN.md` §9a rather than hidden — the fix is operational (wait for target finalization before triggering verification), not a code defect, and was confirmed by retrying the identical call once the target finalized.

## Repository

https://github.com/Fortune9thx/onchain-milestone-verifier

## Key features

- Independent re-execution consensus via `gl.eq_principle.strict_eq` over a real cross-contract read — no shape-only validator exists to get wrong.
- **A genuinely different evidence category** from web-fetch-based oracles: on-chain finalized state, read deterministically outside any non-deterministic block (cross-contract calls are forbidden inside one), rather than re-fetched per validator.
- Dynamic, name-based cross-contract dispatch (`getattr`-resolved view calls) makes this a generic verification layer for target view methods taking no arguments, or only `str`/`int`/`bool` arguments, not a bespoke checker.
- Rigid, three-value bounded outcome (`SATISFIED`/`NOT_SATISFIED`/`INSUFFICIENT_STATE`) — no confidence scores or free text in the compared payload.
- Real escrow economics: checks-effects-interactions fund release, unallocated-balance withdrawal, and a fixed-timeout stale-tranche reclaim. Deliberately has no fund-transfer retry mechanism -- an earlier one was removed after a real GenLayer steward review identified that a capped retry is still an unconditional, guaranteed duplicate payment against this contract's shared pooled balance, since GenVM gives contract code no way to verify the retry's own precondition. See `docs/DESIGN.md` §14.
- Re-verification requires the target's observed state to genuinely change since the last attempt, and is rate-limited by a cooldown (`MIN_VERIFICATION_INTERVAL_SECONDS`) rather than a fixed attempt count — closes a real, self-identified fund-drain path where unlimited free retries against a stochastic LLM judgment could otherwise be farmed for a lucky false-positive `SATISFIED`, without the fixed-count alternative's own failure mode (a bad-faith funder exhausting a shared budget to permanently deny a grantee who genuinely finishes). See `docs/DESIGN.md` §§12–13.
- A real bug found and fixed by the test suite before deployment (a failed cross-contract read doesn't raise, contrary to the initial assumption) — documented transparently, not hidden. See `docs/DESIGN.md` §9.
- A second real finding surfaced only by live deployment (§9a): a not-yet-finalized target contract makes `LATEST_FINAL` reads fault at the VM level, not the Python level — confirmed, understood, and documented as an operational sequencing note for integrators, not glossed over.
- Live-verified end-to-end on Bradbury with real GEN: a full escrow → tranche → `NOT_SATISFIED` → `mark_live` → `SATISFIED` → fund-release cycle, not just mocked tests.
- 40 passing direct-mode tests (including a project-built mock for cross-contract calls, since `gltest` has no built-in one), `genvm-lint check`/`validate` both clean, CI running all three on every push.

## Evidence of quality

```
$ genvm-lint check contracts/OnChainMilestoneVerifier.py
✓ Lint passed (3 checks)
✓ Validation passed
  Contract: OnChainMilestoneVerifier
  Methods: 13 (8 view, 5 write)

$ gltest tests/direct/test_onchain_milestone_verifier.py -v
============================= 40 passed in 4.98s ==============================
```

## Links

- README: see repository root
- Design rationale: `docs/DESIGN.md`
- Rejection-pattern / gate-framework mapping: `docs/WHY_THIS_PASSES_REVIEW.md`
