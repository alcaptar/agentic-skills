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

## Desviacion declarada: agrupar dependencias cuando la lista de puertos es el trabajo

Un caso de uso puede recibir sus dependencias **agrupadas por rol** en dataclasses frozen de su propio
modulo -lo que orquesta por un lado, lo que hace entrada/salida por otro-, en vez de listarlas sueltas
como el ejemplo de arriba. Sigue entrando todo por constructor y todo por nombre; lo que cambia es que
llegan empaquetadas.

El motivo es que una firma con esa cantidad de parametros dispara `PLR0913` de `ruff`, y las dos salidas
que **no** valen son relajar la configuracion del linter -mover la vara para que pase el codigo- y partir
la pieza en trozos que no existen por diseno sino por contar argumentos. Agrupar por rol deja la firma
legible y no esconde ninguna dependencia: siguen siendo tipos del dominio y de aplicacion, y la costura
de test sigue siendo el constructor.

**La linea, para que no se amplie por precedente: lo que autoriza el agrupamiento es de que es
proporcional la lista de puertos, no cuanto mide la firma.** Cuando la lista crece con el numero de
responsabilidades, la firma larga es el sintoma y la respuesta sigue siendo partir el caso de uso. Cuando
crece con **lo que ese caso de uso existe para recorrer** -dirigir un flujo de punta a punta, contestar si
todas las piezas de un sistema estan en su sitio-, partirlo no quita ni un puerto: reparte la misma lista
entre dos piezas y anade una tercera que las componga. Quien agrupe tiene que poder nombrar que recorre;
si no puede nombrarlo, esta agrupando para callar al linter.

## Dejar constancia no es conducir

**Quien decide el flujo no compone la telemetria.** El caso de uso que orquesta un proceso largo decide
**cuando** hay que dejar constancia de un paso; **como** se deja constancia -que se persiste para poder
reanudar, que estado se publica, que se emite, que fila resume el proceso al cerrarse- es de otro caso de
uso, al que invoca como a cualquiera.

La regla se aplica cuando quien orquesta tendria que **nombrar tipos de telemetria** para construirlos.
Mientras solo pase datos a un puerto, no hay nada que extraer.

- **Quien compone un registro posee las reglas de que entra en el.** Si un dato no se pudo medir, decidir
  que no entra -en vez de escribir un cero- es suyo, no de cada llamador: una regla repartida entre los
  sitios que cierran un proceso acaba escrita en unos y no en otros.
- **Un puerto compartido no se saca solo porque el registro lo use.** Quien orquesta conserva los puertos
  que necesita para lo demas; extraerlos enteros obligaria a inventar un caso de uso por cada lectura.

Lo que se gana no es tamano de fichero: es que un cambio en el registro y un cambio en el flujo dejen de
tocar la misma pieza. La medicion que lo sostiene, en `docs/design-notes.md`.

## Lo que no hace

- **No traduce a formatos externos.** Devuelve objetos del dominio; quien serializa es la frontera.
- **No captura excepciones para convertirlas en codigos de salida.** Las propaga tipadas y las mapea
  el entrypoint.
- **No decide politica de reintentos ni de presupuesto.** Eso es una politica del dominio
  (`StateMachine`, con sus `Budgets` inyectados: ver `docs/conventions/domain.md`); quien conduce el run
  le pregunta y ejecuta lo que conteste. **Los contadores que no lleva son los de reintento y los de
  presupuesto de fase**: esos viajan en el `Run` de la transicion y el conductor ni los suma ni los
  compara. `reintentos_implement` del registro durable **no** es un contador mas que nadie lleve: es la
  suma de los reintentos que devuelven el trabajo al paso de implementar, y se deriva de ellos.

  **Lo unico que el conductor acumula por invocacion es lo que nadie mas ve**, y cada acumulador lleva su
  motivo escrito donde vive: lo que acota la invocacion y no el run, lo que todavia no viaja en el `Run`
  persistido, y lo que necesita la fila durable al cerrar. Un acumulador nuevo sin ese motivo es estado
  del conductor que deberia estar en el `Run`.

  De los veredictos acumulados salen **vistas, no campos**, y a proposito: lo que la vuelta siguiente tiene
  que arreglar son los hallazgos de la ultima ronda -las anteriores pueden estar ya corregidas, asi que
  mandarlas al implementador seria mandarle trabajo hecho-, y lo que se escribe al cerrar son los de todas.
  Llevar las dos cosas como campos guardaria dos veces el mismo dato y dejaria que una se quedase vieja.

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

El caso vivo es el armado del `Assignment` del implementador, que reune lo que declara la subissue, lo que
declara el issue padre, el worktree y los hallazgos de la vuelta anterior. Reunir procedencias distintas en
el dato que otro necesita **es** lo que hace el caso de uso: moverlo a una factoria de dominio -que proyecta
**una** entidad- dejaria al caso de uso reenviando una llamada, que es justo la indireccion que rechaza el
apartado del value object de configuracion.

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
