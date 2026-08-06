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

## Componer un value object del dominio si es trabajo del caso de uso

El antipatron de mas abajo -"un helper privado de mapeo en el caso de uso"- se refiere al mapeo hacia un
**contrato externo**: convertir a las claves que espera otro proceso es de la frontera, y hacerlo aqui
duplica el mapeo que el modelo de frontera ya posee. **Componer un value object del dominio a partir de
otros no es eso**, y es trabajo legitimo de un caso de uso.

La desviacion viva es `ImplementSlice._assignment` (`application/actions/implement_slice.py`), que arma el
`Assignment` con lo que trae la subissue (numero, identificador, intencion, criterios, senal), lo que trae
el issue padre (fuentes y controles), el worktree y los hallazgos de la vuelta anterior. Reunir esas cuatro
procedencias en el dato que el implementador necesita **es** lo que hace el caso de uso: moverlo a un
`Assignment.of(...)` -como si fuera `ChecklistEntry.of(subissue)`, que si es factoria de dominio porque
proyecta **una** entidad- dejaria a `ImplementSlice` reenviando una llamada, que es justo la indireccion que
rechaza el apartado del value object de configuracion.

La linea, para no ampliarla por precedente: si lo que se compone lleva claves de un contrato ajeno o
formato de transporte, es de la frontera; si es un objeto del dominio hecho de otros objetos del dominio,
se queda aqui.

## Antipatrones

- Un caso de uso con coletilla en la clase, en `Params`, en `Result` o en el modulo.
- Un caso de uso importando de `infrastructure/`.
- Un helper privado de mapeo (`_to_dto`) en el caso de uso. **El mapeo vive en el modelo de frontera.**
  Componer un value object del dominio a partir de otros no cuenta: ver el apartado de arriba.
- Un caso de uso que devuelve `dict`.
- Un `try/except` que traduce una excepcion de dominio a un codigo de salida.
