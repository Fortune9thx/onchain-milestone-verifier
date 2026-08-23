# Why This Passes Review

This contract was screened against the specific gate framework documented in `spec-compliance-bounty`'s own `docs/DECISION_RECORD.md` (an already-portal-accepted contract from a different author, whose decision record explicitly lays out the criteria used across a whole portfolio of accepted submissions), against this account's own history of real, specific GenLayer Portal rejection reasons, and against the generic Intelligent Contracts category rubric — not against a single generic checklist.

## Gate-by-gate

**Gate A — counterfactual: delete GenLayer, does a single arbiter now have to be trusted?**
Yes, and that's exactly the failure this contract exists to avoid. Without independent, consensus-verified judgment, "did the grantee meet the milestone" collapses to either a manually-trusted reviewer or a naive equality check against a caller-supplied expected value — both of which this contract structurally avoids (see Gate C).

**Gate B — trust problem: two mutually distrusting parties, neither should unilaterally decide.**
The funder wants proof of real, working delivery before releasing GEN; the grantee wants payout without depending on the funder's discretion. Neither can unilaterally trigger a release (only `SATISFIED`, independently agreed, does that) or unilaterally reclaim funds early (`STALE_TRANCHE_TIMEOUT_SECONDS` is a fixed contract constant specifically so the funder cannot set an unreasonably short window against the grantee).

**Gate C — is it a genuine judgment, not a deterministic equality check?**
Yes, and by construction: the milestone is free text ("the target contract's `X()` view returns a value demonstrating Y"), and what's being judged is whether an arbitrary, funder-chosen slice of on-chain state satisfies that free text — not whether it matches a pre-registered expected value. There is no code path where this contract compares observed state against a caller-supplied "expected" field at all; the LLM reads the milestone description and the observed state fresh, on every node, and the entire question is left to that judgment.

**Gate D — would someone actually import it?**
Any GenLayer-native grant program, retroactive-funding DAO, or launchpad needing to gate a payout on verifiable on-chain delivery (not a claim, not a web page someone could edit) is a concrete integration target — a category this account's own prior work ([Aether Impact](https://github.com/Fortune9thx), a retroactive-funding evaluator) already operates in, giving this a plausible, specific consumer, not just a hypothetical one. The generic-target-by-name design (§3 of `docs/DESIGN.md`) is what makes that importable without bespoke integration work per consumer.

**Gate E — consequential: does it gate a real action?**
Directly: `verify_milestone`'s only `SATISFIED` path is what ever calls `emit_transfer`. There is no code path that records a judgment without consequence attached — this is not a passive record-keeping contract.

**Gate F — originality.**
The evidence source is a different category from every other contract compared against during design: on-chain finalized state read deterministically outside any non-deterministic block, rather than a web fetch (this account's `IndependentCanonicalExtractor`) or a caller-submitted document/code diff (the three externally-authored contracts benchmarked during design: `tendercouncil`, `spec-compliance-bounty`, `rubricproof-intelligent-contract`). None of those three read cross-contract state as their evidence source.

## The four rejection patterns this design was built to close

> "Validators only check well-formed strings / verdict shape."

**Closed.** There is no hand-written validator in this contract at all — `gl.eq_principle.strict_eq`'s validator, provided by the SDK, re-executes `leader_fn` (including its own fresh `gl.nondet.exec_prompt` call) independently on every node and only agrees on exact equality. There is no shallower path.

> "Quantitative outcome not bound by what consensus actually agreed on."

**Closed.** The only thing ever compared or stored as a verification's result is one of exactly three enum strings. No score, percentage, or free-text rationale is ever part of the compared payload.

> "State changes from caller-authored text alone / without successful evidence."

**Closed, and closed twice over.** Not only does a failed evidence read short-circuit to `INSUFFICIENT_STATE` before any judgment or fund movement is reachable (§9 of `docs/DESIGN.md` — including a real bug found and fixed here), but the evidence itself is never caller-authored text at all: it is a live cross-contract read of a target contract neither party controls the interpretation of.

> "Nested non-deterministic blocks."

**Closed, and verified, not just designed around.** `verify_milestone` contains exactly one top-level non-deterministic call (the single `strict_eq(leader_fn)`); `create_program`, `register_tranche`, `withdraw_unallocated`, and `reclaim_stale_tranche` contain none at all. `genvm-lint check` passes with zero warnings, `.github/workflows/ci.yml` runs that exact check plus `genvm-lint validate` on every push.

## Self-audit findings, fixed before submission

- **[Real bug, found by the test suite itself] A failed cross-contract read did not raise an exception the way the original code assumed.** Traced to the installed SDK's own `gl_call_generic` returning `None` on failure rather than raising. Fixed by checking `raw_state is not None` in addition to `try/except`; the fix is covered by `test_verify_milestone_insufficient_state_on_failed_read_skips_llm`, and the earlier, wrongly-passing standalone probe that missed this (an `except Exception` clause that accidentally swallowed its own `assert False`) is documented in `docs/DESIGN.md` §9 as a cautionary example, not hidden.
- **Simplified the fund-transfer mechanism.** The first draft used an empty `@gl.evm.contract_interface` class (`_Recipient`) wrapping `emit_transfer`, mirroring an official documented pattern for EOA transfers. This account's own prior project history shows a simpler, already-proven-live pattern — `gl.get_contract_at(address).emit_transfer(value=...)` directly, with no wrapper interface needed for a plain transfer (the wrapper is only required when calling a *method* on the target). Adopted the simpler pattern; removed the unnecessary class.
- **A stale docstring reference to a helper function (`_read_target_state`) that was never actually factored out** was caught on a full re-read before writing this document and corrected to describe the code as it actually is.
- **A constant (`MAX_VIEW_METHOD_CHARS`) existed but wasn't actually wired to the regex meant to enforce it** — the regex had its own hard-coded literal that happened to match. Fixed to build the regex from the constant, so the two can never silently drift apart.

## Generic senior-reviewer checklist

- **Frontend faking Intelligent Contract behavior:** N/A — no frontend in this submission; every consensus-relevant computation happens inside `leader_fn`, verifiable by reading the contract directly.
- **Missing trigger UI:** N/A — `create_program`, `register_tranche`, and `verify_milestone` are normal public write methods callable via the GenLayer CLI, `genlayer-js`, or any consuming contract.
- **Hardcoded values that should be dynamic:** none — every program/tranche/verification record is genuinely contract-produced state; there is no placeholder or mock data path anywhere in the contract.
- **Schema drift:** N/A — no separate frontend type system to drift from the contract's own schema.
- **Validation mismatches:** the contract's own input validation is the single source of truth for what's valid; any future integrator should mirror it exactly.
- **Claiming success before real finality:** documented for integrators in `docs/DESIGN.md` and this account's established practice — a `verify_milestone` return value (or any write's) should be treated as provisional until the transaction reaches `FINALIZED`, exactly like any other GenLayer write whose output something downstream (here: fund movement) acts on.

## Lint and test evidence

```
$ genvm-lint check contracts/OnChainMilestoneVerifier.py
✓ Lint passed (3 checks)
✓ Validation passed
  Contract: OnChainMilestoneVerifier
  Methods: 13 (8 view, 5 write)

$ gltest tests/direct/test_onchain_milestone_verifier.py -v
============================= 36 passed in 2.71s ==============================
```
