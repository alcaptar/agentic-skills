from __future__ import annotations

from slice_runner.infrastructure.contract_model import ContractModel


class PermissionDenial(ContractModel):
    tool_name: str
    tool_use_id: str
    tool_input: dict[str, object]

    @property
    def denied_read(self) -> str:
        target = self.tool_input.get("file_path") or self.tool_input.get("path")

        return f"{self.tool_name} {target}" if isinstance(target, str) else self.tool_name
