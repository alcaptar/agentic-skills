from __future__ import annotations

from typing import TYPE_CHECKING, Self

from slice_runner.domain.exceptions import UnreadableCallSpendLogError
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.spend_payload import SpendPayload

if TYPE_CHECKING:
    from slice_runner.domain.call_spend_log import HarnessCallSpend


class CallSpendPayload(ContractModel):
    session: str
    spend: SpendPayload
    repo: str | None = None
    issue: int | None = None
    ts: str | None = None

    @classmethod
    def from_call(cls, call: HarnessCallSpend, *, ts: str) -> Self:
        return cls(
            session=call.session, spend=SpendPayload.from_domain(call.spend), repo=call.repo, issue=call.issue, ts=ts
        )

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(data, "the spend log line is not one this program wrote", UnreadableCallSpendLogError)
