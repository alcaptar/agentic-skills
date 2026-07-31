from __future__ import annotations

import pytest

from fizzbuzz.core import fizzbuzz


class TestFizzbuzz:
    @pytest.mark.parametrize(("n", "expected"), [(15, "FizzBuzz"), (30, "FizzBuzz"), (45, "FizzBuzz")])
    def test_returns_fizzbuzz_when_divisible_by_three_and_five(self, n: int, expected: str) -> None:
        assert fizzbuzz(n) == expected

    @pytest.mark.parametrize(("n", "expected"), [(3, "Fizz"), (6, "Fizz"), (9, "Fizz")])
    def test_returns_fizz_when_divisible_by_three_only(self, n: int, expected: str) -> None:
        assert fizzbuzz(n) == expected

    @pytest.mark.parametrize(("n", "expected"), [(5, "Buzz"), (10, "Buzz"), (20, "Buzz")])
    def test_returns_buzz_when_divisible_by_five_only(self, n: int, expected: str) -> None:
        assert fizzbuzz(n) == expected

    @pytest.mark.parametrize(("n", "expected"), [(1, "1"), (2, "2"), (7, "7"), (11, "11")])
    def test_returns_the_number_as_string_when_divisible_by_neither(self, n: int, expected: str) -> None:
        assert fizzbuzz(n) == expected

    @pytest.mark.parametrize("n", [0, -1, -3, -15])
    def test_raises_value_error_when_not_positive(self, n: int) -> None:
        with pytest.raises(ValueError, match="positive"):
            fizzbuzz(n)
