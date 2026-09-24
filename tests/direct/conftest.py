"""Test-harness-only compatibility shims. None of these touch any contract
or the real GenVM SDK -- they work around gaps in gltest's direct-mode
mock specific to this project's needs.
"""

import os

_original_unlink = os.unlink


def _safe_unlink(path, *args, **kwargs):
    try:
        _original_unlink(path, *args, **kwargs)
    except PermissionError:
        pass


os.unlink = _safe_unlink


def install_call_contract_mock(vm, responses):
    """Installs a vm._gl_call_hook that answers CallContract gl_call
    requests with caller-supplied canned values, keyed by
    (address_hex_lowercase, method_name). gltest's direct-mode has no
    built-in mock for cross-contract calls (unlike vm.mock_web/vm.mock_llm
    for web/LLM calls) -- this is a project-specific mock built directly
    against the same raw-bytes response format wasi_mock.py's own
    RunNondet handler uses (a leading ResultCode byte + calldata.encode
    (value)), reverse-engineered from the installed SDK/gltest source and
    confirmed working via a standalone probe test before this contract was
    written.

    `responses` maps (address_hex_lowercase, method_name) -> return value
    (or -> Exception instance, to simulate the target raising/reverting).
    Call again to replace the mapping; keys not present simply fail the
    call (matches a real target contract/method that doesn't exist).
    """
    import genlayer.calldata as calldata

    def hook(vm_ctx, request):
        if not isinstance(request, dict) or "CallContract" not in request:
            return None
        call = request["CallContract"]
        address_hex = str(call["address"]).lower()
        # v0.3.0's _make_calldata_obj stores the method name under the
        # empty-string key (`ret[''] = method`), not `"method"` -- a real
        # finding, confirmed by reading genlayer/contract/__init__.py
        # directly rather than assuming the pre-migration key still held.
        method_name = call["calldata"].get("")
        key = (address_hex, method_name)
        if key not in responses:
            return None
        outcome = responses[key]
        if isinstance(outcome, Exception):
            return bytes([1]) + str(outcome).encode("utf-8")
        return bytes([0]) + calldata.encode(outcome)

    vm._gl_call_hook = hook


def warp_with_message(vm, iso_timestamp: str) -> None:
    """vm.warp() alone patches datetime.datetime.now() (via a
    _WarpedDatetime subclass) but does NOT update the live
    genlayer.message module's `raw["datetime"]` -- confirmed by reading
    gltest's own direct/vm.py: warp() calls self._refresh_gl_message(),
    which calls direct/sdk_compat.py's sync_message_context(), which
    updates sender_address/origin_address/value/chain_id on the real
    genlayer.message module (and its raw dict) but deliberately excludes
    datetime (not one of its accepted kwargs). This is the SAME gap this
    account has hit before under the pre-v0.3.0 gl.message_raw module,
    just relocated to genlayer.message.raw under the v0.3.0 API -- a
    contract reading gl.message.raw["datetime"] directly (the
    transaction-canonical timestamp, preferred over datetime.now() for
    anything stored/consensus-relevant) would otherwise see a frozen
    deploy-time value no matter how many later vm.warp() calls happen.
    This helper does both: warps the VM AND directly patches the
    already-imported genlayer.message module's raw dict, scoped to this
    test file only, never touching the contract or the real SDK."""
    import sys

    vm.warp(iso_timestamp)
    message_module = sys.modules.get("genlayer.message")
    if message_module is not None and hasattr(message_module, "raw"):
        message_module.raw["datetime"] = iso_timestamp
