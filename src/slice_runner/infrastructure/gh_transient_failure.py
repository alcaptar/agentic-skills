from __future__ import annotations

from typing import ClassVar


class GhTransientFailure:
    MARKERS: ClassVar[frozenset[str]] = frozenset(
        {
            "connection reset",
            "connection refused",
            "tls handshake",
            "i/o timeout",
            "context deadline exceeded",
            "unexpected eof",
            "temporary failure in name resolution",
            "dial tcp",
            "no such host",
            "network is unreachable",
            "secondary rate limit",
            "api rate limit exceeded",
            "internal server error",
            "bad gateway",
            "service unavailable",
            "gateway timeout",
        }
    )

    @classmethod
    def of(cls, stderr: str) -> bool:
        lowered = stderr.lower()

        return any(marker in lowered for marker in cls.MARKERS)
