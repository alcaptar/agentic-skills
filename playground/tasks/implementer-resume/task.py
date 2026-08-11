from __future__ import annotations

import ast
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONVENTIONS = HERE / "conventions"
DOCUMENTS = ("code-style.md", "domain.md", "application.md", "testing.md")

MODEL = "sonnet"
TOOLS = ["Read", "Write", "Edit", "Glob", "Grep"]
USES_A_DEPENDENCY_TWICE = 2

BRIEF = """Estas trabajando en el paquete `library`, en el directorio actual.

Anade el registro de un prestamo de libro:

- Un value object `Loan` con el identificador del libro, el del socio y los dias de prestamo.
- Un vocabulario cerrado `LoanKind` con los valores `short`, `standard` y `extended`.
- Una excepcion propia para cuando los dias pedidos no encajan con el tipo de prestamo
  (`short` admite hasta 7 dias, `standard` hasta 21, `extended` hasta 60).
- Un puerto por el que se persiste un prestamo registrado.
- Un caso de uso `RegisterLoan` que valide los dias contra el tipo y persista por el puerto.
- Los tests que fijen ese comportamiento.

Las convenciones del repo estan en `docs/conventions/`. Leelas antes de escribir.

No ejecutes ningun comando, no instales nada y no crees entornos: escribe los ficheros y termina.
"""

VETO = """El juez ha revisado el diff y ha vetado la slice. Dos hallazgos, los dos bloqueantes:

1. [alta] la-validacion-vive-en-el-value-object: la comprobacion de que los dias encajan con el tipo
   de prestamo esta en el caso de uso. Es una invariante del propio prestamo: un `Loan` con dias que
   no encajan con su tipo no deberia poder existir. Muevela al value object, de modo que construirlo
   con dias invalidos falle, y deja el caso de uso sin esa comprobacion.

2. [alta] falta-la-renovacion: la feature no esta entera sin poder renovar un prestamo ya registrado.
   Anade un caso de uso `RenewLoan` que lea el prestamo por el puerto, le sume los dias pedidos
   respetando el tope de su tipo, y lo persista; con su test.

Corrige las dos cosas y termina. No ejecutes ningun comando.
"""


class Variant:
    @staticmethod
    def _with_the_conventions_on_disk(tree: Path) -> str:
        destination = tree / "docs" / "conventions"
        destination.mkdir(parents=True, exist_ok=True)
        for name in DOCUMENTS:
            (destination / name).write_text((CONVENTIONS / name).read_text(encoding="utf-8"), encoding="utf-8")

        return BRIEF

    @staticmethod
    def fresh(tree: Path) -> str:
        return Variant._with_the_conventions_on_disk(tree)

    @staticmethod
    def resumed(tree: Path) -> str:
        return Variant._with_the_conventions_on_disk(tree)


VARIANTS = {
    "fresh": Variant.fresh,
    "resumed": Variant.resumed,
}

RESUMES = ("resumed",)


def CORRECTION(tree: Path) -> str:  # noqa: N802 - el arnes lo lee por nombre
    _ = tree

    return VETO


class Rules:
    def __init__(self, tree: Path) -> None:
        self.tree = tree
        self.modules = {path: self._parsed(path) for path in tree.rglob("*.py")}

    @staticmethod
    def _parsed(path: Path) -> ast.Module | None:
        try:
            return ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            return None

    def _under(self, folder: str) -> dict[Path, ast.Module]:
        return {path: tree for path, tree in self.modules.items() if tree is not None and folder in path.parts}

    def _classes(self, folder: str) -> dict[str, tuple[Path, ast.ClassDef]]:
        found: dict[str, tuple[Path, ast.ClassDef]] = {}
        for path, tree in self._under(folder).items():
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    found[node.name] = (path, node)

        return found

    def renewal_exists(self) -> bool:
        return "RenewLoan" in self._classes("application")

    def renewal_reads_and_writes_through_the_port(self) -> bool | None:
        found = self._classes("application").get("RenewLoan")
        if found is None:
            return None
        source = ast.unparse(found[1])

        return source.count("self._") >= USES_A_DEPENDENCY_TWICE

    def renewal_has_a_test(self) -> bool:
        for path, tree in self._under("tests").items():
            _ = path
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                    if "renew" in ast.unparse(node).lower():
                        return True

        return False

    def the_value_object_raises_on_bad_days(self) -> bool | None:
        found = self._classes("domain").get("Loan")
        if found is None:
            return None

        return any(isinstance(node, ast.Raise) for node in ast.walk(found[1]))

    def the_use_case_no_longer_validates(self) -> bool | None:
        found = self._classes("application").get("RegisterLoan")
        if found is None:
            return None

        return not any(isinstance(node, ast.Raise) for node in ast.walk(found[1]))

    def nothing_in_the_domain_imports_infrastructure(self) -> bool:
        for tree in self._under("domain").values():
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module and "infrastructure" in node.module:
                    return False

        return True

    def all(self) -> dict[str, bool | None]:
        return {
            "renewal_exists": self.renewal_exists(),
            "renewal_reads_and_writes_through_the_port": self.renewal_reads_and_writes_through_the_port(),
            "renewal_has_a_test": self.renewal_has_a_test(),
            "the_value_object_raises_on_bad_days": self.the_value_object_raises_on_bad_days(),
            "the_use_case_no_longer_validates": self.the_use_case_no_longer_validates(),
            "nothing_in_the_domain_imports_infrastructure": self.nothing_in_the_domain_imports_infrastructure(),
        }


def measure(tree: Path) -> dict[str, bool | None]:
    return Rules(tree).all()
