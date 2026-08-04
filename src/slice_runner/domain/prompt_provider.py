from __future__ import annotations

from abc import ABC, abstractmethod


class PromptProvider(ABC):
    @abstractmethod
    def system_template(self) -> str: ...
