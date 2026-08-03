"""El orquestador de slices como programa.

Capas y sentido de las dependencias, como en `mercadona/mo.boilerplate.fastapi`: `domain` no
importa nada de fuera, `application` orquesta sobre los puertos del dominio, y `infrastructure`
implementa esos puertos y es la unica que sabe que detras hay `git`, `gh` y `claude -p`. Los tests
viven dentro del paquete espejando el arbol (`slice_runner.tests.<capa>`).
"""
