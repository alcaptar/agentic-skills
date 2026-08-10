from __future__ import annotations

import ast
import io
import shutil
import tokenize
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONVENTIONS = HERE / "conventions"
DOCUMENTS = ("code-style.md", "domain.md", "application.md", "testing.md")

MODEL = "sonnet"
TOOLS = ["Read", "Write", "Edit", "Glob", "Grep", "Skill"]
WORDS_A_TEST_NAME_NEEDS_TO_READ_AS_A_SENTENCE = 8

BRIEF = """Estas trabajando en el paquete `library`, en el directorio actual.

Anade el registro de un prestamo de libro:

- Un value object `Loan` con el identificador del libro, el del socio y los dias de prestamo.
- Un vocabulario cerrado `LoanKind` con los valores `short`, `standard` y `extended`.
- Una excepcion propia para cuando los dias pedidos no encajan con el tipo de prestamo
  (`short` admite hasta 7 dias, `standard` hasta 21, `extended` hasta 60).
- Un puerto por el que se persiste un prestamo registrado.
- Un caso de uso `RegisterLoan` que valide los dias contra el tipo y persista por el puerto.
- Los tests que fijen ese comportamiento.

No ejecutes ningun comando, no instales nada y no crees entornos: escribe los ficheros y termina.
"""

CLOSING = "\nEscribe ahora los ficheros."


class Convention:
    @staticmethod
    def text() -> str:
        return "\n\n".join(
            f"<<<<<< {name} >>>>>>\n{(CONVENTIONS / name).read_text(encoding='utf-8')}" for name in DOCUMENTS
        )

    @staticmethod
    def copy_into(destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        for name in DOCUMENTS:
            shutil.copy(CONVENTIONS / name, destination / name)


class Variant:
    @staticmethod
    def none(tree: Path) -> str:
        return BRIEF + CLOSING

    @staticmethod
    def pointer(tree: Path) -> str:
        Convention.copy_into(tree / "docs" / "conventions")
        listed = ", ".join(f"`docs/conventions/{name}`" for name in DOCUMENTS)

        return (
            BRIEF + f"\nLas convenciones de este repo son obligatorias y mandan sobre cualquier otro criterio.\n"
            f"Estan en {listed}.\n" + CLOSING
        )

    @staticmethod
    def injected(tree: Path) -> str:
        return (
            BRIEF + "\nLas convenciones de este repo son obligatorias y mandan sobre cualquier otro criterio.\n"
            "Este es su texto integro:\n\n" + Convention.text() + CLOSING
        )

    @staticmethod
    def skill(tree: Path) -> str:
        home = tree / ".claude" / "skills" / "repo-conventions"
        home.mkdir(parents=True, exist_ok=True)
        body = "\n".join(
            [
                "---",
                "name: repo-conventions",
                "description: Convenciones obligatorias de este repo para todo codigo nuevo -"
                " estilo, dominio, aplicacion y tests. Usala antes de escribir cualquier fichero .py.",
                "---",
                "",
                Convention.text(),
            ]
        )
        (home / "SKILL.md").write_text(body, encoding="utf-8")

        return (
            BRIEF + "\nLas convenciones de este repo son obligatorias y mandan sobre cualquier otro criterio.\n"
            "Viven en la skill `repo-conventions`.\n" + CLOSING
        )


VARIANTS = {
    "none": Variant.none,
    "pointer": Variant.pointer,
    "injected": Variant.injected,
    "skill": Variant.skill,
}


class Module:
    def __init__(self, path: Path, tree: Path) -> None:
        self.path = path
        self.relative = path.relative_to(tree)
        self.source = path.read_text(encoding="utf-8")
        self.lines = self.source.splitlines()
        self.node = ast.parse(self.source)

    @property
    def is_test(self) -> bool:
        return "test" in self.relative.parts[0:] and (
            self.path.name.startswith("test_") or "tests" in self.relative.parts
        )

    @property
    def is_empty(self) -> bool:
        return not self.node.body

    def classes(self) -> list[ast.ClassDef]:
        return [node for node in ast.walk(self.node) if isinstance(node, ast.ClassDef)]

    def functions(self) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
        return [node for node in ast.walk(self.node) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]

    def imported_names(self) -> set[str]:
        names = set()
        for node in ast.walk(self.node):
            if isinstance(node, ast.ImportFrom):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                names.update(alias.name.split(".")[-1] for alias in node.names)

        return names

    def has_comments(self) -> bool:
        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(self.source).readline))
        except (tokenize.TokenError, IndentationError):
            return False

        return any(token.type == tokenize.COMMENT and not token.string.startswith("#!") for token in tokens)

    def has_docstrings(self) -> bool:
        holders: list[ast.AST] = [self.node, *self.classes(), *self.functions()]

        return any(ast.get_docstring(holder) is not None for holder in holders)  # type: ignore[arg-type]


class Decorators:
    @staticmethod
    def dataclass_call(node: ast.ClassDef) -> ast.Call | None:
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and Decorators._name(decorator.func) == "dataclass":
                return decorator
            if Decorators._name(decorator) == "dataclass":
                return ast.Call(func=decorator, args=[], keywords=[])

        return None

    @staticmethod
    def names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
        return {Decorators._name(decorator) for decorator in node.decorator_list}

    @staticmethod
    def _name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr

        return ""


class Bases:
    @staticmethod
    def names(node: ast.ClassDef) -> set[str]:
        return {Decorators._name(base) for base in node.bases}


class Rules:
    def __init__(self, tree: Path) -> None:
        self.tree = tree
        self.modules = []
        for path in sorted(tree.rglob("*.py")):
            if any(part.startswith(".") or part in ("docs", "node_modules") for part in path.parts):
                continue
            try:
                self.modules.append(Module(path, tree))
            except SyntaxError:
                continue

    @property
    def production(self) -> list[Module]:
        return [module for module in self.modules if "tests" not in module.relative.parts]

    @property
    def tests(self) -> list[Module]:
        return [
            module
            for module in self.modules
            if "tests" in module.relative.parts and not module.is_empty and self._holds_tests(module)
        ]

    @property
    def domain(self) -> list[Module]:
        return [module for module in self.production if "domain" in module.relative.parts]

    @staticmethod
    def _holds_tests(module: Module) -> bool:
        return any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
            for node in ast.walk(module.node)
        )

    def all(self) -> dict[str, bool | None]:
        return {
            "no_prose": self.no_prose(),
            "no_module_functions": self.no_module_functions(),
            "future_annotations_first": self.future_annotations_first(),
            "frozen_kw_slots": self.frozen_kw_slots(),
            "strenum_vocabulary": self.strenum_vocabulary(),
            "enum_member_casing": self.enum_member_casing(),
            "port_is_abc": self.port_is_abc(),
            "exception_not_bare": self.exception_not_bare(),
            "tests_in_classes": self.tests_in_classes(),
            "no_domain_unit_tests": self.no_domain_unit_tests(),
            "mother_used": self.mother_used(),
            "long_test_names": self.long_test_names(),
            "flat_domain_layout": self.flat_domain_layout(),
            "use_case_shape": self.use_case_shape(),
            "actions_folder": self.actions_folder(),
        }

    def _use_case(self) -> tuple[Module, ast.ClassDef] | None:
        for module in self.production:
            for node in module.classes():
                if node.name == "RegisterLoan":
                    return module, node

        return None

    def use_case_shape(self) -> bool | None:
        found = self._use_case()
        if found is None:
            return None
        _, node = found
        for child in node.body:
            if not isinstance(child, ast.FunctionDef) or child.name != "execute":
                continue
            arguments = [argument for argument in child.args.args if argument.arg != "self"]
            if len(arguments) != 1 or arguments[0].annotation is None:
                return False

            return Decorators._name(arguments[0].annotation) == "RegisterLoanParams"

        return False

    def actions_folder(self) -> bool | None:
        found = self._use_case()
        if found is None:
            return None

        return found[0].relative.parts[-2:-1] == ("actions",)

    def flat_domain_layout(self) -> bool | None:
        if not self.domain:
            return None

        return all(module.relative.parts[-2] == "domain" for module in self.domain)

    def no_prose(self) -> bool | None:
        written = [module for module in self.modules if not module.is_empty]
        if not written:
            return None

        return not any(module.has_comments() or module.has_docstrings() for module in written)

    def no_module_functions(self) -> bool | None:
        written = [module for module in self.modules if not module.is_empty]
        if not written:
            return None

        return not any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for module in written for node in module.node.body
        )

    def future_annotations_first(self) -> bool | None:
        written = [module for module in self.modules if not module.is_empty]
        if not written:
            return None

        return all(self._opens_with_future(module) for module in written)

    @staticmethod
    def _opens_with_future(module: Module) -> bool:
        for node in module.node.body:
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                continue

            return isinstance(node, ast.ImportFrom) and node.module == "__future__"

        return False

    def enum_member_casing(self) -> bool | None:
        found = []
        for module in self.production:
            for node in module.classes():
                if not Bases.names(node) & {"StrEnum", "IntEnum", "Enum"}:
                    continue
                for child in node.body:
                    if not isinstance(child, ast.Assign) or not isinstance(child.value, ast.Constant):
                        continue
                    target = child.targets[0]
                    if not isinstance(target, ast.Name) or not isinstance(child.value.value, str):
                        continue
                    found.append(target.id.isupper())
        if not found:
            return None

        return all(found)

    def frozen_kw_slots(self) -> bool | None:
        found = []
        for module in self.domain:
            for node in module.classes():
                call = Decorators.dataclass_call(node)
                if call is None:
                    continue
                keywords = {keyword.arg: keyword.value for keyword in call.keywords}
                found.append(
                    all(
                        isinstance(keywords.get(flag), ast.Constant) and keywords[flag].value is True
                        for flag in ("frozen", "kw_only", "slots")
                    )
                )
        if not found:
            return None

        return all(found)

    def strenum_vocabulary(self) -> bool | None:
        for module in self.production:
            for node in module.classes():
                if node.name == "LoanKind":
                    return "StrEnum" in Bases.names(node)

        return None

    def port_is_abc(self) -> bool | None:
        for module in self.production:
            for node in module.classes():
                if "ABC" not in Bases.names(node):
                    continue
                methods = [child for child in node.body if isinstance(child, ast.FunctionDef)]
                if any("abstractmethod" in Decorators.names(method) for method in methods):
                    return True

        return False

    def exception_not_bare(self) -> bool | None:
        found = []
        for module in self.production:
            for node in module.classes():
                bases = Bases.names(node)
                if not (node.name.endswith("Error") or node.name.endswith("Exception") or bases & {"Exception"}):
                    continue
                found.append("Exception" not in bases)
        if not found:
            return None

        return all(found)

    def tests_in_classes(self) -> bool | None:
        if not self.tests:
            return None

        return not any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
            for module in self.tests
            for node in module.node.body
        )

    def no_domain_unit_tests(self) -> bool | None:
        if not self.tests:
            return None
        for module in self.tests:
            names = module.imported_names()
            if names & {"Loan", "LoanKind"} and "RegisterLoan" not in names:
                return False

        return True

    def mother_used(self) -> bool | None:
        if not self.tests:
            return None

        return any(path.name.endswith("_mother.py") for path in self.tree.rglob("*_mother.py"))

    def long_test_names(self) -> bool | None:
        names = [
            node.name
            for module in self.tests
            for node in ast.walk(module.node)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
        ]
        if not names:
            return None
        words = [len(name.split("_")) - 1 for name in names]

        return sum(words) / len(words) >= WORDS_A_TEST_NAME_NEEDS_TO_READ_AS_A_SENTENCE


def measure(tree: Path) -> dict[str, bool | None]:
    return Rules(tree).all()
