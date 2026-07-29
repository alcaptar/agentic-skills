# Los controles se declaran en el issue

Fecha: 2026-07-29
Estado: aprobado

## Intencion

Hoy el orquestador de `slice-runner` deduce por si mismo, en el paso 2 y **al principio de cada
slice**, que comandos del repo cubren lint, tipos y tests: abre el `Makefile`, lo lee, elige targets.
Eso mete el `Makefile` del repo en el unico contexto que tiene que sobrevivir hasta el paso 10, lo
repite en cada slice, y lo detectado no queda en ningun sitio -la skill dice literalmente "cachea lo
detectado en la respuesta"-: nadie lo confirma, nadie lo ve, y la siguiente slice vuelve a empezar de
cero.

Ademas el orquestador ingiere la salida truncada de los controles que fallan (30 lineas por control)
solo para reenviarsela al implementador.

Las dos cosas son contaminacion de contexto en el agente de vida mas larga del loop, y ninguna
requiere su juicio.

## Decisiones

### 1. Renombrado: "puerta" pasa a ser "control"

"Puerta" es un calco de *gate*. En castellano la idea de "sitio donde te paran y no pasas si no
cumples" es un **control** (control de calidad, control de pasaportes): lleva dentro el bloqueo, que
"comprobacion" no tiene. Se descartaron por colision dentro de la propia skill: **verificacion** (es
el paso 7, el juez adversarial, y toda la arquitectura depende de separarlo de lo mecanico),
**prueba** (son los tests, uno de los tres controles) y **vara** (ya es la vara de medir de las
convenciones).

El renombrado llega a la prosa **y al codigo**.

### 2. Los controles se declaran en el cuerpo del issue

Seccion `## Controles`, hermana de `## Fuentes de convencion`, con la misma forma por repo:

```markdown
## Controles
- lint: make linting
- types: make check-types
- tests: make test

### mercadona/mercadona.online.gke
- controles: ninguno - la CI solo publica en master, no valida en PR
```

- Las lineas antes de cualquier `### <org>/<repo>` son las del repo del issue; cada subseccion, las
  de un repo destino de una slice con `REPO:`.
- Los pares `nombre: comando` son **libres**, no estan fijados a lint/types/tests: un repo de
  manifiestos puede declarar `schema: make validate-json`.
- Un repo sin controles reales (el de paneles de Grafana: la CI solo publica en `master`, no valida
  en PR) lo declara **explicitamente** con motivo, `- controles: ninguno - <motivo>`. Vacio y
  eximido no son lo mismo, igual que en `SENAL: exenta`.

Se elige el issue, y no el implementador ni el orquestador, porque reusa el mecanismo que ya existe:
`## Fuentes de convencion` nacio exactamente de este fallo -el agente asumiendo rutas fijas por
repo- y su forma resuelve las tres cosas a la vez. Se descubre una vez, lo **confirma el humano**
-que es quien sabe que este repo necesita `make env-start` antes, o que `make test` tarda 20 minutos
y en el bucle va `make test-unit`-, y queda como texto publico que nadie puede debilitar en privado.

La alternativa de que lo descubriera el implementador (contexto desechable, coste cero) se descarto
por un agujero: el orquestador necesita los comandos para el control de respaldo del paso 6, y
recibirlos del implementador significa que **el juzgado define la vara con la que se le juzga**. No
hace falta mala fe, basta `compliance-bias`: un agente presionado por entregar verde acaba eligiendo
`make test-unit` en vez de `make test`, y el respaldo re-correria fielmente el control debilitado.

### 3. `slice-spec` descubre, propone, el humano confirma

`discover_controles.py`, hermano de `discover_conventions.py` y en su mismo directorio
(`skills/slice-runner/scripts/`, que es de donde `slice-spec` ya invoca al de convenciones): lee los
targets del `Makefile` -con el comentario de encima como pista- y las senales de
`pyproject.toml`/`tox.ini`, y devuelve **candidatos, sin decidir**.
Luego el mismo baile de tres pasos que ya hace con las convenciones: el agente filtra y propone el
mapeo `nombre: comando` -> el humano confirma -> `issue_body.set_controles` lo escribe en el issue.

El modo `validate` comprueba que la seccion existe, esta bien formada, y que hay subseccion para cada
repo citado en un `REPO:` de alguna slice.

### 4. `slice-runner`: el paso 2 desaparece

- El paso 1 pasa a leer tambien `## Controles` y filtrarlos con `controles_para(controles,
  slice.repo)`. Si la seccion **falta, esta vacia**, o la slice declara `REPO:` y **su** subseccion no
  existe, **para** y pide `slice-spec validate`. Fail-closed, identico al trato de las fuentes de
  convencion: sin controles declarados no se ejecuta.
- Los pasos 5 y 6 usan los comandos declarados **tal cual**. Ningun agente vuelve a leer un
  `Makefile` en tiempo de run.
- Un repo con `controles: ninguno` se trata como capa eximida (delta 1 del paso 5): no se ejecuta
  ningun control y la verificacion real es post-deploy. Es el texto que ya vive en el paso 2 actual;
  se mueve, no se inventa.
- **Se elimina sin sustituto** el punto 3 del paso 2 ("identifica el workflow de `.github/workflows/`
  que corre en `pull_request`"). Es peso muerto ya hoy: el paso 9 espera con `gh pr checks --json`,
  que lista los checks sin necesitar el nombre de antemano.

### 5. La salida de build deja de pasar por el orquestador

El subcomando de ejecucion gana `--out <dir>`, **fuera del repo** (misma regla que `diff-bundle`: un
fichero de trabajo dentro nunca debe poder acabar en la PR). Escribe el log **entero** de cada control
fallido en `<dir>/<nombre>.log` y devuelve `veredicto + exit_code + ruta`, sin `salida` inline.

- El orquestador (paso 6) lee veredicto y rutas, y reenvia **rutas**. Nunca ingiere output de build.
- El implementador (paso 5) recibe rutas y lee el log **completo**, no 30 lineas truncadas: menos
  contexto arriba y mejor feedback abajo.
- Sin `--out` se conserva el `--tail` actual, que es lo util cuando lo lanza un humano en un terminal.

El control de respaldo del paso 6 **se mantiene**. Lo que no vale del paso 5 no es el output de los
controles -es el mismo script, mismo exit code, determinista- sino el **canal**: el orquestador no ve
las tool calls del subagente, solo su mensaje final en prosa. Lo que le llega no es un exit code sino
un agente afirmando "las corri y estan verdes", y los modos de fallo son mundanos: las corrio antes de
su ultima edicion, corrio un subconjunto, o resumio como "verde salvo un warning" lo que era un fallo.
Re-lanzar el script cuesta segundos de reloj y cero juicio; equivocarse cuesta quemar al verificador
contra un diff roto. Y con el log en disco su coste en contexto pasa a ser cero, que era la unica
objecion real.

### 6. Deriva de los comandos: no se hace nada especial

Si alguien renombra un target despues de crear el issue, el comando declarado deja de resolver y el
control **falla como cualquier otro**: el implementador rebota, agota sus 2 reintentos y la slice queda
`bloqueada: controles` con el log. Es una decision consciente y su coste esta aceptado: quema una
slice, y deja abierta la posibilidad de que el implementador intente "arreglar" el `Makefile` para que
el comando exista -la misma patologia que modificar un test preexistente para que pase-.

Cobertura parcial que ya existe y no hay que anadir: el implementador tiene prohibido tocar nada que
no sea codigo/test de la slice, `pr-hygiene` exige lista explicita, y un `Makefile` en el diff lo veria
el verificador.

Se descartaron un pre-flight determinista (`make -n <target>`, `command -v`) y una regla de reporte
para el implementador por no sobredimensionar: la deriva es rara y el fallo es recuperable.

### 7. Compatibilidad hacia atras del nombre viejo

Dos rastros de "puerta" viven **fuera del repo** y no se pueden renombrar por edicion:

- El marcador `bloqueada: puertas` esta escrito en cuerpos de issues abiertos ahora mismo.
- El valor `bloqueada-puertas` esta en registros historicos de `~/.claude/slice-runner/metrics.jsonl`,
  que es durable a proposito.

Ambos parsers siguen **aceptando la forma vieja** y emiten la nueva, y `metrics.py report` agrega las
dos como una sola categoria. Es el precedente exacto de `AC:` -> `ACEPTACION:`.

## Alcance del cambio

- `skills/slice-runner/scripts/gates.py` -> `controles.py`: subcomando `checks` -> `controles`, flag
  `--check` -> `--control`, clave JSON `gate` -> `control`, `--out` nuevo, identificadores al
  castellano (el vocabulario del fichero ya lo es: `veredicto`, `hallazgos`, `salida`).
- `skills/slice-runner/scripts/issue_body.py`: `parse_controles`, `tiene_seccion_controles`,
  `controles_para`, `set_controles`; y compatibilidad de `bloqueada: puertas`.
- `skills/slice-runner/scripts/discover_controles.py`: nuevo (junto a `discover_conventions.py`).
- `smoke/fixture/spec.md`: gana `## Controles` -y `## Fuentes de convencion`, que le faltaba ya-,
  porque se sube tal cual como cuerpo del issue y sin ellas el smoke pararia en el paso 1.
- `skills/slice-runner/scripts/metrics.py`: `bloqueada-controles` + agregacion de la forma vieja.
- `skills/slice-runner/SKILL.md`: borrar el paso 2, ampliar el paso 1, reescribir 5 y 6, renombrar.
- `skills/slice-spec/SKILL.md`: descubrimiento y declaracion de controles, y su `validate`.
- `agents/slice-verifier.md`, `CLAUDE.md`, `docs/`, `smoke/`: renombrado.
- `tests/test_gates.py` -> `tests/test_controles.py`, y tests nuevos de lo anadido.

## Criterio de hecho

`make check` verde (ruff + mypy strict + pytest), y ninguna aparicion de "puerta"/"gate" con el
sentido viejo en el repo salvo las dos compatibilidades declaradas en la decision 7.
