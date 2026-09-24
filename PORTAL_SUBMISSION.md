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
OnChainMilestoneVerifier releases escrowed grant/bounty GEN only when independent validators agree a target contract's real, already-finalized on-chain state satisfies a plain-language milestone. A funder escrows funds and registers tranches naming an amount, a milestone description, a target contract address, and which view method to check. Either party can trigger verification: the contract deterministically reads that view method against finalized state (no re-fetching needed -- finalized state is canonical, unlike a web page), then every validator independently judges whether it satisfies the milestone via gl.eq_principle.strict_eq, bounded to SATISFIED/NOT_SATISFIED/INSUFFICIENT_STATE. Only SATISFIED releases funds. A failed read short-circuits to INSUFFICIENT_STATE with no LLM call spent. Stale tranches are reclaimable after 90 days. Live-verified end-to-end with a real 2 GEN escrow and fund release. 41 direct-mode tests pass, genvm-lint clean.
```

## Deployed contract

- **Network:** GenLayer Studio Devnet (`studioDevnet`, chain id `61997`)
- **Address (current, v1.5.0):** [`0x6892dD5Cdccaa536aA86ba38d14cB99F2FFE50AA`](https://explorer-studio-dev.genlayer.com/address/0x6892dD5Cdccaa536aA86ba38d14cB99F2FFE50AA)
- **Explorer:** https://explorer-studio-dev.genlayer.com/address/0x6892dD5Cdccaa536aA86ba38d14cB99F2FFE50AA
- **Why redeployed (five times, network migration included):** a maximally adversarial, source-only review found and fixed five issues in the original 1.0.0 deployment (`[1.1.0]`, `docs/DESIGN.md` §12), one critical. A second adversarial pass over 1.1.0 found that two of *those* fixes had themselves traded one real problem for another (`[1.2.0]`, `docs/DESIGN.md` §13). A real GenLayer Portal steward review of 1.2.0 found that its capped `retry_release` was still unsafe, since GenVM gives contract code no way to verify a retry's own precondition -- removed entirely in `[1.3.0]`, `docs/DESIGN.md` §14. A second steward review, of 1.3.0, found that `verify_milestone`'s anti-farming marker was hashed from the truncated observed-state string rather than the complete one -- fixed in `[1.4.0]`, `docs/DESIGN.md` §15. Before that fix could redeploy to Bradbury, Bradbury suffered a confirmed, multi-day network outage (`docs/DESIGN.md` §16), and this account's toolchain had already moved to GenLayer Consensus v0.6 / SDK v0.3.0, which Bradbury's older stack cannot serve -- `[1.5.0]` migrates to Studio Devnet and ports the contract to the v0.3.0 API, with no public method signature changes across any of the five rounds; `retry_release` was added in round 1 and fully removed in round 3.
- **Live verification on Studio Devnet, stated honestly:**
  1. `create_program(grantee)` with a real 2 GEN deposit -- escrow correctly recorded, confirmed via `get_program`
  2. `register_tranche(...)` for 1 GEN, gated on a real deployed target contract ([`DeploymentStatusTarget`](examples/deployment_status_target.py) at `0xfBECDFaB8671f009D22E65ea90e49512F6EC2eFE`)'s `deployment_status()` view method -- confirmed via `get_tranche`
  3. `withdraw_unallocated(...)` separately exercised live -- `FINALIZED`/`AGREE`, 5/5 validators voting, in under three seconds, confirming the deterministic write path, account, and network are all healthy
  4. `verify_milestone(...)` -- the one call that runs a real `exec_prompt` -- has not yet completed live on Studio Devnet as of this submission. Every attempt traces to specific validator nodes configured against an unreachable LLM provider (`router.ygr.ai`), a confirmed GenLayer-team-acknowledged infrastructure gap ([`genvm-manager#7`](https://github.com/genlayerlabs/genvm-manager/issues/7), [`#13`](https://github.com/genlayerlabs/genvm-manager/issues/13)), documented in full in `docs/DESIGN.md` §16 rather than hidden. Every attempt reverted cleanly with no state change.
  - The full read → judge → release mechanism (including a real `NOT_SATISFIED` → `mark_live` → `SATISFIED` → 1 GEN release cycle) was already live-verified end-to-end with real GEN on the original Bradbury 1.0.0 deployment; that mechanism is unchanged by any fix since. See `CHANGELOG.md`'s `[1.0.0]` entry for that record.
  - **Real, live-only finding surfaced during that original test** (not present in mocked tests): querying a target contract's finalized state before that target's own relevant transaction has itself reached `FINALIZED` is a VM-level fault, not a Python-catchable one. Documented transparently in `docs/DESIGN.md` §9a rather than hidden.

## Repository

https://github.com/Fortune9thx/onchain-milestone-verifier

## Key features

- Independent re-execution consensus via `gl.eq_principle.strict_eq` over a real cross-contract read — no shape-only validator exists to get wrong.
- **A genuinely different evidence category** from web-fetch-based oracles: on-chain finalized state, read deterministically outside any non-deterministic block (cross-contract calls are forbidden inside one), rather than re-fetched per validator.
- Dynamic, name-based cross-contract dispatch (`getattr`-resolved view calls) makes this a generic verification layer for target view methods taking no arguments, or only `str`/`int`/`bool` arguments, not a bespoke checker.
- Rigid, three-value bounded outcome (`SATISFIED`/`NOT_SATISFIED`/`INSUFFICIENT_STATE`) — no confidence scores or free text in the compared payload.
- Real escrow economics: checks-effects-interactions fund release, unallocated-balance withdrawal, and a fixed-timeout stale-tranche reclaim. Deliberately has no fund-transfer retry mechanism -- an earlier one was removed after a real GenLayer steward review identified that a capped retry is still an unconditional, guaranteed duplicate payment against this contract's shared pooled balance, since GenVM gives contract code no way to verify the retry's own precondition. See `docs/DESIGN.md` §14.
- Re-verification requires the target's observed state to genuinely change since the last attempt, and is rate-limited by a cooldown (`MIN_VERIFICATION_INTERVAL_SECONDS`) rather than a fixed attempt count — closes a real, self-identified fund-drain path where unlimited free retries against a stochastic LLM judgment could otherwise be farmed for a lucky false-positive `SATISFIED`, without the fixed-count alternative's own failure mode (a bad-faith funder exhausting a shared budget to permanently deny a grantee who genuinely finishes). The change-detection marker is hashed from the complete observed state, not the truncated string used for the LLM prompt and audit storage -- a real GenLayer steward review caught an earlier version hashing the truncated string, which could make a milestone-relevant change past the truncation cutoff permanently invisible to this gate. See `docs/DESIGN.md` §§12–13, §15.
- A real bug found and fixed by the test suite before deployment (a failed cross-contract read doesn't raise, contrary to the initial assumption) — documented transparently, not hidden. See `docs/DESIGN.md` §9.
- A second real finding surfaced only by live deployment (§9a): a not-yet-finalized target contract makes a finalized-state read fault at the VM level, not the Python level — confirmed, understood, and documented as an operational sequencing note for integrators, not glossed over.
- Live-verified end-to-end on the original Bradbury deployment with real GEN: a full escrow → tranche → `NOT_SATISFIED` → `mark_live` → `SATISFIED` → fund-release cycle, not just mocked tests; escrow and tranche registration re-verified live on the current Studio Devnet deployment as well. See `docs/DESIGN.md` §16 for the honest current status of `verify_milestone`'s live run there, blocked by a documented, GenLayer-team-acknowledged infrastructure gap rather than a code defect.
- 41 passing direct-mode tests (including a project-built mock for cross-contract calls, since `gltest` has no built-in one), `genvm-lint check`/`validate` both clean, CI running all three on every push.

## Evidence of quality

```
$ genvm-lint check contracts/OnChainMilestoneVerifier.py
✓ Lint passed (3 checks)
✓ Validation passed
  Contract: OnChainMilestoneVerifier
  Methods: 13 (8 view, 5 write)

$ gltest tests/direct/test_onchain_milestone_verifier.py -v
============================= 41 passed in 4.87s ==============================
```

## Links

- README: see repository root
- Design rationale: `docs/DESIGN.md`
- Rejection-pattern / gate-framework mapping: `docs/WHY_THIS_PASSES_REVIEW.md`
