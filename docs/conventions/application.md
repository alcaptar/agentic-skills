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

## Desviacion declarada: el conductor agrupa sus dependencias

`ConductSlice` (`application/actions/conduct_slice.py`) **no** lista sus dependencias sueltas: las recibe
en dos dataclasses frozen del propio modulo, `ConductSliceUseCases` (los seis casos de uso) y
`ConductSlicePorts` (los once puertos), mas `machine` y `budgets` sueltos. Sigue entrando todo por
constructor y todo por nombre; lo que cambia es que llegan en dos paquetes.

El motivo es que quince parametros disparan `PLR0913` de `ruff`, y las dos salidas que **no** valen son
relajar la configuracion del linter -mover la vara para que pase el codigo- y partir el conductor en
piezas que no existen por diseno sino por contar argumentos. Agrupar por rol -lo que orquesta y lo que
hace entrada/salida- deja la firma legible y no esconde ninguna dependencia: siguen siendo tipos del
dominio y de aplicacion, y la costura de test sigue siendo el constructor.

**La linea, para que no se amplie por precedente:** esto es del **conductor**, que es la unica pieza que
compone casi todos los puertos del programa. Una action normal sigue listando sus dependencias sueltas
como el ejemplo de arriba, y un caso de uso que llegue a necesitar el agrupamiento esta diciendo que hace
demasiado: la respuesta por defecto ahi es partirlo, no empaquetarle los argumentos.

## Lo que no hace

- **No traduce a formatos externos.** Devuelve objetos del dominio; quien serializa es la frontera.
- **No captura excepciones para convertirlas en codigos de salida.** Las propaga tipadas y las mapea
  el entrypoint.
- **No decide politica de reintentos ni de presupuesto.** Eso es una politica del dominio
  (`StateMachine`, con sus `Budgets` inyectados: ver `docs/conventions/domain.md`); quien conduce el run
  le pregunta y ejecuta lo que conteste. **Los contadores que no lleva son los de reintento y los de
  presupuesto de fase**: esos viajan en el `Run` de la transicion y el conductor ni los suma ni los
  compara. `reintentos_implement` del registro durable **no** es un contador mas que nadie lleve: es la
  suma de los tres reintentos, porque esas son las unicas vueltas al paso de implementar.

  Lo que **si** acumula por invocacion son cuatro, y los cuatro estan declarados fuera de aqui:
  `ConductSliceProgress.waited_seconds` -porque el tope de espera acota la invocacion y no el run
  (`docs/conventions/domain.md`)-, `ConductSliceProgress.spends` -porque el gasto todavia no viaja en el
  `Run` persistido, que es deuda declarada en `docs/conventions/infrastructure.md`-,
  `ConductSliceProgress.verdicts` -porque la fila durable cuenta los hallazgos de **todas** las vueltas del
  juez y los intermedios no los ve nadie mas- y `ConductSliceProgress.control_rounds` -porque cada ronda
  de controles necesita su propio directorio de log (`round-N`) para que el de la ronda que cierra el run
  no se sobrescriba con el de la siguiente, y el conductor es quien sabe cuantas rondas lleva dadas-. Los
  dos primeros se los pasa a `Budgets` para que decida; seguir sin llevar el numero seria imposible,
  porque nadie mas los ve.

  De los veredictos acumulados salen las **dos vistas** que el conductor necesita, y son propiedades y no
  campos a proposito: `findings_of_the_last_round` es lo que la vuelta siguiente tiene que arreglar -las
  vueltas anteriores pueden estar ya corregidas, asi que mandarlas al implementador seria mandarle trabajo
  hecho- y `findings_of_every_round` es lo que se escribe al cerrar. Llevar los dos como campos guardaria
  dos veces el mismo dato y dejaria que uno se quedase viejo.

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
