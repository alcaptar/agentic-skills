"""Punto de entrada del programa. Desde la raiz del repo:

    PYTHONPATH=src:skills/slice-runner/scripts \\
        uv run python -m slice_runner verificar --repo <ruta> --base <rama>

Las dos rutas hacen falta por dos motivos distintos, y las dos son transitorias. `src` porque el
repo sigue con `package = false`: uv no instala el proyecto y `python -m` solo mira el directorio
actual, asi que hasta que exista el ejecutable instalable el paquete se encuentra a mano. Los
scripts porque el programa reutiliza `controles` -`diff-bundle` y `verify-verdict`- por importacion
mientras su logica siga viviendo alli.
"""

from __future__ import annotations

import sys

from slice_runner.infrastructure.cli import main

if __name__ == "__main__":
    sys.exit(main())
