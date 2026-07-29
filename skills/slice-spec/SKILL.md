---
name: slice-spec
description: Crea (o valida) una spec de slices en el formato exacto que consume slice-runner. Usar cuando el usuario quiera "escribir una spec", "montar el plan de slices", "trocear una feature en slices", "slice-spec", o tenga una idea/feature y necesite convertirla en una spec ejecutable por slice-runner. Envuelve superpowers:brainstorming para el diseno y luego emite la spec en su formato exacto (checklist de slices con nombre y criterios de aceptacion). Modo `validate` para revisar una spec existente contra el contrato. No implementa codigo: produce la spec que slice-runner luego ejecuta.
---

# Slice Spec

STARTER_CHARACTER = [slice-spec]

Emite `[slice-spec]` al inicio de cada respuesta mientras ejecutas este proceso, como testigo de que el contexto esta intacto y sigues estas reglas. (Marcador de texto en lugar de emoji por preferencia del usuario.)

## Description

Skill fina que produce la **spec** que `slice-runner` consume, en su formato exacto. No re-piensa
el diseno del producto: **delega el diseno en `superpowers:brainstorming`** y su unico trabajo es
el **contrato de formato** (los nombres de slice, los criterios de aceptacion, las lineas de slice
que `slice-runner` sabe parsear). Es el `check-alignment` + `text-native` del flujo: la spec es el
artefacto compartido entre humano y agente, y **vive en un issue de GitHub** (una feature = un issue).

Par natural: `/slice-spec` crea el issue con la spec, `/slice-runner #N` lo ejecuta.

Dos modos:

- **Autoria (por defecto):** brainstorming -> crea el issue de GitHub con la spec bien formada.
- **`validate`:** revisa una spec existente (issue o borrador) contra el contrato y reporta (o corrige) desviaciones.

## Principios

- **No implementa.** No escribe codigo ni tests; produce la spec. El estado terminal es una spec
  valida, no un plan de `writing-plans` ni una PR.
- **El diseno lo lleva brainstorming.** No dupliques su trabajo (entender intencion, proponer
  enfoques, validar diseno). Esta skill reengancha solo la **cola**: cuando el diseno esta
  aprobado, en vez de `writing-plans` emite la spec de slices. La spec ES el plan que consume
  slice-runner.
- **Formato es contrato.** La spec debe parsearla `slice-runner` (via `scripts/issue_body.py`) sin
  ambiguedad. Si no cumple el contrato de abajo, no esta terminada.
- **Cada slice tiene nombre.** `name` kebab-case, estable, determinista: alimenta rama y scope de
  commit en slice-runner. Sin nombre no hay spec bien formada.
- **Guia el corte, no lo delega.** El troceo lo lleva esta skill cargando su cerebro de slicing
  (`references/slicing.md`): walking skeleton, heuristica ordenada, hamburger como motor de
  composicion, calibrador de tamano y validacion del corte. La skill es la **fuente de verdad** del
  slicing; `hamburger-method`/`story-splitting` son profundizacion opcional, no el motor.
- **Slices verticales y pequenas.** Cada slice es una rebanada entregable de punta a punta con
  criterios de aceptacion propios, no una capa tecnica suelta.
- **La intencion es parte de la spec, y es lo primero que se lee.** El issue abre con una seccion
  `## Intencion` (que esta mal hoy, o que no se puede hacer hoy, a quien le pasa y como se nota) y
  cada slice declara su linea `INTENCION:` (que deja de estar mal cuando esa slice entra). No es
  decoracion: es lo que acaba en el cuerpo de cada pull request, en lugar de un resumen del codigo
  -que el diff ya cuenta mejor-. **Vara: el coste de no hacerlo.** Si borras la slice, ¿que queda
  roto o imposible? Si no puedes nombrarlo, la linea es relleno y hay que reescribirla:
  `INTENCION: hoy se pueden pedir cantidades negativas y el stock queda en negativo sin que nadie
  se entere` cumple la vara; `INTENCION: mejorar la validacion del dominio` no (borrala y no queda
  nada roto que puedas nombrar). A diferencia de `SENAL:`, **no hay figura de exencion**: una slice
  sin por que no deberia existir. Las slices sin efecto observable en produccion (refactor, value
  object interno) tambien tienen intencion; su coste es interno, pero se puede nombrar.
- **Criterios de aceptacion obligatorios y falsables.** Sin ellos no hay control de verificacion en
  slice-runner: toda slice declara criterios concretos. **Vara de falsabilidad:** un criterio vale
  si puedes nombrar el **cambio de produccion que lo haria fallar**; si no puedes nombrarlo, es
  prosa y hay que reescribirlo. Es la contraparte upstream de "los tests son ciudadanos de primera
  categoria" de slice-runner: su verificador bloquea con severidad alta el mapeo criterio↔test, y
  ese check solo tiene con que medir si el criterio es falsable.
- **La observabilidad es parte del corte, no un extra.** Toda slice que cambia comportamiento
  observable en produccion declara su linea `SENAL:`: **como se comprueba viva**. Es la contraparte
  post-deploy de los criterios de aceptacion — estos los verifica un test antes de mergear, la senal
  la verifica `deploy-watch` despues— y la misma vara de falsabilidad aplicada al otro extremo:
  *nombra la senal que cambiaria si esto se rompe vivo*. Si no puedes nombrarla, la slice no es
  observable, y eso se arregla **en el slicing**, no en el incidente. Las exentas (refactor puro, VO
  interno, migracion sin efecto visible) lo declaran con motivo: `SENAL: exenta - <motivo>`;
  ausencia silenciosa no es exencion. El detalle vive en `references/observabilidad.md` (escalera
  para decidir si hay que instrumentar o la senal ya existe, stack concreto, redaccion de la linea).
- **Alertas y paneles son slices propias, en su repo.** Una alerta o un panel no van nunca en la PR de
  la metrica que consumen (repos distintos ⇒ PRs distintas), y el orden es forzoso: primero la slice
  que emite la serie, luego la alerta, luego el panel. Se declaran con `REPO:` en su linea.
- **Declara las fuentes de convencion.** La spec incluye una seccion `## Fuentes de convencion` con
  **punteros** (no contenido) a la vara de medir del repo: docs de convencion y skills de proyecto.
  slice-runner las lee para que implementador y verificador midan contra las convenciones **reales**
  del repo, no contra defaults genericos ni contra como quedo una slice anterior. No se asumen rutas
  fijas: se **descubren** por repo (paso 3) y las **confirma la persona**. Sin esta seccion,
  slice-runner para y no ejecuta con la vara vacia (evita el `silent-misalignment` de trabajar sin
  criterio y no avisar).
- **Declara los controles.** Si las fuentes son la vara, la seccion `## Controles` son **los comandos
  con los que se mide**: `lint`, `types`, `tests` y lo que el repo tenga. Tambien se descubren y se
  confirman (paso 3b), y por el mismo motivo: antes los deducia `slice-runner` leyendo el `Makefile`
  al empezar cada slice, lo que le metia el toolchain del repo en el contexto que debe durar todo el
  run y no dejaba rastro que nadie pudiera revisar. Declarados aqui, la vara es **texto publico** que
  ninguna slice puede debilitar en privado.
- **La spec vive en el issue de GitHub.** `slice-spec` crea el issue (1 issue = 1 feature): es la
  fuente de verdad duradera del estado, no un fichero en el repo. No la guardes en `docs/` ni la comitees.

## Contrato de formato (lo que el script espera)

La spec es un **checklist de slices**. Un solo formato, sin variantes.

```markdown
# <titulo de la feature>

## Intencion
<que esta mal hoy, o que no se puede hacer hoy; a quien le pasa y como se nota. Tres a seis
lineas, sin nombrar clases, ficheros ni patrones: el como vive en las slices y en el codigo>

## Fuentes de convencion
- doc: <ruta a convencion declarativa, p. ej. .claude/CLAUDE.md>
- skill: <ruta a skill de proyecto, p. ej. .claude/skills/duplicate-action>

### <org>/<repo-destino>            # solo si alguna slice lleva REPO:
- doc: <ruta dentro de ESE repo>

## Controles
- <nombre>: <comando exacto, p. ej. make linting>
- tests: <comando exacto, p. ej. make test>

### <org>/<repo-destino>            # solo si alguna slice lleva REPO:
- ninguno: <motivo, si ese repo no valida en PR>

## Slices
- [ ] slice-01 (nombre-kebab): <titulo de la slice> [pendiente]
      INTENCION: <que deja de estar mal cuando entra esta slice>
      ACEPTACION: <criterio 1>; <criterio 2>; tests en <ruta>
      SENAL: <fuente> <serie/expresion>; <assert vivo con ventana>; critical|advisory
- [ ] slice-02 (otro-nombre): <titulo> [pendiente]
      INTENCION: <coste de no hacerla>
      ACEPTACION: <criterios>
      SENAL: exenta - <motivo>
- [ ] slice-03 (alerta-algo): <titulo> [pendiente]
      REPO: <org>/<repo-destino>
      INTENCION: <coste de no hacerla>
      ACEPTACION: <criterios>
      SENAL: <assert vivo>
```

Reglas duras:

- Antes de todo, una seccion `## Intencion` con el problema de la feature entera: que esta mal hoy
  y como se nota. Es la primera cosa que lee una persona al abrir el issue, y la que `slice-runner`
  reutiliza en el cuerpo de cada pull request. Sin ella la spec no esta terminada.
- Antes de `## Slices`, una seccion `## Fuentes de convencion` con lineas `- doc: <ruta>` o
  `- skill: <ruta>`: punteros confirmados a la vara de medir del repo (la escribe el paso 3;
  slice-runner la exige). Punteros, nunca el contenido de la convencion.
- **Las fuentes son por repo.** Las lineas antes de cualquier `### <org>/<repo>` son las del repo del
  issue; cada subseccion `###` declara la vara de un repo destino. Si una slice lleva `REPO:`, su repo
  **tiene que** tener su subseccion: medir una alerta del repo de manifiestos con las convenciones del
  repo de la app es exactamente la desviacion silenciosa que esta seccion evita.
- Antes de `## Slices`, una seccion `## Controles` con lineas `- <nombre>: <comando>`: los comandos
  deterministas con los que se mide el repo (la escribe el paso 3b; slice-runner la exige y **no
  deduce nada** en tiempo de run). Los nombres son libres -`lint`, `types`, `tests`, o `schema` en un
  repo de manifiestos-, pero el comando tiene que ser **exacto y ejecutable tal cual**, porque nadie
  lo va a interpretar: se le pasa al script y se ejecuta.
- **Los controles tambien son por repo**, con la misma forma que las fuentes y por la misma razon:
  correr `make test` de la app contra el repo de manifiestos no valida nada. Un repo sin controles
  reales se declara con la linea reservada `- ninguno: <motivo>`; dejarlo vacio hace que slice-runner
  pare, e inventarse un control finge una garantia que no existe.

- Cada slice es una linea `- [ ] slice-NN (name): titulo`. `NN` = orden de dos digitos; `name` =
  kebab-case unico dentro de la spec.
- Type opcional para conventional commits: `slice-03 (refactor: extraer-repo): ...`. Sin type ⇒ `feat`.
  No hace falta declarar la lista de types validos: el commit lo redacta el agente (sabe conventional
  commits) y su unico control determinista es la higiene del diff (`controles.py pr-hygiene`).
- Debajo de cada slice, una linea `INTENCION:` con el coste de no hacerla: que esta mal hoy y deja
  de estarlo cuando entra. Va **antes** de los `ACEPTACION:` (primero el por que, luego lo que se
  comprueba antes de fusionar, luego lo que se comprueba vivo). Obligatoria siempre, sin exencion
  posible.
- La etiqueta canonica es `ACEPTACION:`; se llamaba `AC:` y el parser sigue aceptando esa forma para
  no romper los issues ya abiertos, pero **lo que emites es el nombre completo**. Si validas un
  issue viejo, reescribir sus `AC:` es correcto y no cambia nada del contrato.
- Debajo de cada slice, una o mas lineas indentadas con `ACEPTACION:` describiendo criterios
  concretos (y donde viven los tests si aplica). Las **restricciones duras** (p. ej. "no toca infra
  directamente") se expresan como un criterio comprobable mas.
- **Cada criterio debe ser falsable**: tiene que poder nombrarse el cambio de produccion que lo haria
  fallar. `ACEPTACION: rechaza cantidades negativas con ValueError` lo es (borra la validacion y falla);
  `ACEPTACION: el flujo funciona correctamente` no lo es (nada lo puede refutar). Un criterio no
  falsable deja al
  verificador de slice-runner sin nada contra lo que mapear el test, asi que no cumple el contrato.
- Debajo de cada slice, una linea `SENAL:` con **como se comprueba viva en produccion** (formato:
  `<fuente> <serie/expresion>; <assert vivo con ventana>; critical|advisory`), o
  `SENAL: exenta - <motivo>`. Es obligatoria cuando la slice cambia comportamiento observable en prod.
  **La senal tambien es falsable**: `SENAL: se monitoriza con Grafana` no vale (no nombra serie,
  ventana ni assert); `SENAL: prometheus rate(application_stock_ajustado_total[5m]) > 0 en 10m
  post-deploy; critical` si. Si la senal hay que **construirla**, su emision entra ademas como criterio
  de aceptacion normal (el test de emision): la emision se verifica pre-merge, el valor vivo post-deploy.
- Linea `REPO: <org>/<repo>` opcional cuando la slice se implementa en otro repo (alerta, panel).
  Ausente = el repo del issue. Toda slice con `REPO:` exige la subseccion de fuentes de su repo.

- Cada slice arranca `[ ] ... [pendiente]`. slice-runner actualiza el marcador de estado durante el
  run (`en-curso`, `esperando-merge`, `mergeada` con `[x]`, `bloqueada`, `abortada`).
- Una feature de **una sola slice** = un checklist con una unica linea.

## Steps — modo autoria (por defecto)

1. **Invoca `superpowers:brainstorming`** y sigue su proceso para entender intencion, proponer
   enfoques y validar el diseno con el usuario. **Excepcion al terminal de brainstorming:** no
   invoques `writing-plans`; el paso siguiente es emitir la spec de slices (pasos 2-6).
2. **Trocea en slices verticales (guia activa).** Carga `references/slicing.md` y aplica su
   procedimiento sobre el diseno aprobado: identifica el **walking skeleton** (slice #1), genera el
   resto por la **heuristica ordenada**, y **solo abre dialogo con la persona** (opciones graduadas
   por capa, estilo hamburger) cuando el corte no es obvio o una slice supera el budget. Valida cada
   slice contra los criterios de validez y el conjunto contra el **test de despriorizacion** e
   **igualdad de tamano**. Elige `name` kebab-case por slice y, si aplica, su `type`.

2a. **Escribe la intencion, la de la feature y la de cada slice.** El brainstorming del paso 1 ya
   entendio el problema: la seccion `## Intencion` es su destilado, no trabajo nuevo. Redactala con
   lo que esta mal hoy y como se nota, sin nombrar clases ni ficheros. Luego, slice a slice, escribe
   su `INTENCION:` y **pasale la vara**: nombra el cambio de mundo que la borraria; si no puedes
   nombrar nada roto o imposible, reescribela. Si al hacerlo descubres una slice cuya intencion no
   sabes nombrar, la senal no es "redactar mejor": es que la slice sobra o esta mal cortada, y eso se
   arregla volviendo al paso 2.

2b. **Disena la senal de cada slice (mientras el corte todavia se puede cambiar).** Carga
   `references/observabilidad.md` y, slice a slice, **baja la escalera**: ¿la senal ya existe gratis
   por la libreria del repo? ¿basta enriquecer lo que ya emite? ¿hace falta una metrica de negocio
   nueva (y entonces su emision es un criterio de aceptacion mas, con su test)? ¿o es un **gap de la
   libreria** que hay que declarar en vez de instrumentar a mano? Escribe la linea `SENAL:`
   resultante, o la exencion con su motivo. Decide tambien si el conjunto necesita **slice de
   alerta** y **slice de panel**: si las necesita, van con su `REPO:` y **detras** de la slice que
   emite la serie (orden forzoso); si no las necesita, que sea una decision explicita, no un olvido.
   Lo aplazable es la telemetria fina, no la senal minima.
3. **Descubre y confirma las fuentes de convencion (`offload-deterministic` + `check-alignment`).**
   Corre el helper determinista para no asumir rutas ni inventarlas:
   `python3 ~/.claude/skills/slice-runner/scripts/discover_conventions.py <repo>`. Lista candidatos
   (docs y skills de proyecto) sin decidir. Juzga cuales son la vara de medir real, **proponselos a
   la persona y espera su confirmacion** (puede anadir o quitar). Si el helper no devuelve nada
   plausible o no se confirma ninguna, **para y pregunta** donde viven las convenciones: nunca emitas
   la spec con la seccion vacia. Con lo confirmado, redacta la seccion `## Fuentes de convencion`
   (punteros, no contenido: las convenciones siguen viviendo en el repo).

   **Una vez por repo destino.** Si alguna slice lleva `REPO:`, corre el mismo helper **sobre ese
   repo** (`discover_conventions.py <ruta-del-repo-destino>`), confirma con la persona, y escribe sus
   punteros en la subseccion `### <org>/<repo>`. Cada repo tiene su propia vara: la del repo de
   manifiestos (templating, escaping, politica de labels de alerta) no se parece a la de la app, y
   heredar la equivocada es la desviacion silenciosa que esta seccion existe para evitar.
3b. **Descubre y confirma los controles del repo (mismo baile de tres pasos).** Si las fuentes son la
   vara, los controles son **los comandos con los que se mide**, y se declaran aqui por la misma razon:
   `slice-runner` no puede deducirlos en cada slice sin meter el `Makefile` en el contexto que tiene
   que durar todo el run, y dejarselo al implementador seria peor -el juzgado eligiendo su propia
   vara-. Corre el helper determinista:
   `python3 ~/.claude/skills/slice-runner/scripts/discover_controles.py <repo>`. Lista los targets del
   `Makefile` (con el comentario de encima como pista) y las herramientas configuradas en
   `pyproject.toml`/`tox.ini`, **sin decidir**. Propon el mapeo `nombre: comando` y **espera
   confirmacion**: es el paso que mas valor anade, porque ninguna autodeteccion sabe que este repo
   necesita `make env-start` antes, o que `make test` tarda 20 minutos y en el bucle va
   `make test-unit`. Escribe la seccion `## Controles` con lo confirmado.

   - **Una vez por repo destino**, igual que las fuentes: cada `REPO:` lleva su subseccion
     `### <org>/<repo>`. Correr `make test` de la app contra el repo de manifiestos no valida nada.
   - **Un repo sin controles reales** (el de paneles de Grafana: la CI solo publica en `master`, no
     valida en PR) se declara con `- ninguno: <motivo>`. **No lo dejes vacio y no te inventes uno**:
     vacio hace que `slice-runner` pare, y un control inventado finge una garantia que no existe.
4. **Crea el issue** de GitHub con la spec en el cuerpo (`gh issue create --title <feature> --body ...`).
   Como es una accion visible/colaborativa (outward-facing), **confirmala antes de crear**. El cuerpo
   lleva `## Intencion` (paso 2a), `## Fuentes de convencion` (paso 3), `## Controles` (paso 3b) y
   luego `## Slices`; cada slice arranca `[ ] slice-NN (name): titulo [pendiente]`. Cumple el contrato
   de formato al pie de la letra.
5. **Auto-validacion.** Aplica el checklist de `validate` (abajo) sobre lo que vas a poner en el
   cuerpo y corrige inline antes de crear el issue.
6. **Cierra** diciendo el numero/URL del issue y que se ejecuta con `/slice-runner #N` (o
   `/loop /slice-runner #N` para encadenar todas las slices en Nivel 2).

## Steps — modo `validate <ruta>`

Revisa una spec existente contra el contrato y reporta desviaciones (con `regla + linea`). Ofrece
corregirlas. Checklist:

- Es un checklist de slices (`## Slices` con lineas `- [ ] slice-NN ...`).
- Cada slice tiene `slice-NN`, `(name)` kebab-case unico, titulo y al menos una linea `ACEPTACION:`
  (o la forma vieja `AC:`).
- Si aparece un `type` en el parentesis, es un type de conventional commit (no hay lista normativa
  que validar aqui: el commit lo redacta y valida el flujo de slice-runner).
- Checkboxes `[ ]`/`[x]` y, si hay marcador `[estado]`, es uno canonico (pendiente, en-curso,
  esperando-merge, mergeada, bloqueada, abortada).
- **Tiene seccion `## Intencion` con texto**, y **ninguna slice sin linea `INTENCION:`**. Si falta
  (p. ej. un issue anterior a este mecanismo), **es la desviacion a corregir**: reconstruyela con la
  persona y anadela. Comprueba tambien la **vara** en cada linea: nombra el coste de no hacerla. Si
  dice "mejorar", "limpiar" o "refactorizar" sin decir que esta mal hoy, reescribela. Y si la linea
  describe el codigo (que clase se introduce, que fichero se toca) en vez del problema, tambien: eso
  es lo que el diff ya cuenta, y ocupa el sitio de lo que no cuenta.
- Ninguna slice sin criterios de aceptacion (sin ellos no hay control de verificacion en
slice-runner).
- **Ninguna slice que cambie comportamiento en prod sin `SENAL:`**, y ninguna `SENAL: exenta` sin
  motivo escrito. Si falta (p. ej. un issue anterior a este mecanismo), **es la desviacion a corregir**:
  aplica la escalera de `references/observabilidad.md` con la persona y anade la linea. La `SENAL` debe
  ser **refutable**: nombra la serie, la ventana y el assert; si dice "se monitoriza" o "no empeora",
  reescribela.
- **Cadena de observabilidad**: si alguna slice emite una senal nueva relevante, comprueba que hay slice
  de alerta (y de panel si aporta) **con su `REPO:`** y **detras** de la que emite la serie, o que la
  ausencia es una decision explicita. Nunca alerta/panel en la misma slice que la metrica.
- **Toda slice con `REPO:` tiene su subseccion `### <org>/<repo>`** en las fuentes de convencion **y
  en los controles**. Si falta cualquiera de las dos, es desviacion: corre el descubrimiento
  correspondiente sobre ese repo y anadela.
- **Tiene seccion `## Controles` con al menos una linea** para el repo del issue. Si falta (p. ej. un
  issue de cuando `slice-runner` los autodetectaba), **es la desviacion a corregir**: corre
  `discover_controles.py`, confirma el mapeo con la persona y anadela; sin ella `slice-runner` para.
  Un repo que de verdad no tiene controles se declara con `- ninguno: <motivo>`, nunca vacio.
- **Los comandos declarados siguen resolviendo.** Este es el sitio donde se caza la deriva: si alguien
  renombro un target del `Makefile` despues de crear el issue, corrigelo aqui. En tiempo de run no hay
  red -el control falla como cualquier otro y la slice acaba `bloqueada: controles`-, y esa fue una
  decision consciente para no anadir un pre-flight heuristico.
- **Cada criterio es falsable** (no basta con que exista). Por cada uno, nombra el cambio de
  produccion que lo haria fallar; si no puedes nombrarlo, **es la desviacion a corregir**:
  reescribelo con la persona hasta que sea refutable (o pregunta que se pretendia). Un criterio vago
  pasa el check de existencia pero deja sin dientes el mapeo criterio↔test del verificador de
  slice-runner.
- Tiene una seccion `## Fuentes de convencion` con al menos un puntero (`- doc:` / `- skill:`). Si
  falta (p. ej. un issue legacy anterior a este mecanismo), **es la desviacion a corregir**: corre el
  descubrimiento (paso 3), confirmala con la persona y anadela al cuerpo con
  `issue_body.set_fuentes`. Este modo es el unico sitio que rellena issues sin la seccion:
  slice-runner solo la consume, no la genera.
- Nombres unicos y estables (no colisionan al derivar ramas `slice/NN-name`).
- **Calidad del corte** (contra `references/slicing.md`): cada slice es vertical, desplegable sola y
  reversible; el conjunto pasa el **test de despriorizacion** (hay >=1 slice que se podria posponer)
  y tiene **tamano equilibrado**; ninguna slice nombrada por capa tecnica salvo horizontal
  justificado; cuando una slice sustituye comportamiento en prod, nombra su mecanismo seguro (flag /
  expand-contract).

Si todo cumple: reporta `spec valida` y recuerda que se ejecuta con `/slice-runner`.

## Fin

Reporta: numero/URL del issue, numero de slices y sus nombres, y el comando para ejecutarla
(`/slice-runner #N`, o `/loop /slice-runner #N` para Nivel 2). No implementes nada: ese es el trabajo
de `slice-runner`.
