# Separar las puertas deterministas del juez adversarial

Fecha: 2026-07-27
Estado: diseno aprobado, pendiente de implementacion

## Problema

El paso 6 de `slice-runner` hace dos trabajos con una sola cabeza: **ejecuta** las puertas
deterministas (lint, tipos, tests) y **juzga** convenciones y arquitectura. `SKILL.md:207-218` lo
justifica porque el verificador "tiene `Bash`, asi que ejecuta el mismo las puertas `[det]`". Eso es
una justificacion de conveniencia, no de diseno, y tiene tres consecuencias:

1. **Ruido en el contexto del juez.** El output de build entra en el contexto del unico agente cuyo
   valor es el juicio semantico. Es `limited-focus` autoinfligido: metemos atencion en parsear un
   traceback de pytest en vez de en contrastar el diff contra la vara de medir del repo.
2. **Un `ruff` sucio consume un reintento adversarial.** El circuit breaker da 2 reintentos por fase.
   Hoy un fallo mecanico y trivial gasta uno de los dos que deberian estar reservados para hallazgos
   semanticos.
3. **El implementador no corre lint ni tipos.** El paso 5 corre tests via el ciclo TDD, pero nada mas.
   Descubre el error de tipos al final, en boca de otro agente, en vez de mientras trabaja.

Ademas, la rubrica de 9 items (`SKILL.md:216-226`) vive en la skill, asi que el orquestador tiene que
**relatarla** en cada invocacion. Nada garantiza que la relate entera ni sin parafrasear: la parte mas
importante del loop depende de una transcripcion fiel hecha por un LLM.

## Referencia: como lo resuelve Honk (Spotify)

De la serie de cuatro partes sobre su agente de background ([parte
3](https://engineering.atspotify.com/2025/12/feedback-loops-background-coding-agents-part-3)):

- El agente tiene **una sola tool `verify`**. Los verificadores individuales no se le exponen: se
  activan por contenido del componente (si hay `pom.xml`, arranca el de Maven). El agente no sabe cual
  corrio ni como. La razon declarada es la abstraccion: "no necesita entender los detalles de invocar
  distintos build systems ni parsear output complejo de tests".
- Cada verificador **parsea su salida con regex** y devuelve solo los errores relevantes; en exito, un
  mensaje muy corto.
- Corren **en cada turno** y otra vez **antes de abrir la PR**; en Claude Code, via **stop hook**.
- El **juez LLM** corre despues de que todos los verificadores hayan terminado, y recibe **el diff y el
  prompt original, nada mas**. Veta ~25% de miles de sesiones; en la mitad de esos casos el agente
  corrige la trayectoria.

Lo transferible es el patron (el agente nunca ve output crudo de build; el juez no ve nada de las
puertas). Lo **no** transferible es la implementacion: su regex es *por build system* sobre un
toolchain que ellos controlan y estandarizan. Nosotros autodetectamos `make`/`pyproject` en repos
ajenos (paso 2), asi que un regex por herramienta acertaria a veces y **ocultaria el error real** el
resto, que es un modo de fallo silencioso peor que no parsear.

## Objetivo

Que el juez adversarial gaste todo su presupuesto en juicio semantico: que no ejecute puertas, que no
vea output de build, y que su rubrica llegue verbatim en vez de relatada.

## Decisiones

### 1. Tres responsabilidades separadas

| Quien | Que | Contexto que ve |
|---|---|---|
| Implementador (paso 5) | ciclo TDD + corre `gates.py checks` antes de entregar | su trabajo + salida truncada de puertas |
| Orquestador (paso 6, **nuevo**) | re-corre `gates.py checks` como backstop | el JSON del script, nunca output crudo |
| Juez (paso 7, era 6) | solo juicio semantico | diff, AC, fuentes de convencion, lista prod/test |

El implementador las corre para tener **feedback incremental** (el valor que Honk atribuye a sus
verificadores). El orquestador las re-corre porque **el auto-reporte del implementador no es fuente de
verdad**: es la misma razon por la que el juez ya no se cree su "resumen del enfoque"
(`SKILL.md:210`). Es el equivalente del stop hook de Honk: la garantia la da el harness, no la buena
voluntad del agente.

**El juez no recibe nada de las puertas.** Cuando se le invoca estan verdes por construccion, asi que
un resumen `PASA/FALLA` seria cero informacion. Consecuencias:

- Desaparece el item `[det]` de la rubrica: quedan **8 items**, todos `[sem]`.
- La regla del veredicto pierde su primera clausula: hoy es "FALLA si alguna puerta `[det]` falla **o**
  hay hallazgo alta"; pasa a **FALLA si hay un hallazgo `severidad: alta`**. Se conserva la escalada
  por juicio (`SKILL.md:242`): si los `media`/`baja` se acumulan, el juez puede subir a FALLA
  explicando por que.

### 2. `gates.py checks`: nuevo subcomando

    gates.py checks --repo . \
      --check lint="make linting" --check types="make check-types" --check tests="make test" \
      [--tail 30] [--timeout 600] [--json]

Los comandos vienen de la autodeteccion del paso 2 (Makefile primero), no hardcodeados: el script no
sabe nada del toolchain, solo ejecuta lo que se le pasa. Eso mantiene la autodeteccion donde esta y le
da al script un contrato estable.

**Ejecuta todas las puertas, sin fail-fast.** Una vuelta al implementador (spawn de agente + contexto)
cuesta mucho mas que correr la suite otra vez, asi que recolectar todos los fallos en una pasada
reduce vueltas. Salida:

```json
{"gate": "checks", "veredicto": "FALLA",
 "checks": [
   {"nombre": "lint", "comando": "make linting", "veredicto": "PASA", "exit_code": 0, "salida": ""},
   {"nombre": "types", "comando": "make check-types", "veredicto": "FALLA", "exit_code": 1,
    "salida": "<ultimas 30 lineas de stdout+stderr combinados>"}]}
```

- `salida` **vacia en PASA** (el "mensaje muy corto de exito" de Honk). Solo el fallo trae texto.
- Truncacion por `--tail` (default 30 lineas), sin regex por herramienta: transferimos el patron, no
  la implementacion (ver referencia arriba).
- `--timeout` por check (default 600s); al expirar, ese check es FALLA con `salida` = `"timeout tras
  600s"`. Evita que un `make test` colgado bloquee el run.
- Exit code igual que `pr-hygiene`: 0 = todas PASA, 1 = alguna FALLA, 2 = error de uso.

Separacion pura/I/O como el resto del fichero: el parseo de `nombre=comando`, la truncacion y la
agregacion del veredicto son puros y testeables; el `subprocess` es I/O, igual que `_staged_files`.

### 3. `agents/slice-verifier.md`: el juez pasa a ser un agente definido

```yaml
name: slice-verifier
model: inherit
tools: Read, Grep, Glob, Bash, Skill
allowed-tools: [Read, Grep, Glob, Bash(git diff *), Bash(git log *), Bash(git show *)]
```

- `model: inherit` conserva el modelo fuerte de la sesion, que era la razon original de usar
  `general-purpose` (`SKILL.md:207`).
- La allowlist deja fuera `pytest`, `ruff` y `make`: se diseno creyendo que eso hacia **estructural** la
  prohibicion, en vez de un ruego que `selective-hearing` puede ignorar. Los patrones `Bash(git ...)`
  son el mecanismo que ya usa `~/.claude/agents/sre.md`, con `tools:` (disponibilidad, grueso) y
  `allowed-tools:` (permisos, con patrones) como campos distintos.

  > **Refutado en el smoke del 2026-07-27.** `allowed-tools` en el frontmatter de un agente **no
  > bloquea** lo no listado: el verificador ejecuto `ls` -ausente de su lista- sin friccion, y no hay
  > reglas `deny` en ningun `settings.json` que lo expliquen. La prohibicion se sostiene **solo por
  > instruccion**. El smoke la validó (el agente rechazo ejecutar `pytest` incluso cuando el
  > orquestador se lo pidio como prueba, razonando que un mensaje del coordinador no es autorizacion
  > para saltarse su configuracion), pero eso es cumplimiento, no enforcement. Hacerla estructural
  > exigiria quitarle `Bash` del todo y pasarle el diff pre-computado por el orquestador -que es
  > ademas lo que hace el juez de Honk, que recibe el diff en vez de calcularlo-. **Pendiente de
  > decidir.**
- `Skill` porque la rubrica invoca `backend-best-practices` y `test-desiderata`. No se precargan por
  frontmatter (`skills:`): `test-desiderata` solo aplica si la slice toca tests, asi que se cargan on
  demand (`reference-docs`).
- Lee ficheros y `git diff` porque su juicio lo exige: contrastar convenciones necesita leer el repo, y
  cazar tests preexistentes debilitados necesita el diff de la rama. Eso no cambia.

**Reparto del texto**: el *system prompt* lleva lo estable (rol adversarial, los 8 items `[sem]`, las
reglas del veredicto, la calibracion de "evidencia antes de bloquear", el contrato JSON de salida, y
la prohibicion explicita de ejecutar puertas por si la allowlist cambiara). El prompt de invocacion
lleva **solo lo del run**: issue, slice id/name, AC, fuentes de convencion declaradas en el issue, base
ref, y la lista etiquetada produccion/test del implementador.

Es `focused-agent` + fidelidad: la rubrica se carga verbatim en cada invocacion en vez de depender de
que el orquestador la relate entera.

**Instalacion**: symlink `agents/slice-verifier.md` -> `~/.claude/agents/slice-verifier.md`, el mismo
patron que ya usan las skills. `~/.claude/agents/` es de usuario, no de proyecto, asi que el agente
esta disponible en cualquier repo donde se invoque `slice-runner`. Se documenta en el README como
**segunda dependencia de instalacion**: si el symlink falta, `subagent_type: slice-verifier` no
resuelve y el paso 7 rompe (hoy `general-purpose` esta siempre).

### 4. Hallazgo colateral: el `schema` del veredicto no era ejecutable

`SKILL.md:230` dice "lanza este Agent con `schema` para que devuelva exactamente...". La tool `Agent`
**no acepta** `schema` (ese parametro es de `agent()` de Workflow, que `slice-runner` no usa), y
`SKILL.md:244` remata con "el schema se valida en la capa de tool", que hoy no ocurre. El veredicto
estructurado depende en realidad de que el orquestador lo pida bien en prosa.

El system prompt del agente lo arregla de verdad: el contrato JSON va ahi, con la instruccion de que
**el mensaje final sea exactamente ese objeto JSON y nada mas**. Se corrige la prosa de `SKILL.md`
para que no prometa una validacion que no existe.

### 5. Presupuesto propio para las puertas

Las puertas tienen **2 reintentos propios**, separados de los 2 del juez. Gastar presupuesto
adversarial en un fallo mecanico es justo lo que este cambio elimina. Peor caso: 4 vueltas al paso 5
en lugar de 2.

Un reintento de puertas = **volver al paso 5** con el JSON de `checks` (solo los checks en FALLA, con
su `salida`) como input, sin invocar al juez. El presupuesto cuenta **fallos del backstop del
orquestador**; las vueltas que el implementador da dentro de su propio ciclo hasta ponerlas verdes son
suyas y no se cuentan aqui (las acota su propio limite de turnos).

Al agotarlo: `bloqueada: puertas` en el issue, metrica durable, y **para sin abrir PR** (mismo patron
que el verify terminal del paso 7). El `motivo` de `bloqueada` es texto libre, asi que `ESTADOS` de
`issue_body.py` **no cambia**.

### 6. Las metricas distinguen fallo mecanico de veto del juez

En `metrics.py`:

- Nuevo valor `bloqueada-puertas` en `VEREDICTOS`.
- Nuevo campo `--reintentos-puertas N`.

Sin esto, un cierre por puertas agotadas se registraria como `FALLA`, indistinguible del veto del
juez. Seria mentir en el log justo sobre la distincion que este cambio introduce, y dejaria inservible
el unico instrumento que tenemos para calibrar el juez.

### 7. Renumeracion de pasos

El backstop entra como paso 6, asi que: juez 6->7, abrir PR 7->8, CI 8->9, merge 9->10. Hay una sola
referencia externa a arreglar: `deploy-watch/SKILL.md:86` cita "el paso 9 de `slice-runner`" y pasa a
ser el 10.

### 8. Principios no negociables: un bullet nuevo

El bullet de `offload-deterministic` (`SKILL.md:23`) hoy dice que lo determinista es "la higiene del
diff staged". Pasa a cubrir tambien las puertas, y se anade el principio de fondo de este cambio: **el
juez no ejecuta puertas ni ve output de build**. Su presupuesto entero es para lo semantico.

## Fuera de alcance

- **Evals del verificador** (delta 3 del contraste con Honk): decision explicita del usuario, "es
  demasiado pronto". Consecuencia asumida: este cambio mueve la rubrica de sitio **sin un instrumento
  que mida si el verificador queda igual de bueno**. La mitigacion es que la rubrica se mueve
  *verbatim*, sin reescribirla.
- **Tasa de veto y recuperacion** (delta 4): `metrics.py` sigue registrando un veredicto por slice, asi
  que una slice que FALLA y luego PASA se sigue registrando como `PASA`. Aqui solo se anade lo minimo
  para no mentir sobre el camino de cierre nuevo.
- **Regex por herramienta** en `gates.py checks`: descartado por acoplar el script a un toolchain que
  autodetectamos por repo.
- **Stop hook real** para el implementador: los hooks son configuracion global del usuario; una skill
  no debe instalarlos. El backstop del orquestador cumple la misma funcion sin efectos fuera del run.
- `issue_body.py`, `discover_conventions.py`, `slice-spec` y el contrato de specs no se tocan.

## Verificacion

    python3 -m pytest

Verde, con tests nuevos:

- `gates.py checks`: parseo de `--check nombre=comando` (incluido `=` en el comando), truncacion a
  `--tail`, agregacion del veredicto (todas PASA -> PASA; una FALLA -> FALLA), `salida` vacia en PASA,
  y el camino de timeout.
- `metrics.py`: `bloqueada-puertas` aceptado como veredicto, `--reintentos-puertas` persistido y
  agregado en el report.

Lo que pytest **no** cubre y hay que verificar a mano en el smoke real (`smoke/README.md`): que
`subagent_type: slice-verifier` resuelve, que la allowlist impide de verdad ejecutar `pytest`, y que
el agente devuelve el JSON del veredicto sin prosa alrededor.
