# v0.2.16
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

"""
DeploymentStatusTarget -- illustrative reference only, not part of this
repository's tested/linted deliverable set.

Shows the OTHER HALF of an OnChainMilestoneVerifier integration: a real
target contract a grant recipient might deploy as part of their own
deliverable, exposing a plain view method a funder can point a tranche at.
Nothing here is specific to OnChainMilestoneVerifier's own code -- that is
the point. Any already-deployed GenVM contract with a view method works,
because OnChainMilestoneVerifier calls it by name at verification time
(`getattr(contract.view(state=StorageType.LATEST_FINAL), view_method)`),
not through any interface this contract declares in advance.

## The scenario

A grantee is funded to deploy and mark a project "LIVE" on Bradbury. The
funder does not want to trust the grantee's own claim that deployment
succeeded -- they want the verifier to check the grantee's own deployed
contract's own state.

    # Funder, after this contract is deployed at <target_address>:
    verifier.write().register_tranche(
        program_id="program-0",
        amount=500_000000000000000000,  # 500 GEN, in wei
        milestone_description=(
            "the target contract's deployment_status() view method "
            "returns exactly the string \"LIVE\""
        ),
        target_contract="<target_address>",
        view_method="deployment_status",
        view_args_json="[]",
    )

    # Grantee, once they believe the milestone is met:
    target.write().mark_live()

    # Either party, to settle the tranche:
    verifier.write().verify_milestone(tranche_id="program-0-tranche-0")

OnChainMilestoneVerifier's own `verify_milestone` will read
`deployment_status()` from this contract's *finalized* state -- so
`mark_live()` must itself have finalized before verification will observe
"LIVE" -- and every validator will independently agree the milestone is
satisfied only because they all observed the identical finalized value,
not because either party asserted it.
"""

from genlayer import *


class DeploymentStatusTarget(gl.Contract):
    status: str

    def __init__(self):
        self.status = "PENDING"

    @gl.public.write
    def mark_live(self) -> None:
        """Deterministic, ordinary write -- no non-determinism needed here.
        Whatever real deployment work this contract's author actually did
        off-chain, this is the on-chain fact a milestone can be gated on."""
        self.status = "LIVE"

    @gl.public.view
    def deployment_status(self) -> str:
        return self.status
