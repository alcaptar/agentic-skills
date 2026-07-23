from __future__ import annotations

import pytest

from fizzbuzz.core import fizzbuzz


def test_multiple_of_fifteen_returns_fizzbuzz() -> None:
    assert fizzbuzz(15) == "FizzBuzz"


def test_multiple_of_three_returns_fizz() -> None:
    assert fizzbuzz(9) == "Fizz"


def test_multiple_of_five_returns_buzz() -> None:
    assert fizzbuzz(10) == "Buzz"


def test_other_number_returns_its_string() -> None:
    assert fizzbuzz(7) == "7"


def test_non_positive_raises_value_error() -> None:
    with pytest.raises(ValueError):
        fizzbuzz(0)
