from __future__ import annotations

from enum import StrEnum


class InstalledCodeMatch(StrEnum):
    SAME = "same"
    DIFFERENT = "different"
    CHECKOUT_GONE = "checkout-gone"
