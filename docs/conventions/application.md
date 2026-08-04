# Capa de aplicacion

Los casos de uso. Orquestan; la logica vive en el dominio y la entrada/salida detras de un puerto.

## Forma de un caso de uso

- Un modulo por caso de uso, en `application/`, con el nombre del caso de uso en snake_case.
- La clase **sin coletilla**: `VerifySlice`, no `VerifySliceUseCase` ni `VerifySliceService`.
- Metodo principal `execute(params: <Name>Params) -> <Result>`.
- `<Name>Params` -y `<Name>Result` si devuelve datos- son dataclasses frozen **en el mismo modulo**.
- Las dependencias entran por constructor, con `*` para forzar el paso por nombre.
- **Depende de puertos, nunca de adaptadores.** El caso de uso no sabe que hay un subproceso al otro
  lado, ni que el diff se materializa con `git`.

```python
class VerifySlice:
    def __init__(self, *, bundler: DiffBundler, verifier: Verifier) -> None:
        self._bundler = bundler
        self._verifier = verifier

    def execute(self, params: VerifySliceParams) -> Verdict:
        ...
```

## Lo que no hace

- **No traduce a formatos externos.** Devuelve objetos del dominio; quien serializa es la frontera.
- **No captura excepciones para convertirlas en codigos de salida.** Las propaga tipadas y las mapea
  el entrypoint.
- **No decide politica de reintentos ni de presupuesto** mientras eso siga viviendo en la skill.

## Direccion a seguir

Cuando aparezca la primera **lectura** (leer el estado de un issue, por ejemplo), separar
`application/actions/` (escrituras) de `application/queries/` (lecturas), con la carpeta como
discriminador y sin sufijo en el nombre de la clase. Es la convencion de la casa
(`mo.arcen-pi`). Hoy hay un solo caso de uso y la carpeta seria estructura sin sujeto.

## Antipatrones

- Un caso de uso con coletilla en la clase, en `Params`, en `Result` o en el modulo.
- Un caso de uso importando de `infrastructure/`.
- Un helper privado de mapeo (`_to_dto`) en el caso de uso. **El mapeo vive en el modelo de frontera.**
- Un caso de uso que devuelve `dict`.
- Un `try/except` que traduce una excepcion de dominio a un codigo de salida.
