---
name: slice-spec
description: Crea (o valida) una spec de slices en el formato exacto que consume slice-runner. Usar cuando el usuario quiera "escribir una spec", "montar el plan de slices", "trocear una feature en slices", "slice-spec", o tenga una idea/feature y necesite convertirla en una spec ejecutable por slice-runner. Envuelve superpowers:brainstorming para el diseno y luego crea el issue padre (intencion, fuentes de convencion y controles) con una subissue por slice (titulo con identificador y nombre, intencion, criterios de aceptacion, senal y etiqueta de estado). Modo `validate` para revisar una spec existente contra el contrato. Cierra proponiendo que slices pueden correr en paralelo y, si se confirma, monta un worktree por slice y lanza sus runs. No implementa codigo: produce la spec que slice-runner luego ejecuta.
---

# Slice Spec

STARTER_CHARACTER = [slice-spec]

Emite `[slice-spec]` al inicio de cada respuesta mientras ejecutas este proceso, como testigo de que el contexto esta intacto y sigues estas reglas. (Marcador de texto en lugar de emoji por preferencia del usuario.)

## Description

Skill fina que produce la **spec** que `slice-runner` consume, en su formato exacto. No re-piensa
el diseno del producto: **delega el diseno en `superpowers:brainstorming`** y su unico trabajo es
el **contrato de formato** (los nombres de slice, los criterios de aceptacion, las lineas que
`slice-runner` sabe parsear). Es el `check-alignment` + `text-native` del flujo: la spec es el
artefacto compartido entre humano y agente, y **vive en GitHub**: una feature = **un issue padre**
mas **una subissue por slice**.

Par natural: `/slice-spec` crea el issue padre y sus subissues, `uv run slice-runner run <N> --repo
<org>/<repo> --base master` las ejecuta, una invocacion por slice.

Dos modos:

- **Autoria (por defecto):** brainstorming -> crea el issue padre y una subissue por slice, bien formadas.
- **`validate`:** revisa una spec existente contra el contrato -el issue padre `#N` con sus subissues,
  o el borrador de antes de crearlos- y reporta (o corrige) desviaciones con su regla y su ubicacion.

## Principios

- **No implementa.** No escribe codigo ni tests; produce la spec. El estado terminal es una spec
  valida, no un plan de `writing-plans` ni una PR.
- **El diseno lo lleva brainstorming.** No dupliques su trabajo (entender intencion, proponer
  enfoques, validar diseno). Esta skill reengancha solo la **cola**: cuando el diseno esta
  aprobado, en vez de `writing-plans` emite la spec de slices. La spec ES el plan que consume
  slice-runner.
- **Formato es contrato.** La spec la parsea `slice-runner` sin ambiguedad: el cuerpo del padre, el
  titulo y el cuerpo de cada subissue, y su etiqueta de estado. Si no cumple el contrato de abajo, no
  esta terminada.
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
- **Investiga antes de cortar.** El troceo se hace sobre lo que ya hay, no sobre un repo imaginario:
  antes del paso 2 se busca **que se intento antes** y **que existe ya que se pueda reutilizar**, y lo
  confirmado viaja en la seccion `## Lo que ya existe` del padre. Los dos
  fallos que esto corrige son reales: una slice que iba a implementar algo que ningun consumidor leia,
  y otra que tradujo el vocabulario de un script que una tercera estaba jubilando. **Vara: un hallazgo
  es una ruta o un numero, no una impresion.**
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
- **La spec vive en GitHub, repartida por slice.** `slice-spec` crea el issue padre de la feature y
  una subissue por slice: es la fuente de verdad duradera del estado, no un fichero en el repo. No la
  guardes en `docs/` ni la comitees. El reparto es deliberado: **etiquetas para lo que se consulta,
  cuerpo para lo que se reanuda**, asi que una transicion de estado es una escritura de etiqueta y
  nadie reescribe el documento de nadie. Su coste es que la spec deja de leerse de un tiron, y lo paga
  el paso 5: se muestra completa en el terminal antes de crear nada. **No** se paga repitiendo las
  slices en el cuerpo del padre, que seria estado duplicado que deriva.
- **Trocear termina cuando el trabajo esta lanzado, no cuando el issue esta escrito.** Quien acaba de
  cortar es quien mejor sabe que va a tocar cada slice, asi que el reparto en paralelo -que puede ir
  con que, y que no- se propone aqui (paso 7) y, confirmado, se monta aqui: un worktree por slice y su
  run. Dejarlo para despues obliga a reconstruir a ojo lo que en este momento se sabe. **Lo que no se
  hace es prometer que las slices son disjuntas**: se declara el solape que se espera, porque la
  version comoda ya ha fallado dos veces y una fusion avisada no cuesta nada.

## Contrato de formato (lo que el programa lee)

Una feature = **un issue padre** + **una subissue por slice**. Un solo formato, sin variantes.

| Donde | Que lleva |
|---|---|
| Issue padre | `## Intencion`, `## Lo que ya existe`, `## Fuentes de convencion` y `## Controles`, los dos ultimos por repo, mas `## Historia de usuario` si la feature tiene una -y entonces tambien la clave delante de su titulo y la etiqueta `origen:<clave>`-. Las slices son sus subissues, y la barra de progreso la calcula GitHub |
| Titulo de la subissue | `slice-NN (name): titulo`, con la clave de la historia de usuario delante si el padre la declara; de ahi sale el orden de ejecucion, y de `name` sale la rama (con la clave delante del numero cuando la hay: `slice/AS-255-NN-name`) y el scope del commit |
| Cuerpo de la subissue | Las lineas de la slice: `REPO:`, `INTENCION:`, `ACEPTACION:`, `SENAL:`, `EXCLUYE:`, `SUSTITUYE:` |
| Etiqueta de la subissue | El estado macro, que arranca en `estado:pendiente`, mas `origen:<clave>` si el padre declara historia de usuario |

### El issue padre

```markdown
## Intencion
Hoy un ajuste de stock se hace a mano en la consola y no queda rastro de quien lo hizo ni de por que.
Cuando un pedido sale con menos unidades de las pedidas, la tienda no puede reconstruir que paso y
acaba abriendo un caso a soporte, que tampoco tiene donde mirar. Y como nada valida la cantidad, un
ajuste negativo entra sin que nadie lo frene y deja el stock en negativo hasta que alguien lo nota.

## Lo que ya existe
- pieza: src/stock/domain/stock_repository.py - el puerto de persistencia ya existe; esta slice usa
  el que hay, no introduce otro
- precedente: #88 - se intento con un job nocturno y se revirtio porque no daba trazabilidad del quien
- acopla: `AjustarStock` ya emite el evento; el ajuste manual se engancha ahi, no en el endpoint

## Fuentes de convencion
- doc: CLAUDE.md
- skill: .claude/skills/duplicate-action

### tu-org/infra-alertas
- doc: templates/CLAUDE.md

## Controles
- lint: make linting
- types: make check-types
- tests: make test

### tu-org/infra-alertas
- ninguno: la integracion continua de ese repo no valida en PR
```

### Una subissue por slice

Cada slice es una subissue **hija de ese padre**, con su etiqueta de estado desde que nace:

- **Titulo**: `slice-03 (alerta-stock-negativo): avisa cuando el stock queda en negativo`. Delante va
  `slice-NN`, de donde sale el orden de ejecucion -no del orden en que la interfaz de programacion
  devuelva las subissues-; entre parentesis, el `name` en kebab-case, de donde salen la rama
  `slice/NN-name` y el scope del commit. Si el padre declaro `## Historia de usuario`, la clave va
  delante del `slice-NN` en el titulo y tambien delante del numero en la rama: `slice/AS-255-NN-name`.
- **Etiqueta**: `estado:pendiente`, el estado macro inicial, mas `origen:<clave>` si el padre
  declaro `## Historia de usuario` (ver Reglas duras, mas abajo).
- **Cuerpo**: solo las lineas de la slice. El bloque `<!-- slice-runner:estado ... -->` es propiedad de
  la maquina -lo escribe `slice-runner` para poder reanudar- y aqui no se escribe nunca.

El ejemplo es el caso cross-repo, que es el que mas cosas exige: una slice que se implementa en el repo
del padre no lleva primera linea.

```markdown
REPO: tu-org/infra-alertas
INTENCION: hoy el stock se queda en negativo y nadie se entera hasta que una tienda llama a soporte
ACEPTACION: la alerta dispara con stock negativo sostenido 10m y no con un negativo aislado
ACEPTACION: la alerta sale con severidad critical y apunta al runbook de stock
SENAL: prometheus min_over_time(application_stock_actual[10m]) < 0 dispara la alerta en 15m post-deploy; critical
EXCLUYE: el panel de Grafana que visualiza esta misma serie va en su propia slice, detras de esta
SUSTITUYE: no
```

### Reglas duras

- El padre abre con `## Intencion`: el problema de la feature entera, que esta mal hoy y como se nota.
  Es lo primero que lee una persona al abrirlo, y lo que `slice-runner` reutiliza en el cuerpo de cada
  pull request. Sin ella la spec no esta terminada.
- El padre lleva `## Lo que ya existe` con lineas `- pieza: <ruta> - <que es>`,
  `- precedente: #<numero> - <que le paso>` o `- acopla: <sitio> - <como>`. **Cada linea cita una ruta
  o un numero**: un hallazgo que no se puede ir a comprobar es una impresion y no entra. Si de verdad
  no hay nada, la seccion lleva una sola linea `- nada: <motivo>`; **vacia no vale**, por lo mismo que
  `SENAL:` distingue exenta de ausente.
- El padre lleva `## Fuentes de convencion` con lineas `- doc: <ruta>` o `- skill: <ruta>`: punteros
  confirmados a la vara de medir del repo (los escribe el paso 3; slice-runner los exige). Punteros,
  nunca el contenido de la convencion.
- **Cada ruta es un fichero, nunca un directorio.** `slice-runner` **lee el contenido** de cada fuente
  y lo mete en el prompt de los tres agentes, asi que `- doc: docs/conventions/` no es un puntero mas
  corto: es una fuente que no se puede leer, y para el run en los prechecks. Y listar la carpeta
  tampoco valdria: meteria en el prompt lo que **no** es la vara del codigo -el flujo de trabajo de una
  persona, la convencion de como se redacta una convencion- y haria que anadir un fichero ahi cambiase
  en silencio lo que ven los tres agentes. Se listan los ficheros, uno por linea.
- **Las fuentes son por repo.** Las lineas antes de cualquier `### <org>/<repo>` son las del repo del
  padre; cada subseccion `###` declara la vara de un repo destino. Si una slice lleva `REPO:`, su repo
  **tiene que** tener su subseccion: medir una alerta del repo de manifiestos con las convenciones del
  repo de la app es exactamente la desviacion silenciosa que esta seccion evita.
- El padre lleva `## Controles` con lineas `- <nombre>: <comando>`: los comandos deterministas con los
  que se mide el repo (los escribe el paso 3b; slice-runner los exige y **no deduce nada** en tiempo de
  run). Los nombres son libres -`lint`, `types`, `tests`, o `schema` en un repo de manifiestos-, pero el
  comando tiene que ser **exacto y ejecutable tal cual**, porque nadie lo va a interpretar: se ejecuta.
- **Los controles tambien son por repo**, con la misma forma que las fuentes y por la misma razon:
  correr `make test` de la app contra el repo de manifiestos no valida nada. Un repo sin controles
  reales se declara con la linea reservada `- ninguno: <motivo>`, que **no es un control llamado
  `ninguno`**: es la exencion, y lo que la sigue es el motivo, no un comando -si acabara ejecutandose,
  alguien pasaria una frase en castellano a un shell-. Vacio y eximido no son lo mismo: vacio hace que
  `slice-runner` pare, e inventarse un control finge una garantia que no existe. Y la exencion no admite
  controles al lado: "no hay controles" y "hay estos" no pueden ser ciertas a la vez.
- **El padre no repite las slices.** Su detalle vive en cada subissue; copiarlo arriba es estado
  duplicado que deriva en cuanto una slice cambia.
- **Una subissue por slice, y creada como hija del padre** (`gh issue create --parent`). El parentesco
  no es cosmetico: `slice-runner` busca las slices de una feature con `parent-issue:<org>/<repo>#<N>`,
  asi que una subissue creada sin `--parent` es una slice que no existe para el run.
- **El titulo es `slice-NN (name): titulo`, con la clave de la historia de usuario delante cuando el
  padre la declara** (`AS-255 slice-NN (name): titulo`; el formato completo de esa clave esta un poco
  mas abajo). `NN` = orden de dos digitos, y es lo que ordena las slices; `name` = kebab-case unico
  dentro de la feature, y es lo que deriva la rama y el scope del commit. Un titulo cuyo `slice-NN` -
  precedido o no de esa clave- no aparece donde el programa lo espera no se puede leer y para el run.
- **El parentesis lleva el `name` y nada mas.** Nada de un type de conventional commit delante: el
  programa se lleva el parentesis entero como nombre, asi que un `(refactor: extraer-repo)` le pide a
  git una rama llamada `slice/03-refactor: extraer-repo`, que no es un nombre de rama valido, y el run
  muere **despues** de haber publicado el entendimiento y pagado la llamada. El type del commit lo
  elige el agente al redactarlo -sabe conventional commits-, y su unico control determinista es la
  higiene del diff que aplica el programa al stagear, asi que declararlo aqui no alimentaba nada.
- **El estado macro es una etiqueta, nunca una marca en el texto.** Toda subissue nace con
  `estado:pendiente` y `slice-runner` la mueve escribiendo etiquetas (`estado:en-curso`,
  `estado:esperando-merge`, `bloqueada:controles`, `abortada:presupuesto`...); mergeada es GitHub
  cerrando la subissue al fusionar su pull request. Un segundo sitio donde escribir el estado es un
  sitio donde puede desmentir al primero, y nada lee ese.
- **Si la feature tiene una historia de usuario, su clave va en una seccion propia del padre y
  delante del `slice-NN` en el titulo de cada subissue.** La clave son mayusculas y digitos, un guion
  y uno o mas digitos: una letra mayuscula, cero o mas letras mayusculas o digitos, `-`, uno o mas
  digitos (`AS-255`, `JIRA2-10`). Una clave en minusculas, con guion bajo, o sin el numero final no
  tiene esa forma y `slice-runner` no la lee. El padre la declara con:

  ```markdown
  ## Historia de usuario
  AS-255
  ```

  y esa clave se antepone al titulo de cada subissue de la feature, como primera palabra y separada
  de `slice-NN` por un espacio: `AS-255 slice-04 (nombre): titulo`. Su ausencia dice que la feature
  no tiene historia de usuario asociada, y el titulo se queda exactamente como hoy: sin esa palabra
  delante.

  **Y tambien delante del titulo del padre** (`AS-255 <feature>`), por el mismo motivo por el que va
  en el de las subissues: en el listado de issues no se abre nada, y un padre que no la lleva es el
  unico issue de la feature que no dice a que historia pertenece. El programa **no** parsea el titulo
  del padre -solo el de las subissues-, asi que esta mitad es para quien mira, no para quien ejecuta.
- **La etiqueta de historia de usuario lleva la clave dentro, una por historia.** Cuando el padre
  declara `## Historia de usuario`, la subissue nace ademas con `origen:AS-255` (el patron es
  `origen:<clave>`, y lo que va detras de los dos puntos es siempre la clave de la historia de usuario:
  el prefijo dice **de donde viene el trabajo**, no en que estado esta), escrita en la misma llamada de
  creacion junto a `estado:pendiente`. No entra
  en el vocabulario cerrado de `IssueLabel` -que asume una sola etiqueta de estado por issue-: es
  una etiqueta mas, y filtrar por ella en GitHub aisla exactamente las subissues de esa historia, no
  todas las que tengan alguna.

  **El padre la lleva tambien**, y no es redundante: la etiqueta es la unica forma de pedirle a GitHub
  "todo lo de esta historia" de una vez, y sin ella el filtro devuelve las slices pero deja fuera el
  issue donde viven la intencion, las fuentes y los controles. El padre no lleva etiqueta de estado
  -el estado es de cada slice-, asi que `origen:<clave>` es la unica que tiene.
- El cuerpo lleva una linea `INTENCION:` con el coste de no hacer la slice: que esta mal hoy y deja de
  estarlo cuando entra. Va **antes** de los `ACEPTACION:` (primero el por que, luego lo que se comprueba
  antes de fusionar, luego lo que se comprueba vivo). Obligatoria siempre, sin exencion posible.
- El cuerpo lleva una o mas lineas `ACEPTACION:` con criterios concretos (y donde viven los tests si
  aplica). Las **restricciones duras** (p. ej. "no toca infra directamente") se expresan como un
  criterio comprobable mas.
- **Cada criterio debe ser falsable**: tiene que poder nombrarse el cambio de produccion que lo haria
  fallar. `ACEPTACION: rechaza cantidades negativas con ValueError` lo es (borra la validacion y falla);
  `ACEPTACION: el flujo funciona correctamente` no lo es (nada lo puede refutar). Un criterio no
  falsable deja al verificador de slice-runner sin nada contra lo que mapear el test, asi que no cumple
  el contrato.
- **Un criterio puede fijar donde vive una pieza, y cuando la slice introduce una tiene que hacerlo.**
  "Se ejecuta desde su propio caso de uso" o "la proyeccion vive en el vocabulario de destino" son tan
  falsables como cualquier criterio de comportamiento -borras la pieza de su sitio y el criterio cae-, y
  son lo unico que le da al verificador algo que exigir sobre la **forma**. Sin ellos, la arquitectura
  queda huerfana entre dos varas: los criterios solo hablan de lo que el codigo hace, y las convenciones
  del repo solo cubren lo que alguien se acordo de escribir en ellas. Un criterio de forma no sustituye a
  la convencion -si la regla vale para todo el repo, su casa es `docs/conventions/`-, pero es lo que
  impide que **esta** slice nazca en el sitio equivocado mientras la convencion se escribe.
- **Y cada criterio se le pide a quien puede cumplirlo.** El implementador no toca `git` -ni commitea,
  ni stagea, ni cambia de rama, ni redacta mensajes de commit- y no compone el cuerpo de la pull
  request: lo que devuelve es codigo, tests y su informe. Un criterio que pida algo fuera de eso es
  **invalido aunque sea falsable**, porque nadie en el pipeline puede cumplirlo, y su unico efecto es
  gastar una vuelta hasta que alguien lo descubre. `ACEPTACION: la retirada de los tests va en un
  segundo commit` hay que reescribirla (el reparto en commits lo decide el programa, una vuelta un
  commit); `ACEPTACION: el cuerpo de la pull request nombra el test que cubre cada uno retirado`
  tambien (el cuerpo se compone solo, y en las vueltas de correccion ni siquiera se reescribe). Lo
  que si esta en su mano es **declararlo en su informe**, que es por donde eso llega a la pull
  request: `ACEPTACION: por cada test retirado, el informe nombra el del caso de uso que lo cubre`
  cumple la vara.
- **Una slice que traslada logica declara que se retira de donde estaba.** Cuando el trabajo es mover
  algo de A a B -un paso que se va a su caso de uso, una regla que baja al dominio-, el criterio sobre
  tests dice **que sale de A**, no solo que A sigue verde. "Los tests de A siguen verdes sin tocarlos"
  es la red que prueba que el comportamiento no cambio **mientras** se traslada, y es buena; pero si es
  lo unico que se pide, dejar en A la cobertura que ahora tambien vive en B es la respuesta correcta
  segun la vara, y la duplicidad se queda. Se piden las dos cosas: la red durante el traslado y la
  retirada despues.
- **Y al retirarla, un test que cubria dos mitades no se retira entero.** Si el test que sobra
  comprobaba ademas algo que la pieza nueva no puede ver -la transicion que produce, la etiqueta que se
  escribe, lo que cruza invocaciones-, esa mitad se queda fijada donde estaba. `ACEPTACION: se retira de
  A lo que solo ejercita <lo trasladado>, y lo que ademas fijaba una transicion se queda` cumple la
  vara; `ACEPTACION: se retiran los tests duplicados` no, porque no dice quien decide que es duplicado.
- El cuerpo lleva una linea `SENAL:` con **como se comprueba viva en produccion** (formato:
  `<fuente> <serie/expresion>; <assert vivo con ventana>; critical|advisory`), o
  `SENAL: exenta - <motivo>`. Es obligatoria cuando la slice cambia comportamiento observable en prod.
  **La senal tambien es falsable**: `SENAL: se monitoriza con Grafana` no vale (no nombra serie,
  ventana ni assert); `SENAL: prometheus rate(application_stock_ajustado_total[5m]) > 0 en 10m
  post-deploy; critical` si. Si la senal hay que **construirla**, su emision entra ademas como criterio
  de aceptacion normal (el test de emision): la emision se verifica pre-merge, el valor vivo post-deploy.
- El cuerpo lleva una linea `EXCLUYE:` con **lo que esta slice deja fuera de su alcance a proposito**:
  andamiaje de una slice futura ya prevista, no algo que falte. Es obligatoria siempre, sin ausencia
  silenciosa: si de verdad no hay nada que excluir, se declara con `EXCLUYE: nada - <motivo>`, igual
  que `SENAL: exenta - <motivo>`. Es una **prohibicion que viaja a los dos agentes**: el implementador
  no construye lo que nombra, y el verificador bloquea si aparece en el diff, citando la linea en vez de
  tener que argumentar que sobra.
- El cuerpo lleva una linea `SUSTITUYE:` que dice **si el diff sustituye comportamiento que ya vive en
  produccion**, con la forma `SUSTITUYE: no` o `SUSTITUYE: si - <que sustituye>; <como se vuelve atras
  sin redeploy>`. Es obligatoria siempre y **sin figura de exencion**: a diferencia de `EXCLUYE:` y de
  `SENAL:`, aqui no hay `nada`/`exenta` posible, porque la pregunta -¿esto reemplaza algo vivo?- siempre
  tiene una respuesta, aunque sea que no. Con `si`, las dos mitades son obligatorias: nombrar que se
  sustituye sin decir como se vuelve atras deja al verificador de slice-runner sin el mecanismo que el
  item de patron de rollout exige ver en el diff.
- Linea `REPO: <org>/<repo>` cuando la slice se implementa en otro repo (alerta, panel). Ausente = el
  repo del padre. Toda slice con `REPO:` exige la subseccion de fuentes **y de controles** de su repo.
- Una feature de **una sola slice** = un padre con una sola subissue.

## Steps — modo autoria (por defecto)

1. **Invoca `superpowers:brainstorming`** y sigue su proceso para entender intencion, proponer
   enfoques y validar el diseno con el usuario. **Excepcion al terminal de brainstorming:** no
   invoques `writing-plans`; el paso siguiente es emitir la spec de slices (pasos 2-6).
1b. **Investiga el repo antes de cortar (`check-alignment`).** Trocear sin mirar que hay ya produce
   slices que construyen lo que existe, que traducen lo que otra esta jubilando, o que implementan algo
   que ningun consumidor lee. Busca tu mismo, con los terminos del concepto que vas a trocear, y
   contesta tres preguntas **con punteros, no con prosa**:

   - **¿Que hay ya que esto necesite?** Busca en el arbol quien nombra el concepto. Vale una ruta que
     existe; no vale "el repo ya tiene puertos".
   - **¿Se intento antes?** Mira las pull requests mergeadas y las issues cerradas
     (`gh pr list --state merged --search ...`, `gh issue list --state closed --search ...`). Vale un
     numero y lo que le paso.
   - **¿Donde acopla?** Vale el sitio concreto del que cuelga.
   - **¿Cual es el fichero de orquestacion del repo?** El uno o dos sitios donde un conflicto deja de
     ser cosmetico -el caso de uso que dirige el flujo, el entrypoint que monta las dependencias-. No
     cambia el corte, pero **decide el paso 7**: son carriles de uno.

   **Vara: si no puedes citar una ruta o un numero, no es un hallazgo, es una impresion**, y no entra.
   Es la misma vara de falsabilidad que gobierna los criterios de aceptacion, aplicada aguas arriba.

   **Acota la busqueda.** El objetivo es un punado de lineas que una persona pueda confirmar de un
   vistazo, no un informe: para cuando dejes de encontrar cosas nuevas, y quedate con lo que de verdad
   cambia el corte.

   Propon los hallazgos a la persona y **espera su confirmacion**, igual que con las fuentes y los
   controles: ella sabe cual de esos precedentes se revirtio por un motivo que sigue vigente. Lo
   confirmado se escribe en la seccion `## Lo que ya existe` del issue padre, y **se usa en el paso 2**:
   una pieza reutilizable suele quitar una slice entera, y un precedente revertido suele cambiar el
   orden.

   **Si no hay nada, dilo con esa seccion vacia y su motivo**, no la omitas: ausencia declarada y
   ausencia silenciosa no son lo mismo, igual que en `SENAL:` y en los controles.

1c. **Publica lo entendido del codigo y los criterios propuestos, y espera confirmacion de los dos
   antes de cortar (`check-alignment`).** El paso 1b confirma punteros -rutas, numeros de issue,
   sitios de acople-; lo que no confirma nadie es que se entendio **que hace** el codigo que el corte
   va a tocar, ni **que se va a considerar hecho**. Hoy el primer momento en que un malentendido del
   flujo, o un criterio que no era ese, se puede ver es leyendo las subissues ya creadas, o la pull
   request de la primera slice con el run ya pagado.

   Publica dos mitades y **espera confirmacion de las dos**:

   - **Lo que entiendes del codigo**, con forma exigible: por cada pieza que el corte va a tocar, su
     ruta y **que hace hoy**. **Una linea que solo dice que el fichero existe no cumple**: eso ya lo
     dio el paso 1b, y esta pausa pide el comportamiento.
   - **Los criterios de aceptacion de la feature entera**, con la misma **vara de falsabilidad** que
     gobierna los criterios de cada slice -nombra el cambio de produccion que lo haria fallar-, y
     **declara que esa vara se aplico**.

   Estos criterios de feature **no se escriben en el issue padre**: seria un tercer sitio diciendo lo
   mismo que ya dicen las subissues, y derivaria en cuanto una slice cambie -el mismo motivo por el
   que **"el padre no repite las slices"**-. Viven en esta conversacion, y de aqui los reparte el paso
   siguiente.

2. **Trocea en slices verticales (guia activa), repartiendo lo confirmado en el paso 1c.** Carga
   `references/slicing.md` y aplica su procedimiento sobre el diseno aprobado: identifica el **walking
   skeleton** (slice #1), **saca delante el contrato de toda frontera** -un endpoint o un evento hacia
   fuera, pero tambien un puerto o un modelo compartido entre capas-, porque es lo que permite que sus
   dos lados se construyan a la vez en vez de en fila (paso 1b de `slicing.md`, y es de donde sale el
   paralelismo del paso 7), genera el resto por la **heuristica ordenada**, y **solo abre dialogo con
   la persona** (opciones graduadas por capa, estilo hamburger) cuando el corte no es obvio o una
   slice supera el budget. Valida cada slice contra los criterios de validez y el conjunto contra el
   **test de despriorizacion** e **igualdad de tamano**. Elige el `name` kebab-case de cada slice. Las
   lineas `ACEPTACION:` de cada slice salen de **repartir** los criterios de feature confirmados en el
   paso 1c, no de inventarlos aqui.

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
2c. **Pregunta si la feature tiene una historia de usuario asociada (`check-alignment`).** No hay
   heuristica ni fichero que la derive: pregunta directamente por su clave (formato `AS-255` - una
   letra mayuscula, cero o mas letras mayusculas o digitos, un guion y uno o mas digitos) y **espera
   la respuesta**. Si la persona da una clave, comprueba que tiene esa forma -si no, dilo y vuelve a
   pedirla- y escribe la seccion `## Historia de usuario` del padre con ella; esa misma clave se
   antepone al titulo de cada subissue en el paso 5 y viaja a su etiqueta `origen:<clave>`. Si la
   persona dice que la feature no tiene historia asociada, no se escribe nada: sin esta pregunta el
   padre nunca tendria la seccion, porque ningun otro paso la deriva de lo que ya se ha discutido.
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
4. **Auto-validacion.** Aplica el checklist de `validate` (abajo) sobre lo que vas a crear -cuerpo del
   padre, titulo, etiqueta y cuerpo de cada subissue- y corrigelo antes de tocar GitHub.
5. **Muestra la spec completa por terminal, espera confirmacion, y solo entonces crea.** La spec ya no
   es un documento que se lea de un tiron, asi que lo que se revisa es lo que imprimes: el cuerpo del
   padre entero y, slice a slice, su titulo, su etiqueta y su cuerpo. Es una accion visible en el repo
   de alguien y no se deshace facil, asi que **no crees nada hasta que la persona lo confirme**; si
   pide cambios, corriges y vuelves a mostrarlo.

   Con la confirmacion dada, y en este orden:

   - El padre: `gh issue create --repo <org>/<repo> --title "<feature>" --body-file -`, con el cuerpo
     del paso 2a/2c/3/3b. Si declaro `## Historia de usuario`, su titulo abre con la clave
     (`AS-255 <feature>`) y la llamada anade `--label origen:AS-255`.
   - Cada slice, en orden de `slice-NN`, como hija suya:
     `gh issue create --repo <org>/<repo> --title "slice-NN (name): <titulo>" --body-file - --parent <N> --label estado:pendiente`,
     donde `<N>` es el numero del padre. El `--parent` es lo que la hace slice de esa feature y la
     `--label` es su estado macro inicial.
   - Si `gh` responde que la etiqueta no existe en el repo, creala una vez
     (`gh label create estado:pendiente --repo <org>/<repo>`) y reintenta: una subissue sin etiqueta de
     estado es una slice sin estado que nadie puede consultar.
   - Si el padre declaro `## Historia de usuario`, el titulo lleva la clave delante
     (`AS-255 slice-NN (name): <titulo>`) y el comando anade `--label origen:AS-255` a la misma
     llamada, junto a `--label estado:pendiente`. Si `gh` responde que esa etiqueta tampoco existe, se
     crea igual que la de estado (`gh label create origen:AS-255 --repo <org>/<repo>`) y se
     reintenta.
6. **Cierra** diciendo el numero/URL del padre, las subissues creadas con su numero, y que se ejecuta
   con `slice-runner run <N> --repo <org>/<repo> --base master`, una invocacion por slice.

7. **Propon el reparto en paralelo y, si te lo confirman, montalo tu.** Una invocacion conduce **una**
   slice, asi que una feature de ocho son ocho invocaciones; en serie eso es toda la tarde. Se pueden
   correr a la vez en **worktrees distintos**, y quien acaba de trocear es quien mejor sabe que va a
   tocar cada slice, asi que la propuesta se hace aqui y no se deja para que la improvise otro.

   **El reparto lo decides por semantica: no hay helper, y el riesgo se declara en vez de negarse.**
   Lee lo que acabas de trocear y estima, slice a slice, **que ficheros va a tocar**. Luego cruza las
   estimaciones. Lo que **no** vale es la conclusion comoda: decir "son disjuntas" es lo que ha fallado
   dos veces en este flujo -una pareja elegida como la mas disjunta mirando su fichero protagonista
   compartio cuatro ficheros, y otra compartio siete, incluido uno que **las dos crearon**-. La forma
   honesta es *"comparten `<fichero>`; si hay conflicto sera pequeno"*, y **no** *"no se tocan"*.

   Tres reglas duras, que no dependen de lo bien que estimes:

   - **Dos slices que toquen el mismo fichero de orquestacion no van juntas.** En todo repo hay uno o
     dos ficheros donde el conflicto deja de ser cosmetico y pasa a ser logica que hay que rehacer.
     Identificalos en el paso 1b y trata cada uno como un carril de uno.
   - **Los ficheros iman se comparten casi siempre**: el entrypoint que monta las dependencias, los
     dobles de test, el vocabulario de errores, el `README.md` y los docs de convencion. Compartir uno
     no impide lanzar; **garantiza una fusion**, y la segunda en mergear la resuelve.
   - **Una slice que depende de otra va detras**, nunca al lado. Si el paso 1b encontro un `- acopla:`
     entre dos, esas dos son secuenciales aunque toquen ficheros distintos.

   Presenta el reparto en **tandas**, y para cada slice di su worktree y el solape que esperas.
   **Espera confirmacion** (`check-alignment`): crear worktrees y lanzar runs gasta dinero en el
   harness de otra persona.

   Con la confirmacion dada, montalo tu, un worktree por slice de la tanda:

   ```bash
   git worktree add <ruta-del-worktree> --detach origin/<base>
   slice-runner run <padre> --repo <org>/<repo> --base <base> --slice <identificador> --worktree <ruta-del-worktree>
   ```

   **El `--detach` vale para una slice que arranca de cero, y solo para esa.** El programa crea la rama
   el mismo antes de implementar, asi que ahi el worktree suelto es lo limpio. Pero una slice **que ya
   tiene estado persistido** -porque un run anterior murio, o quedo esperando algo- **retoma por su paso
   y no vuelve a crear la rama**: si el worktree esta suelto, implementa entero sobre nada y revienta al
   commitear, con el trabajo hecho, el juez pasado y el harness ya pagado. Antes de relanzar una slice
   asi, **ponla en su rama**: `slice/NN-name`, o `slice/AS-255-NN-name` si la feature tiene historia
   de usuario.

   ```bash
   git -C <ruta-del-worktree> switch slice/NN-name
   ```

   Cada run **en background**, nunca encadenados en una shell que bloquee: son procesos largos y el
   principio de este flujo es que ninguna espera congele una sesion.

   **Y con la salida a la vista: no la redirijas a un fichero ni la pases por una tuberia.** Quien lanza
   el run no es quien lo mira. Desviada, la persona se queda sin ver que esta pasando en un proceso que
   dura tres cuartos de hora y cuesta decenas de dolares, y la unica forma que le queda de enterarse es
   pedirtelo a ti, turno a turno. Una tuberia ademas puede dejarla en nada: el proceso escribe a bloques
   cuando el otro extremo no es un terminal, asi que matar el run se lleva lo que aun no habia salido.
   Si solo te interesa el final, **recorta al leer, no al escribir**.

   Y avisa de lo que viene despues, porque es lo que sorprende: **cada run se para en su pausa de
   alineacion**, asi que N runs en paralelo son N entendimientos que revisar y N `-GO` que dar, no uno.

## Steps — modo `validate`

Revisa una spec existente -el padre `#N` y sus subissues- contra el contrato y reporta cada desviacion con
**la regla que incumple y su ubicacion**: `issue padre` cuando esta en el cuerpo del padre, y
`slice-NN (#numero)` cuando esta en una subissue, diciendo si esta en el titulo, en la etiqueta o en el
cuerpo. Sin ubicacion la persona tiene que buscarla, y en una feature de doce slices eso es medio
trabajo. Ofrece corregirlas. Checklist:

- **Hay un issue padre y una subissue por slice, y cada subissue es hija de el.** Si alguna esta
  suelta, es desviacion: `slice-runner` no la vera, porque busca por `parent-issue:<org>/<repo>#<N>`.
  Un padre con checklist de slices en el cuerpo es del formato viejo, y eso se termina con la version
  vieja de estas skills, no se convierte a medias.
- Cada subissue tiene titulo `slice-NN (name): titulo` -con la clave de la historia de usuario
  delante si el padre la declaro-, con `NN` de dos digitos sin huecos ni repetidos y `name` en
  kebab-case unico dentro de la feature, y al menos una linea `ACEPTACION:` en su cuerpo.
- **El parentesis no lleva nada mas que el `name`.** Un type de conventional commit delante, del
  estilo `(refactor: extraer-repo)`, es desviacion: el programa se lleva el parentesis entero como
  nombre y deriva una rama que git rechaza.
- **El padre declara `## Historia de usuario` pero su propio titulo no abre con la clave, o no lleva
  la etiqueta `origen:<clave>`.** Las dos mitades sirven para lo mismo -encontrar la feature entera
  sin abrirla- y las dos se corrigen igual: reportalo como `issue padre`, diciendo cual de las dos
  falta.
- **El padre declara `## Historia de usuario` pero alguna subissue no lleva la clave en el
  titulo.** Si el padre trae la seccion y el titulo de una subissue no empieza por esa clave seguida
  de `slice-NN`, es la desviacion a corregir: reportala como `slice-NN (#numero)`, en el titulo,
  citando la regla de que la clave va delante del `slice-NN`.
- **Cada subissue tiene su etiqueta de estado macro**, y es una del vocabulario (`estado:pendiente` al
  crearla; luego las que escribe slice-runner). Un estado escrito en el texto en vez de como etiqueta es
  desviacion: nada lo lee, y desmiente a la etiqueta en cuanto las dos existen. Un cuerpo que traiga a
  mano el bloque `<!-- slice-runner:estado ... -->` es la misma desviacion al reves: ese bloque es de la
  maquina.
- **Tiene seccion `## Lo que ya existe`**, y cada linea cita una ruta o un `#numero`. Si falta (p. ej.
  un issue anterior a este mecanismo), **es la desviacion a corregir**: corre el descubrimiento
  (paso 1b), confirmalo con la persona y anadela. Una linea sin referencia comprobable -"el repo ya
  tiene puertos"- se reescribe o se quita: lo que no se puede ir a mirar no informa el corte. Ausencia
  real se declara con `- nada: <motivo>`, nunca dejando la seccion vacia.
- **Tiene seccion `## Intencion` con texto**, y **ninguna slice sin linea `INTENCION:`**. Si falta
  (p. ej. un issue anterior a este mecanismo), **es la desviacion a corregir**: reconstruyela con la
  persona y anadela. Comprueba tambien la **vara** en cada linea: nombra el coste de no hacerla. Si
  dice "mejorar", "limpiar" o "refactorizar" sin decir que esta mal hoy, reescribela. Y si la linea
  describe el codigo (que clase se introduce, que fichero se toca) en vez del problema, tambien: eso
  es lo que el diff ya cuenta, y ocupa el sitio de lo que no cuenta.
- Ninguna slice sin criterios de aceptacion en su cuerpo (sin ellos no hay control de verificacion en
  slice-runner).
- **Ninguna slice que cambie comportamiento en prod sin `SENAL:`**, y ninguna `SENAL: exenta` sin
  motivo escrito. Si falta (p. ej. un issue anterior a este mecanismo), **es la desviacion a corregir**:
  aplica la escalera de `references/observabilidad.md` con la persona y anade la linea. La `SENAL` debe
  ser **refutable**: nombra la serie, la ventana y el assert; si dice "se monitoriza" o "no empeora",
  reescribela.
- **Ninguna slice sin `EXCLUYE:`, y ninguna `EXCLUYE: nada` sin motivo escrito.** Si falta (p. ej. un
  issue anterior a este mecanismo), **es la desviacion a corregir**: pregunta a la persona que decidio
  dejar fuera al cortar esta slice -si de verdad nada, la exencion lleva motivo- y anade la linea,
  reportandola como `slice-NN (#numero)`, en el cuerpo.
- **Ninguna slice sin `SUSTITUYE:`, y ninguna `SUSTITUYE: si` sin las dos mitades.** Si falta (p. ej.
  un issue anterior a este mecanismo), **es la desviacion a corregir**: pregunta a la persona si el
  diff de esta slice sustituye comportamiento que ya vive en produccion y anade la linea con la forma
  `no` o `si - <que sustituye>; <como se vuelve atras sin redeploy>`, reportandola como
  `slice-NN (#numero)`, en el cuerpo. Un `SUSTITUYE: si` que no nombra las dos mitades -que sustituye,
  como se vuelve atras- es la misma desviacion: sin el mecanismo de vuelta atras el verificador de
  slice-runner no tiene contra que exigirlo.
- **Cadena de observabilidad**: si alguna slice emite una senal nueva relevante, comprueba que hay slice
  de alerta (y de panel si aporta) **con su `REPO:`** y **detras** de la que emite la serie, o que la
  ausencia es una decision explicita. Nunca alerta/panel en la misma slice que la metrica.
- **Toda slice con `REPO:` tiene su subseccion `### <org>/<repo>`** en las fuentes de convencion **y
  en los controles**. Si falta cualquiera de las dos, es desviacion: corre el descubrimiento
  correspondiente sobre ese repo y anadela.
- **El padre tiene seccion `## Controles` con al menos una linea** para su propio repo. Si falta (p. ej.
  un issue de cuando `slice-runner` los autodetectaba), **es la desviacion a corregir**: corre
  `discover_controles.py`, confirma el mapeo con la persona y anadela; sin ella `slice-runner` para.
  Un repo que de verdad no tiene controles se declara con `- ninguno: <motivo>`, nunca vacio, y esa
  linea no lleva controles al lado ni se lee como un comando.
- **Los comandos declarados siguen resolviendo.** Este es el sitio donde se caza la deriva: si alguien
  renombro un target del `Makefile` despues de crear el padre, corrigelo aqui. En tiempo de run no hay
  red -el control falla como cualquier otro y la slice acaba con `bloqueada:controles`-, y esa fue una
  decision consciente para no anadir un pre-flight heuristico.
- **Cada criterio es falsable** (no basta con que exista). Por cada uno, nombra el cambio de
  produccion que lo haria fallar; si no puedes nombrarlo, **es la desviacion a corregir**:
  reescribelo con la persona hasta que sea refutable (o pregunta que se pretendia). Un criterio vago
  pasa el check de existencia pero deja sin dientes el mapeo criterio↔test del verificador de
  slice-runner.
- **Y cada criterio cae dentro de lo que el implementador puede hacer.** Si pide un commit, un mensaje
  de commit, una rama o texto del cuerpo de la pull request, **es la desviacion a corregir**: no lo
  puede cumplir nadie, y se descubre tarde, cuando la vuelta ya esta pagada. Reescribelo apuntando a lo
  que si esta en su mano -normalmente, que lo declare en su informe-. Esta es la unica desviacion del
  checklist que **no se ve leyendo el criterio solo**: hay que preguntarse quien lo cumpliria.
- **Si la slice traslada logica, sus criterios piden la retirada, no solo la red.** Un criterio que
  solo diga "los tests de donde estaba siguen verdes sin tocarlos" **es la desviacion a corregir**:
  describe el estado de mitad del trabajo, y cumplirlo al pie de la letra deja la cobertura duplicada
  para siempre. Anade el criterio que dice que sale de donde estaba, y el que protege las mitades: lo
  que ademas fijaba una transicion, una etiqueta o algo que cruza invocaciones se queda.
- **El padre tiene una seccion `## Fuentes de convencion`** con al menos un puntero (`- doc:` /
  `- skill:`). Si falta (p. ej. un issue anterior a este mecanismo), **es la desviacion a corregir**:
  corre el descubrimiento (paso 3), confirmala con la persona y anadela al cuerpo del padre. Este modo
  es el unico sitio que rellena un padre sin la seccion: slice-runner solo la consume, no la genera.
- **Y cada fuente es un fichero que existe y se puede leer**, no un directorio ni una ruta que se
  movio. **Compruebalo de verdad, una por una, contra el repo**: es el unico item de este checklist que
  no se decide leyendo el issue. Un directorio como `docs/conventions/` valia cuando las fuentes eran
  punteros que el implementador abria y elegia; desde que **su contenido viaja dentro del prompt**, una
  fuente que no se puede leer para el run en los prechecks, antes de escribir nada. Si encuentras una,
  la desviacion se corrige **listando los ficheros** que de verdad son la vara del codigo -no todos los
  que haya en la carpeta: `git-workflow.md` y el `CLAUDE.md` los lee una persona en sesion, no quien
  implementa-. Es la revision que hay que pasarle a **todo issue creado antes de que la vara viajara en
  el prompt**, y hacerlo aqui cuesta un minuto; descubrirlo al lanzar cuesta el lanzamiento.
- Nombres unicos y estables (no colisionan al derivar ramas `slice/NN-name`).
- **Calidad del corte** (contra `references/slicing.md`): cada slice es vertical, desplegable sola y
  reversible; el conjunto pasa el **test de despriorizacion** (hay >=1 slice que se podria posponer)
  y tiene **tamano equilibrado**; ninguna slice nombrada por capa tecnica salvo horizontal
  justificado; cuando una slice sustituye comportamiento en prod, nombra su mecanismo seguro (flag /
  expand-contract).

Si todo cumple: reporta `spec valida` y recuerda que se ejecuta con `uv run slice-runner run`.

## Fin

Reporta: numero/URL del issue padre, las subissues con su numero y su nombre, y el comando para
ejecutarla (`uv run slice-runner run <N> --repo <org>/<repo> --base master`, una invocacion por
slice). No implementes nada: ese es el trabajo de `slice-runner`.
