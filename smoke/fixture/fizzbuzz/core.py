from __future__ import annotations


def fizzbuzz(n: int) -> str:
    if n <= 0:
        raise ValueError(n)
    if n % 15 == 0:
        return "FizzBuzz"
    if n % 3 == 0:
        return "Fizz"
    if n % 5 == 0:
        return "Buzz"
    return str(n)
