# Desduplicar slice-runner contra superpowers (delegar el ciclo TDD)

Fecha: 2026-07-27
Estado: diseno aprobado, pendiente de implementacion

## Problema

`slice-spec` ya envuelve `superpowers:brainstorming`, pero `slice-runner` **no referencia
superpowers en ningun punto**: reescribe de su cuenta el ciclo TDD y la integridad de tests
(`SKILL.md:24,170-177`), que `superpowers:test-driven-development` (320 lineas) ya cubre
—red-green-refactor con "watch it fail" obligatorio, asertar comportamiento real, "test falla ->
arregla el codigo, no el test"— y que ademas referencia `writing-good-tests.md`.

Esa prosa duplicada es la que se desincroniza: superpowers lo mantiene un tercero y va por la
6.2.0. Cada version suya que refine el ciclo deja el texto de `slice-runner` un poco mas viejo, sin
que nada lo senale.

Complicacion: la Iron Law de superpowers es absoluta ("NO PRODUCTION CODE WITHOUT A FAILING TEST
FIRST", sin excepciones sin permiso humano) y **contradice** el TDD consciente de capa de
`slice-runner`, que exime las capas que la convencion del repo no testea por separado (modelos ORM,
migraciones alembic). Delegar sin declarar precedencia mete la contradiccion en el prompt del
implementador (`selective-hearing`: cuando dos reglas chocan, el modelo elige la que mas suena en su
entrenamiento, y aqui ganaria la Iron Law).

## Objetivo

Que el ciclo TDD tenga **una sola fuente** (superpowers) y que en `slice-runner` viva unicamente lo
que es suyo y no esta ahi: la exencion por capa, la integridad de tests preexistentes, el refactor
tras cada verde, y el estatus de los tests como ciudadanos de primera categoria. Y que la
divergencia deliberada del verificador respecto a `superpowers:requesting-code-review` quede escrita,
para que nadie la "arregle".

## Decisiones

### 1. El implementador (paso 5) invoca la skill, con precedencia explicita

El prompt del implementador **invoca** `superpowers:test-driven-development` (no lo resume: es
`reference-docs`, y un subagente tiene contexto fresco, asi que cargar ahi 320 lineas no cuesta
`context-rot`). Encima se declara la cadena de precedencia, que es lo que desactiva el choque:

    convenciones del repo > exencion de capa > Iron Law de superpowers

Se borran de `slice-runner` los tres bloques de prosa TDD (`SKILL.md:170-177`) y se quedan solo los
deltas:

- **Exencion de capa.** En capas que la convencion del repo no testea por separado, la puerta es
  "suite intacta + efecto verificado", no test-first por AC.
- **Integridad de tests preexistentes.** Superpowers solo dice "arregla el codigo, no el test"; el
  delta es la regla de hierro completa: prohibido relajar asserts, borrar tests o anadir
  `@skip`/`xfail` para acomodar la implementacion.
- **Refactor tras cada verde**, no diferido a una pasada final (la evidencia empirica lo senala como
  el driver de calidad real en agentes).
- **El esfuerzo va al test.** El presupuesto de calidad del implementador se gasta en que el test
  fije de verdad su AC, no en ponerlo verde.

### 2. Los tests como ciudadanos de primera categoria (principio no negociable nuevo)

Los tests valen tanto o mas que el codigo de produccion: ahi va el mayor esfuerzo de calidad, y sobre
todo la exigencia de que **testeen de verdad lo que la slice pretende construir**, no una version
debilitada ni un proxy que pasa por casualidad. Un test que pasa sin fijar su AC es un fallo tan
grave como codigo roto.

Con dientes, no como declaracion: el implementador aplica `writing-good-tests.md` de superpowers
(nombrar el cambio de produccion que haria fallar el test **antes** de escribirlo, asertar
comportamiento real y nunca mocks, codigo de test fuera de produccion), y el verificador ya lo
bloquea con severidad **alta** en el paso 6 (mapeo AC↔test, fixture/wiring theater, manipulacion de
tests, test-desiderata). El principio nombra la exigencia y **cita** donde se ejecuta; no repite esos
checks.

### 3. El resumen de arriba no repite la regla delegada

El bullet "TDD consciente de capa" de `Principios no negociables` (`SKILL.md:24`) hoy reenuncia la
regla completa. Pasa a apuntar a superpowers para el ciclo y a conservar solo el delta de exencion.
Si no, el resumen de la cabecera y la fuente delegada divergen a la primera version nueva de
superpowers.

### 4. La divergencia del verificador se documenta como intencionada

El paso 6 ya explica que el verificador **no re-testea** (evidencia empirica: split authorship costo
3x sin ganancia consistente porque los AC ocultos ya gobernaban la correccion). Lo que falta es
**nombrar** que eso significa no usar `superpowers:requesting-code-review`, que si re-revisa el
codigo. Sin esa frase, el proximo que compare las dos skills lo lee como un olvido y lo acopla.

Ademas, el item `[sem]` de TDD consciente de capa cita que la vara es la del paso 5 (delegada), para
que implementador y verificador no midan con reglas distintas si una de las dos cambia.

### 5. Contraparte upstream: los AC de `slice-spec` deben ser falsables

El principio de la decision 2 tiene dientes via el **mapeo AC↔test** del paso 6, y ese check solo
puede medir si el AC es refutable. `slice-spec` declaraba en sus principios AC "concretos y
comprobables", pero su checklist de `validate` solo comprobaba que **existieran** (`al menos una
linea AC:`): un AC como "el flujo funciona correctamente" pasaba el gate y luego dejaba al verificador
sin nada contra lo que mapear, tumbando el principio en origen.

Se anade la **vara de falsabilidad**, la misma que superpowers usa para los tests en
`writing-good-tests.md`: un AC vale si puedes nombrar el **cambio de produccion que lo haria fallar**.
Entra en tres sitios de `slice-spec/SKILL.md` -principio, regla dura del contrato (con ejemplo
valido/invalido) y checklist de `validate`, donde un AC no falsable pasa a ser **la desviacion a
corregir**-. El modo autoria lo hereda: su paso 5 ya aplica el checklist de `validate` antes de crear
el issue, asi que no se duplica prosa en el paso 2.

No cambia el contrato de parseo: `issue_body.py` sigue viendo las mismas lineas `AC:`. La
falsabilidad es un juicio `[sem]`, no una regla mecanica, asi que no se puede offloadear a script.

## Fuera de alcance

- **`superpowers:verification-before-completion`**: las puertas de `slice-runner` ya son
  deterministas con exit code autoritativo (`gates.py`, items `[det]` del paso 6,
  `gh pr checks --json` en el paso 8). Anadir su prosa no cambiaria ningun comportamiento: seria
  justo el relleno que este cambio quita.
- **Fallback si superpowers no esta**: se da por presente (decision del usuario).
- El contrato de specs, `gates.py`, `issue_body.py`, `metrics.py` y `slice-spec` no se tocan.

## Verificacion

Ningun script cambia, luego `python3 -m pytest` debe seguir verde **sin tocar tests**: es la
comprobacion de no-regresion de que el cambio es solo de prosa de la skill.
