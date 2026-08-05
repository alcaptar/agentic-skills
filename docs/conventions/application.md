# Capa de aplicacion

Los casos de uso. Orquestan; la logica vive en el dominio y la entrada/salida detras de un puerto.

## Forma de un caso de uso

- Un modulo por caso de uso, en `application/actions/`, con el nombre del caso de uso en snake_case.
- La clase **sin coletilla**: `VerifySlice`, no `VerifySliceUseCase` ni `VerifySliceService`.
- Metodo principal `execute(params: <Name>Params) -> <Result>`.
- `<Name>Params` -y `<Name>Result` si devuelve datos- son dataclasses frozen **en el mismo modulo**.
- Las dependencias entran por constructor, con `*` para forzar el paso por nombre.
- **Depende de puertos, nunca de adaptadores.** El caso de uso no sabe que hay un subproceso al otro
  lado, ni que el diff lo calcula `git`.

```python
class VerifySlice:
    def __init__(
        self, *, reader: DiffReader, verifier: Verifier, judge: Judge, skills: SkillLibrary, corpus: Corpus
    ) -> None:
        self._reader = reader
        self._verifier = verifier
        self._judge = judge
        self._skills = skills
        self._corpus = corpus

    def execute(self, params: VerifySliceParams) -> Verification:
        ...
```

**Un value object de configuracion entra como dato, no detras de un puerto.** El `judge` de arriba es un
`Judge` ya construido que inyecta el entrypoint, igual que el agente raiz en el chat de agentes de
`mercadona/mo.staff.django-playground`. Un puerto cuyo unico metodo devuelve una constante es
indireccion: lo que se gana con el objeto es que la rubrica, las herramientas y los directorios legibles
del juez **viajen juntos** y su coherencia se pueda comprobar en un sitio.

## Lo que no hace

- **No traduce a formatos externos.** Devuelve objetos del dominio; quien serializa es la frontera.
- **No captura excepciones para convertirlas en codigos de salida.** Las propaga tipadas y las mapea
  el entrypoint.
- **No decide politica de reintentos ni de presupuesto.** Eso es una politica del dominio
  (`StateMachine`, con sus `Budgets` inyectados: ver `docs/conventions/domain.md`); quien conduce el run
  le pregunta y ejecuta lo que conteste, sin llevar contadores propios: los que gasta viajan en el `Run`
  de la transicion. `reintentos_implement` del registro durable **no** es un contador mas que nadie
  lleve: es la suma de los tres reintentos, porque esas son las unicas vueltas al paso de implementar.

## Escrituras y lecturas

**La carpeta es el discriminador**, no un sufijo en el nombre de la clase: `application/actions/` para
lo que muta estado, `application/queries/` para lo que solo lee. Si un caso de uso muta y ademas
devuelve datos, es una action: `DeliverSlice` (`application/actions/deliver_slice.py`) commitea, pushea y
abre la pull request, y **devuelve su numero**, y sigue siendo una action porque lo que la clasifica es
que muta, no que conteste.

`queries/` ya tiene su primera lectura: `RunPrechecks` (`application/queries/run_prechecks.py`), que le
pregunta a los puertos `Branches` y `Forum` si la rama o la pull request de la slice ya existen antes de
tocar codigo.

**Interrogar una politica del dominio no es una query.** El subcomando `explain` le pregunta a
`StateMachine` desde el entrypoint, sin pasar por `application/`, y es deliberado: la politica no tiene
puertos que orquestar, asi que un caso de uso que solo reenviase la llamada seria la indireccion que
rechaza el parrafo anterior. `queries/` llega con la primera lectura que **necesite un puerto** -leer el
estado del run del foro, p. ej.-, no con la primera pregunta que se le haga al dominio.

## Antipatrones

- Un caso de uso con coletilla en la clase, en `Params`, en `Result` o en el modulo.
- Un caso de uso importando de `infrastructure/`.
- Un helper privado de mapeo (`_to_dto`) en el caso de uso. **El mapeo vive en el modelo de frontera.**
- Un caso de uso que devuelve `dict`.
- Un `try/except` que traduce una excepcion de dominio a un codigo de salida.
