from __future__ import annotations

import pytest

from fizzbuzz.core import fizzbuzz


def test_returns_the_number_itself_when_not_divisible_by_three_or_five() -> None:
    assert fizzbuzz(7) == "7"


def test_returns_fizz_when_divisible_by_three_only() -> None:
    assert fizzbuzz(9) == "Fizz"


def test_returns_buzz_when_divisible_by_five_only() -> None:
    assert fizzbuzz(10) == "Buzz"


def test_returns_fizzbuzz_when_divisible_by_fifteen() -> None:
    assert fizzbuzz(30) == "FizzBuzz"


def test_rejects_zero() -> None:
    with pytest.raises(ValueError):
        fizzbuzz(0)


def test_rejects_negative_numbers() -> None:
    with pytest.raises(ValueError):
        fizzbuzz(-3)
