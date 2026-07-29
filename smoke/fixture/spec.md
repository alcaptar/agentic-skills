# Spec de smoke test

## Intencion

Hoy este repo de smoke no tiene ninguna funcion que ejercitar, asi que no hay forma de
comprobar de punta a punta que el flujo de slice-runner funciona contra GitHub de verdad.

## Slices

- [ ] slice-01 (fizzbuzz-core): Implementar `fizzbuzz(n: int) -> str` en `fizzbuzz/core.py` [pendiente]
      INTENCION: sin esta funcion no hay nada que implementar, y el smoke no puede ejercitar el ciclo completo
      ACEPTACION: n divisible por 15 -> "FizzBuzz"; divisible por 3 -> "Fizz"; divisible por 5 -> "Buzz"; resto -> str(n); n <= 0 lanza ValueError. Tests en tests/test_core.py.
      SENAL: exenta - libreria pura sin despliegue ni runtime en produccion que observar
