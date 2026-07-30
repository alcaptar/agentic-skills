from __future__ import annotations

import pytest

from fizzbuzz.core import fizzbuzz


def test_returns_fizz_for_multiples_of_three() -> None:
    assert fizzbuzz(3) == "Fizz"
    assert fizzbuzz(9) == "Fizz"


def test_returns_buzz_for_multiples_of_five() -> None:
    assert fizzbuzz(5) == "Buzz"
    assert fizzbuzz(20) == "Buzz"


def test_returns_fizzbuzz_for_multiples_of_fifteen() -> None:
    assert fizzbuzz(15) == "FizzBuzz"
    assert fizzbuzz(30) == "FizzBuzz"


def test_returns_the_number_as_text_when_divisible_by_neither_three_nor_five() -> None:
    assert fizzbuzz(1) == "1"
    assert fizzbuzz(7) == "7"


def test_rejects_zero() -> None:
    with pytest.raises(ValueError):
        fizzbuzz(0)


def test_rejects_negative_numbers() -> None:
    with pytest.raises(ValueError):
        fizzbuzz(-1)
    with pytest.raises(ValueError):
        fizzbuzz(-15)
