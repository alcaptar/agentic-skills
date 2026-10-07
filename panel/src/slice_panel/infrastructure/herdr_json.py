from __future__ import annotations

import json

from slice_panel.infrastructure.herdr_payload_rejected import HerdrPayloadRejectedError


class HerdrJson:
    @staticmethod
    def loaded(text: str, *, expected: str) -> object:
        try:
            return json.loads(text)
        except json.JSONDecodeError as error:
            raise HerdrPayloadRejectedError(f"herdr answered {expected} with something that is not JSON") from error

    @staticmethod
    def at(data: object, *path: str) -> object:
        for key in path:
            if not isinstance(data, dict) or key not in data:
                return None
            data = data[key]

        return data
