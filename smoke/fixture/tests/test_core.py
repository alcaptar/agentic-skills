from __future__ import annotations

import pytest

from fizzbuzz.core import fizzbuzz


def test_returns_fizzbuzz_for_multiples_of_fifteen() -> None:
    assert fizzbuzz(15) == "FizzBuzz"


def test_returns_fizz_for_multiples_of_three_only() -> None:
    assert fizzbuzz(9) == "Fizz"


def test_returns_buzz_for_multiples_of_five_only() -> None:
    assert fizzbuzz(20) == "Buzz"


def test_returns_the_number_as_text_when_divisible_by_neither_three_nor_five() -> None:
    assert fizzbuzz(7) == "7"


@pytest.mark.parametrize("n", [0, -3])
def test_rejects_numbers_that_are_not_positive(n: int) -> None:
    with pytest.raises(ValueError):
        fizzbuzz(n)
