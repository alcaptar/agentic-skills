# Autodeteccion de fuentes de convencion (slice-spec + slice-runner)

Fecha: 2026-07-24
Estado: diseno aprobado, pendiente de implementacion

## Problema

`slice-runner` (y `slice-spec`) cargan la vara de medir de convenciones desde rutas
fijas: `docs/conventions/` + `CLAUDE.md` en raiz (ver `slice-runner/SKILL.md:21,143,157,189`).
El repo destino `mo.picking.api` publica sus convenciones en OTRAS rutas
(`.claude/CLAUDE.md`, `.claude/rules/conventions/`, `.claude/skills/`), asi que el
"si existen" de la instruccion cae a vacio: implementador y verificador ejecutan **sin
vara de medir** y caen al default generico de hexagonal/DDD + memoria en contexto.

Consecuencia observada (bucle 3 de la migracion hermes): cuatro correcciones humanas,
todas de convencion (constante de retry, rename a `Legacy*`, naming de topic, test que
duplica comportamiento), pese a que tres de ellas estaban escritas en `delivery.md` y
`testing.md` y en la skill de proyecto `duplicate-action`. La compactacion entre slices
fue el agravante que retiro la muleta de memoria; la causa raiz es el **desajuste de
ruta** entre la skill y el repo.

Patrones implicados (`ai-patterns`): `silent-misalignment` (seguir sin criterio sin
avisar), y la cura es `offload-deterministic` + descubrimiento robusto en lugar de
rutas asumidas.

## Objetivo

Que la vara de medir de convenciones se **descubra** por repo en vez de asumirse en
rutas fijas, se **confirme** con el humano una vez, y se **persista como punteros** en la
unica fuente de verdad viva del run: el cuerpo del issue de GitHub. Sin rutas
hardcodeadas, sin estado local, sin duplicar el contenido de las convenciones.

## Decisiones

### 1. Que se persiste: punteros, en el issue

Nueva seccion en el cuerpo del issue, `## Fuentes de convencion`, con **punteros
confirmados** (no contenido). Dos tipos:

- **Docs de convencion** (declarativo): rutas a lo que haya en el repo
  (`.claude/rules/conventions/`, `.claude/CLAUDE.md`, `docs/conventions/`,
  `CONTRIBUTING.md`, ...).
- **Skills de proyecto** (procedimental): rutas a skills del propio repo destino que
  codifican patrones (`.claude/skills/duplicate-action`,
  `.claude/skills/deprecate-hermes-handler`, ...). El verificador las abre/invoca y las
  **cita** igual que una regla.

Nunca se copia el contenido de las convenciones al issue: viven en su repo
(single-source); duplicarlas las desincronizaria. El issue guarda solo el "donde".

Formato propuesto (estable, parseable):

```markdown
## Fuentes de convencion

- doc: .claude/CLAUDE.md
- doc: .claude/rules/conventions/
- skill: .claude/skills/duplicate-action
- skill: .claude/skills/deprecate-hermes-handler
```

### 2. Como se descubren: glob heuristico + juicio + confirmacion

Sin rutas fijas. Un helper determinista hace un **glob amplio de candidatos** (ficheros
tipo `CLAUDE.md`/`AGENTS.md` a cualquier nivel, directorios cuyo nombre contenga
`convention`/`rules`, `CONTRIBUTING*`, `.claude/skills/*`) y **devuelve la lista**; no
decide. El agente juzga cuales son convencion real, los **propone**, y el humano
**confirma**. Si el glob no encuentra nada plausible o el humano no confirma nada, se
**para y se pregunta**: nunca se sigue con la vara vacia.

### 3. Reparto de responsabilidades

- **`slice-spec` crea.** Al montar el issue, corre el descubrimiento -> propone ->
  confirma -> escribe la seccion `## Fuentes de convencion`. Su modo `validate` sirve
  para anadir la seccion a un issue ya existente (p. ej. issues legacy sin la seccion).
- **`slice-runner` solo consume.** Al arrancar cada slice: lee la seccion (comprobar si
  existe es mecanico). Si existe, implementador y verificador cargan esos punteros como
  vara de medir. Si falta, **para y avisa** de anadirlas con `slice-spec`. No descubre
  ni escribe (sin logica de backfill: descartado por YAGNI).

Cada slice re-lee el issue (contexto fresco), asi que la compactacion ya no puede
degradar esta informacion.

### 4. Determinismo (`offload-deterministic`)

- Extender `slice-runner/scripts/issue_body.py` para **detectar / parsear / emitir** la
  seccion de fuentes (existe o no, y la lista de punteros). Comprobacion mecanica ->
  script, no juicio de IA.
- El **glob de candidatos** es un helper determinista (lista, no decide).
- El **juicio** (que es convencion) y la **confirmacion** los hacen agente + humano.
- Actualizar el texto de las skills que hoy fijan rutas:
  - `slice-runner/SKILL.md:21,143,157,189` ("cargar `docs/conventions/` + `CLAUDE.md`")
    -> "cargar las fuentes declaradas en la seccion `## Fuentes de convencion` del issue".
  - El punto equivalente de `slice-spec/SKILL.md` -> el nuevo paso de descubrimiento +
    confirmacion + escritura de la seccion.

### 5. Tests

- `tests/` para `issue_body.py`: parse, emit, y el caso "seccion ausente".
- El glob helper contra un arbol de ficheros de prueba.
- La I/O contra `gh` la valida el smoke real (`smoke/README.md`).

## Fuera de alcance

- **Backfill en `slice-runner`**: descartado. Los issues legacy se arreglan pasando por
  `slice-spec validate`.
- **Copiar el contenido de las convenciones al issue**: no. Solo punteros.
- **Rutas fijas / lista canonica cerrada**: no. El glob es amplio y el humano confirma;
  el objetivo es no volver a asumir una ubicacion.

## Trazabilidad con los principios del repo

- Estado del run en el issue (SSOT viva): las fuentes viven en el issue, no en local ni
  en `.claude/settings.json` del repo destino.
- El que implementa no verifica: ambos subagentes cargan la MISMA vara declarada, cazando
  desviaciones de convencion que antes pasaban.
- Determinista lo que es regla exacta: deteccion/parseo por script; juicio por agente.
