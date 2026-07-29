from __future__ import annotations

import pytest

from fizzbuzz.core import fizzbuzz


@pytest.mark.parametrize(("number", "expected"), [(1, "1"), (2, "2"), (7, "7"), (11, "11")])
def test_returns_the_number_as_text_when_it_is_not_divisible_by_three_or_five(
    number: int, expected: str
) -> None:
    assert fizzbuzz(number) == expected


@pytest.mark.parametrize("number", [3, 6, 9, 33])
def test_returns_fizz_when_the_number_is_divisible_by_three_only(number: int) -> None:
    assert fizzbuzz(number) == "Fizz"


@pytest.mark.parametrize("number", [5, 10, 20, 55])
def test_returns_buzz_when_the_number_is_divisible_by_five_only(number: int) -> None:
    assert fizzbuzz(number) == "Buzz"


@pytest.mark.parametrize("number", [15, 30, 45, 90])
def test_returns_fizzbuzz_when_the_number_is_divisible_by_fifteen(number: int) -> None:
    assert fizzbuzz(number) == "FizzBuzz"


@pytest.mark.parametrize("number", [0, -1, -3, -5, -15])
def test_rejects_numbers_that_are_not_positive(number: int) -> None:
    with pytest.raises(ValueError):
        fizzbuzz(number)
