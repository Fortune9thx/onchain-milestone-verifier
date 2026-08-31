"""Direct-mode tests for OnChainMilestoneVerifier.

Covers: the full program -> tranche -> verify -> release lifecycle, the
deterministic-read/non-deterministic-judgment split (including the
short-circuit-to-INSUFFICIENT_STATE-with-no-LLM-call path on a failed
cross-contract read), fund-movement correctness (escrow accounting,
CEI ordering, unallocated withdrawal, stale-tranche reclaim), input
validation, authorization, and the pure helper functions in isolation.
"""

import json
import sys

import pytest

from conftest import install_call_contract_mock, warp_with_message

CONTRACT_PATH = "contracts/OnChainMilestoneVerifier.py"

GRANTEE = "0x" + "22" * 20
FUNDER_SIBLING = "0x" + "44" * 20  # a second, non-funder/non-grantee address
TARGET = "0x" + "33" * 20


def _module():
    return sys.modules["_contract_OnChainMilestoneVerifier"]


def _mock_state_read(direct_vm, value, method="get_status"):
    install_call_contract_mock(direct_vm, {(TARGET.lower(), method): value})


def _setup_program_and_tranche(
    contract,
    direct_vm,
    *,
    program_value=1_000_000,
    tranche_amount=100_000,
    view_method="get_status",
    milestone="the target contract's get_status() returns DONE",
):
    direct_vm.value = program_value
    program_id = contract.create_program(GRANTEE)
    direct_vm.value = 0
    tranche_id = contract.register_tranche(
        program_id=program_id,
        amount=tranche_amount,
        milestone_description=milestone,
        target_contract=TARGET,
        view_method=view_method,
        view_args_json="[]",
    )
    return program_id, tranche_id


# ---------------------------------------------------------------------------
# create_program
# ---------------------------------------------------------------------------


def test_create_program_happy_path(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    direct_vm.value = 1_000_000
    program_id = contract.create_program(GRANTEE)
    direct_vm.value = 0

    assert program_id == "program-0"
    record = json.loads(contract.get_program(program_id))
    assert record["grantee"].lower() == GRANTEE.lower()
    assert record["total_escrowed"] == "1000000"
    assert record["allocated"] == "0"
    assert record["released"] == "0"
    assert record["status"] == "ACTIVE"
    assert contract.get_program_count() == 1
    assert list(contract.list_program_ids()) == ["program-0"]


def test_create_program_rejects_zero_value(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    with direct_vm.expect_revert("positive GEN deposit"):
        contract.create_program(GRANTEE)


def test_create_program_rejects_invalid_grantee(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    direct_vm.value = 1000
    with direct_vm.expect_revert("invalid grantee address"):
        contract.create_program("not-an-address")


# ---------------------------------------------------------------------------
# register_tranche
# ---------------------------------------------------------------------------


def test_register_tranche_happy_path(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    program_id, tranche_id = _setup_program_and_tranche(contract, direct_vm)

    assert tranche_id == f"{program_id}-tranche-0"
    record = json.loads(contract.get_tranche(tranche_id))
    assert record["amount"] == "100000"
    assert record["status"] == "PENDING"
    assert record["target_contract"].lower() == TARGET.lower()
    assert record["view_method"] == "get_status"
    assert record["view_args"] == []

    program = json.loads(contract.get_program(program_id))
    assert program["allocated"] == "100000"

    assert json.loads(contract.list_tranche_ids(program_id)) == [tranche_id]


def test_register_tranche_rejects_non_funder(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    direct_vm.value = 1_000_000
    program_id = contract.create_program(GRANTEE)
    direct_vm.value = 0

    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("only the program's funder"):
        contract.register_tranche(
            program_id=program_id,
            amount=100,
            milestone_description="x",
            target_contract=TARGET,
            view_method="get_status",
        )


def test_register_tranche_rejects_amount_exceeding_remaining(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    direct_vm.value = 1000
    program_id = contract.create_program(GRANTEE)
    direct_vm.value = 0
    with direct_vm.expect_revert("exceeds unallocated program balance"):
        contract.register_tranche(
            program_id=program_id,
            amount=1001,
            milestone_description="x",
            target_contract=TARGET,
            view_method="get_status",
        )


def test_register_tranche_rejects_zero_amount(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    direct_vm.value = 1000
    program_id = contract.create_program(GRANTEE)
    direct_vm.value = 0
    with direct_vm.expect_revert("must be positive"):
        contract.register_tranche(
            program_id=program_id,
            amount=0,
            milestone_description="x",
            target_contract=TARGET,
            view_method="get_status",
        )


def test_register_tranche_rejects_empty_milestone(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    direct_vm.value = 1000
    program_id = contract.create_program(GRANTEE)
    direct_vm.value = 0
    with direct_vm.expect_revert("milestone_description must not be empty"):
        contract.register_tranche(
            program_id=program_id,
            amount=10,
            milestone_description="   ",
            target_contract=TARGET,
            view_method="get_status",
        )


def test_register_tranche_rejects_invalid_target(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    direct_vm.value = 1000
    program_id = contract.create_program(GRANTEE)
    direct_vm.value = 0
    with direct_vm.expect_revert("invalid target_contract"):
        contract.register_tranche(
            program_id=program_id,
            amount=10,
            milestone_description="x",
            target_contract="not-an-address",
            view_method="get_status",
        )


def test_register_tranche_rejects_invalid_view_method(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    direct_vm.value = 1000
    program_id = contract.create_program(GRANTEE)
    direct_vm.value = 0
    for bad_method in ("_private", "123start", "has space", "x" * 65):
        with direct_vm.expect_revert("invalid view_method"):
            contract.register_tranche(
                program_id=program_id,
                amount=10,
                milestone_description="x",
                target_contract=TARGET,
                view_method=bad_method,
            )


def test_register_tranche_rejects_malformed_view_args(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    direct_vm.value = 1000
    program_id = contract.create_program(GRANTEE)
    direct_vm.value = 0
    with direct_vm.expect_revert("must be valid JSON"):
        contract.register_tranche(
            program_id=program_id,
            amount=10,
            milestone_description="x",
            target_contract=TARGET,
            view_method="get_status",
            view_args_json="not json",
        )
    with direct_vm.expect_revert("must be a JSON array"):
        contract.register_tranche(
            program_id=program_id,
            amount=10,
            milestone_description="x",
            target_contract=TARGET,
            view_method="get_status",
            view_args_json='{"a": 1}',
        )
    with direct_vm.expect_revert("strings, integers, or booleans only"):
        contract.register_tranche(
            program_id=program_id,
            amount=10,
            milestone_description="x",
            target_contract=TARGET,
            view_method="get_status",
            view_args_json="[null]",
        )


# ---------------------------------------------------------------------------
# verify_milestone -- SATISFIED path (fund release)
# ---------------------------------------------------------------------------


def test_verify_milestone_satisfied_releases_funds(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    program_id, tranche_id = _setup_program_and_tranche(contract, direct_vm)

    _mock_state_read(direct_vm, "DONE")
    direct_vm.mock_llm(r".", '{"outcome": "SATISFIED"}')

    verification_id = contract.verify_milestone(tranche_id)
    assert verification_id == f"{tranche_id}-verify-0"

    verification = json.loads(contract.get_verification(verification_id))
    assert verification["outcome"] == "SATISFIED"
    assert verification["observed_state"] == '"DONE"'

    tranche = json.loads(contract.get_tranche(tranche_id))
    assert tranche["status"] == "RELEASED"
    assert tranche["verification_count"] == 1

    program = json.loads(contract.get_program(program_id))
    assert program["released"] == "100000"

    assert json.loads(contract.list_verification_ids(tranche_id)) == [verification_id]
    assert json.loads(contract.list_tranches_for_grantee(GRANTEE)) == [tranche_id]


def test_verify_milestone_satisfied_only_via_exact_enum_value(direct_deploy, direct_vm):
    """A model that returns something outcome-shaped but not an exact
    ALLOWED_OUTCOMES member must never release funds -- fail closed."""
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    _, tranche_id = _setup_program_and_tranche(contract, direct_vm)

    _mock_state_read(direct_vm, "DONE")
    direct_vm.mock_llm(r".", '{"outcome": "PROBABLY_SATISFIED"}')

    verification_id = contract.verify_milestone(tranche_id)
    verification = json.loads(contract.get_verification(verification_id))
    assert verification["outcome"] == "NOT_SATISFIED"
    tranche = json.loads(contract.get_tranche(tranche_id))
    assert tranche["status"] == "PENDING"


# ---------------------------------------------------------------------------
# verify_milestone -- NOT_SATISFIED path (no release, re-triggerable)
# ---------------------------------------------------------------------------


def test_verify_milestone_not_satisfied_no_release(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    program_id, tranche_id = _setup_program_and_tranche(contract, direct_vm)

    _mock_state_read(direct_vm, "IN_PROGRESS")
    direct_vm.mock_llm(r".", '{"outcome": "NOT_SATISFIED"}')

    verification_id = contract.verify_milestone(tranche_id)
    verification = json.loads(contract.get_verification(verification_id))
    assert verification["outcome"] == "NOT_SATISFIED"

    tranche = json.loads(contract.get_tranche(tranche_id))
    assert tranche["status"] == "PENDING"
    program = json.loads(contract.get_program(program_id))
    assert program["released"] == "0"


def test_verify_milestone_can_be_retriggered_after_not_satisfied(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    warp_with_message(direct_vm, "2026-01-01T00:00:00Z")
    _, tranche_id = _setup_program_and_tranche(contract, direct_vm)

    _mock_state_read(direct_vm, "IN_PROGRESS")
    direct_vm.mock_llm(r".", '{"outcome": "NOT_SATISFIED"}')
    first_id = contract.verify_milestone(tranche_id)

    warp_with_message(direct_vm, "2026-01-02T00:01:00Z")  # past the cooldown
    direct_vm.clear_mocks()
    _mock_state_read(direct_vm, "DONE")
    direct_vm.mock_llm(r".", '{"outcome": "SATISFIED"}')
    second_id = contract.verify_milestone(tranche_id)

    assert first_id != second_id
    tranche = json.loads(contract.get_tranche(tranche_id))
    assert tranche["status"] == "RELEASED"
    assert tranche["verification_count"] == 2
    assert json.loads(contract.list_verification_ids(tranche_id)) == [first_id, second_id]


def test_verify_milestone_rejects_repeat_attempt_with_unchanged_state(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    warp_with_message(direct_vm, "2026-01-01T00:00:00Z")
    _, tranche_id = _setup_program_and_tranche(contract, direct_vm)

    _mock_state_read(direct_vm, "IN_PROGRESS")
    direct_vm.mock_llm(r".", '{"outcome": "NOT_SATISFIED"}')
    contract.verify_milestone(tranche_id)

    # Past the cooldown, so this reaches the state-unchanged gate rather
    # than being rejected by the cooldown gate first.
    warp_with_message(direct_vm, "2026-01-02T00:01:00Z")
    # Same target state as before -> rejected before any LLM call or write,
    # even though a fresh (unused) LLM mock is still registered.
    direct_vm.mock_llm(r".", '{"outcome": "SATISFIED"}')
    with direct_vm.expect_revert("state has not changed"):
        contract.verify_milestone(tranche_id)

    tranche = json.loads(contract.get_tranche(tranche_id))
    assert tranche["status"] == "PENDING"
    assert tranche["verification_count"] == 1
    assert json.loads(contract.list_verification_ids(tranche_id)) == [
        f"{tranche_id}-verify-0"
    ]


def test_verify_milestone_rejects_too_soon_repeat_attempt(direct_deploy, direct_vm):
    """Even with genuinely different observed state, a second attempt
    inside the cooldown window is rejected -- the cooldown, not a fixed
    attempt count, is what actually bounds re-verification rate (see
    docs/DESIGN.md #12 for why a fixed count was tried and reverted)."""
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    warp_with_message(direct_vm, "2026-01-01T00:00:00Z")
    _, tranche_id = _setup_program_and_tranche(contract, direct_vm)

    _mock_state_read(direct_vm, "STATE-A")
    direct_vm.mock_llm(r".", '{"outcome": "NOT_SATISFIED"}')
    contract.verify_milestone(tranche_id)

    warp_with_message(direct_vm, "2026-01-01T00:00:10Z")  # 10s later, well inside the cooldown
    direct_vm.clear_mocks()
    _mock_state_read(direct_vm, "STATE-B")  # genuinely different state
    direct_vm.mock_llm(r".", '{"outcome": "SATISFIED"}')
    with direct_vm.expect_revert("must wait at least"):
        contract.verify_milestone(tranche_id)

    tranche = json.loads(contract.get_tranche(tranche_id))
    assert tranche["status"] == "PENDING"
    assert tranche["verification_count"] == 1


def test_verify_milestone_allows_repeat_attempt_after_cooldown_elapses(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    warp_with_message(direct_vm, "2026-01-01T00:00:00Z")
    _, tranche_id = _setup_program_and_tranche(contract, direct_vm)

    _mock_state_read(direct_vm, "STATE-A")
    direct_vm.mock_llm(r".", '{"outcome": "NOT_SATISFIED"}')
    contract.verify_milestone(tranche_id)

    warp_with_message(direct_vm, "2026-01-02T00:01:00Z")  # past the cooldown
    direct_vm.clear_mocks()
    _mock_state_read(direct_vm, "STATE-B")
    direct_vm.mock_llm(r".", '{"outcome": "SATISFIED"}')
    contract.verify_milestone(tranche_id)

    tranche = json.loads(contract.get_tranche(tranche_id))
    assert tranche["status"] == "RELEASED"
    assert tranche["verification_count"] == 2


def test_verify_milestone_can_be_retriggered_when_state_genuinely_changes_after_failure(
    direct_deploy, direct_vm
):
    """Distinct from the unchanged-state rejection above: a genuinely
    different observed state each time must keep working, once the
    cooldown has elapsed."""
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    warp_with_message(direct_vm, "2026-01-01T00:00:00Z")
    _, tranche_id = _setup_program_and_tranche(contract, direct_vm)

    _mock_state_read(direct_vm, "IN_PROGRESS")
    direct_vm.mock_llm(r".", '{"outcome": "NOT_SATISFIED"}')
    first_id = contract.verify_milestone(tranche_id)

    warp_with_message(direct_vm, "2026-01-02T00:01:00Z")  # past the cooldown
    direct_vm.clear_mocks()
    _mock_state_read(direct_vm, "STILL_IN_PROGRESS")
    direct_vm.mock_llm(r".", '{"outcome": "NOT_SATISFIED"}')
    second_id = contract.verify_milestone(tranche_id)

    assert first_id != second_id
    tranche = json.loads(contract.get_tranche(tranche_id))
    assert tranche["verification_count"] == 2


def test_verify_milestone_rejects_on_already_released(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    _, tranche_id = _setup_program_and_tranche(contract, direct_vm)
    _mock_state_read(direct_vm, "DONE")
    direct_vm.mock_llm(r".", '{"outcome": "SATISFIED"}')
    contract.verify_milestone(tranche_id)

    with direct_vm.expect_revert("not PENDING"):
        contract.verify_milestone(tranche_id)


# ---------------------------------------------------------------------------
# verify_milestone -- INSUFFICIENT_STATE paths
# ---------------------------------------------------------------------------


def test_verify_milestone_insufficient_state_via_llm_judgment(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    _, tranche_id = _setup_program_and_tranche(contract, direct_vm)

    _mock_state_read(direct_vm, "")
    direct_vm.mock_llm(r".", '{"outcome": "INSUFFICIENT_STATE"}')

    verification_id = contract.verify_milestone(tranche_id)
    verification = json.loads(contract.get_verification(verification_id))
    assert verification["outcome"] == "INSUFFICIENT_STATE"
    tranche = json.loads(contract.get_tranche(tranche_id))
    assert tranche["status"] == "PENDING"


def test_verify_milestone_insufficient_state_on_failed_read_skips_llm(
    direct_deploy, direct_vm
):
    """No cross-contract mock installed at all -> the deterministic read
    fails -> outcome must be INSUFFICIENT_STATE WITHOUT any LLM call
    (no mock_llm registered at all; if the contract tried to call
    exec_prompt anyway, gltest's strict-mock-free default would still not
    fail loudly, so this is also checked by strict_mocks below)."""
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    _, tranche_id = _setup_program_and_tranche(contract, direct_vm)
    # deliberately no install_call_contract_mock call, no mock_llm call

    direct_vm.strict_mocks = True  # would flag an unused LLM mock, but none is registered,
    # so this really just documents intent; the real assertion is the outcome below.

    verification_id = contract.verify_milestone(tranche_id)
    verification = json.loads(contract.get_verification(verification_id))
    assert verification["outcome"] == "INSUFFICIENT_STATE"
    assert verification["observed_state"] is None
    tranche = json.loads(contract.get_tranche(tranche_id))
    assert tranche["status"] == "PENDING"


# ---------------------------------------------------------------------------
# verify_milestone -- authorization and view_args plumbing
# ---------------------------------------------------------------------------


def test_verify_milestone_rejects_non_funder_non_grantee(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    _, tranche_id = _setup_program_and_tranche(contract, direct_vm)
    _mock_state_read(direct_vm, "DONE")

    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("only the tranche's funder or grantee"):
        contract.verify_milestone(tranche_id)


def test_verify_milestone_passes_view_args_through(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    direct_vm.value = 1000
    program_id = contract.create_program(GRANTEE)
    direct_vm.value = 0
    tranche_id = contract.register_tranche(
        program_id=program_id,
        amount=100,
        milestone_description="get_balance(owner) returns at least 100",
        target_contract=TARGET,
        view_method="get_balance",
        view_args_json='["some-owner-id"]',
    )

    install_call_contract_mock(direct_vm, {(TARGET.lower(), "get_balance"): 500})
    direct_vm.mock_llm(r".", '{"outcome": "SATISFIED"}')

    verification_id = contract.verify_milestone(tranche_id)
    verification = json.loads(contract.get_verification(verification_id))
    assert verification["outcome"] == "SATISFIED"
    assert verification["observed_state"] == "500"


# ---------------------------------------------------------------------------
# withdraw_unallocated
# ---------------------------------------------------------------------------


def test_withdraw_unallocated_happy_path(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    direct_vm.value = 1000
    program_id = contract.create_program(GRANTEE)
    direct_vm.value = 0
    contract.register_tranche(
        program_id=program_id,
        amount=400,
        milestone_description="x",
        target_contract=TARGET,
        view_method="get_status",
    )
    contract.withdraw_unallocated(program_id)
    program = json.loads(contract.get_program(program_id))
    assert program["total_escrowed"] == "400"
    assert program["allocated"] == "400"


def test_withdraw_unallocated_rejects_non_funder(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    direct_vm.value = 1000
    program_id = contract.create_program(GRANTEE)
    direct_vm.value = 0
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("only the program's funder"):
        contract.withdraw_unallocated(program_id)


def test_withdraw_unallocated_rejects_when_nothing_unallocated(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    direct_vm.value = 1000
    program_id = contract.create_program(GRANTEE)
    direct_vm.value = 0
    contract.register_tranche(
        program_id=program_id,
        amount=1000,
        milestone_description="x",
        target_contract=TARGET,
        view_method="get_status",
    )
    with direct_vm.expect_revert("no unallocated balance"):
        contract.withdraw_unallocated(program_id)


# ---------------------------------------------------------------------------
# reclaim_stale_tranche
# ---------------------------------------------------------------------------


def test_reclaim_stale_tranche_too_early_rejected(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    _, tranche_id = _setup_program_and_tranche(contract, direct_vm)
    with direct_vm.expect_revert("not yet stale"):
        contract.reclaim_stale_tranche(tranche_id)


def test_reclaim_stale_tranche_happy_path_after_timeout(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    warp_with_message(direct_vm, "2026-01-01T00:00:00Z")
    program_id, tranche_id = _setup_program_and_tranche(contract, direct_vm)

    warp_with_message(direct_vm, "2026-04-15T00:00:00Z")  # well over 90 days later
    contract.reclaim_stale_tranche(tranche_id)

    tranche = json.loads(contract.get_tranche(tranche_id))
    assert tranche["status"] == "EXPIRED"
    program = json.loads(contract.get_program(program_id))
    assert program["allocated"] == "0"

    # unallocated funds are now withdrawable
    contract.withdraw_unallocated(program_id)
    program = json.loads(contract.get_program(program_id))
    assert program["total_escrowed"] == "0"


def test_reclaim_stale_tranche_rejects_non_funder(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    warp_with_message(direct_vm, "2026-01-01T00:00:00Z")
    _, tranche_id = _setup_program_and_tranche(contract, direct_vm)
    warp_with_message(direct_vm, "2026-04-15T00:00:00Z")

    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("only the program's funder"):
        contract.reclaim_stale_tranche(tranche_id)


def test_reclaim_stale_tranche_rejects_already_released(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    warp_with_message(direct_vm, "2026-01-01T00:00:00Z")
    _, tranche_id = _setup_program_and_tranche(contract, direct_vm)
    _mock_state_read(direct_vm, "DONE")
    direct_vm.mock_llm(r".", '{"outcome": "SATISFIED"}')
    contract.verify_milestone(tranche_id)

    warp_with_message(direct_vm, "2026-04-15T00:00:00Z")
    with direct_vm.expect_revert("not PENDING"):
        contract.reclaim_stale_tranche(tranche_id)


# ---------------------------------------------------------------------------
# View methods: unknown-id errors
# ---------------------------------------------------------------------------


def test_get_program_unknown_id_raises(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    with direct_vm.expect_revert("no program found"):
        contract.get_program("program-999")


def test_get_tranche_unknown_id_raises(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    with direct_vm.expect_revert("no tranche found"):
        contract.get_tranche("program-0-tranche-0")


def test_get_verification_unknown_id_raises(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    with direct_vm.expect_revert("no verification found"):
        contract.get_verification("program-0-tranche-0-verify-0")


def test_list_tranche_ids_unknown_program_returns_empty(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    assert json.loads(contract.list_tranche_ids("program-999")) == []


def test_list_tranches_for_grantee_rejects_invalid_address(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    with direct_vm.expect_revert("invalid grantee address"):
        contract.list_tranches_for_grantee("not-an-address")


# ---------------------------------------------------------------------------
# Pure unit tests of the deterministic helper functions
# ---------------------------------------------------------------------------


def test_extract_outcome_unit(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    mod = _module()
    assert mod._extract_outcome('{"outcome": "SATISFIED"}') == "SATISFIED"
    assert mod._extract_outcome('{"outcome": "not_satisfied"}') == "NOT_SATISFIED"
    assert mod._extract_outcome('Sure! {"outcome": "SATISFIED"} because...') == "SATISFIED"
    assert mod._extract_outcome("no json at all") == "NOT_SATISFIED"
    assert mod._extract_outcome('{"outcome": "MAYBE"}') == "NOT_SATISFIED"
    assert mod._extract_outcome({"outcome": "INSUFFICIENT_STATE"}) == "INSUFFICIENT_STATE"


def test_stringify_view_result_unit(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    mod = _module()
    assert mod._stringify_view_result("hello") == "hello"
    assert mod._stringify_view_result(42) == 42
    assert mod._stringify_view_result(True) is True
    assert mod._stringify_view_result(None) is None
    assert mod._stringify_view_result(b"\xde\xad") == "0xdead"
    assert mod._stringify_view_result([1, "a", True]) == [1, "a", True]
    assert mod._stringify_view_result({"x": 1}) == {"x": 1}

    deep = {"a": {"b": {"c": {"d": {"e": {"f": {"g": "too deep"}}}}}}}
    result = mod._stringify_view_result(deep)
    assert json.dumps(result)  # must still be JSON-safe, no exception

    long_list = list(range(200))
    result = mod._stringify_view_result(long_list)
    assert len(result) == mod.MAX_OBSERVED_STATE_ITEMS

    # Total-node budget: per-level item/depth caps alone don't bound their
    # product (50 items * 50 nested items = 2550 nodes, well within depth 6
    # but over MAX_OBSERVED_STATE_NODES=2000) -- the budget must still
    # truncate this promptly and leave the result JSON-safe.
    wide = [["x"] * mod.MAX_OBSERVED_STATE_ITEMS for _ in range(mod.MAX_OBSERVED_STATE_ITEMS)]
    result = mod._stringify_view_result(wide)
    encoded = json.dumps(result)  # must still be JSON-safe, no exception
    assert "<node budget exceeded>" in encoded


def test_validate_view_args_unit(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    mod = _module()
    assert mod._validate_view_args("[]") == []
    assert mod._validate_view_args('["a", 1, true]') == ["a", 1, True]
    with pytest.raises(Exception):
        mod._validate_view_args("[1, 2, 3, 4, 5]")  # exceeds MAX_VIEW_ARGS
    with pytest.raises(Exception):
        mod._validate_view_args("[null]")
    with pytest.raises(Exception):
        mod._validate_view_args("[[1,2]]")


def test_seconds_since_unit(direct_deploy, direct_vm):
    contract = direct_deploy(CONTRACT_PATH, sdk_version="v0.2.16")
    mod = _module()
    warp_with_message(direct_vm, "2026-01-01T00:01:40Z")
    assert mod._seconds_since("2026-01-01T00:00:00Z") == 100
    assert mod._seconds_since("not-a-date") == 0
