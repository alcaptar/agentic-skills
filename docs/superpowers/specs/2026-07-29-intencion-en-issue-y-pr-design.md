# La intencion como parte del contrato: en el issue y en el cuerpo de la PR

Fecha: 2026-07-29
Estado: diseno aprobado, implementado

## Problema

Un issue creado por `slice-spec` no cuenta **por que** existe la feature. Su cuerpo arranca en
`## Fuentes de convencion` y sigue con `## Slices`: cada slice trae lo que hay que cumplir (`AC:`) y
como se comprueba viva (`SENAL:`), pero nada dice que esta mal hoy. El titulo es lo unico que insinua
el motivo, y un titulo no es un motivo.

Aguas abajo eso se paga en la pull request. El paso 8 de `slice-runner` pedia un cuerpo que "lista los
AC cumplidos, nombra la `SENAL` ... y **resume los cambios**". Ese ultimo trozo es el problema: un
resumen en prosa del diff es la peor parte del cuerpo de una PR, porque **compite con el diff en lo
que el diff hace mejor** y ocupa el sitio de lo unico que el diff no puede contar. El revisor ve
perfectamente que se anadio un value object; lo que no ve es que antes cada endpoint revalidaba a mano
y ya se habia olvidado en dos sitios.

Hay un tercer sintoma, menos visible: el implementador (paso 5) recibe AC y `SENAL`, o sea **que**
tiene que cumplirse y **como** se comprueba, pero nunca **para que**. Es el terreno donde nace la
solucion tecnicamente correcta y funcionalmente inutil.

## Diseno

La intencion pasa a ser parte del contrato de formato, en dos niveles.

**Nivel feature: seccion `## Intencion`**, la primera del cuerpo del issue. Que esta mal hoy (o que no
se puede hacer hoy), a quien le pasa y como se nota. Tres a seis lineas, sin nombrar clases, ficheros
ni patrones: el como vive en las slices y en el codigo.

**Nivel slice: linea `INTENCION:`**, junto a `AC:` y `SENAL:` y **antes** que ellas. El orden no es
estetico: primero el por que, luego lo que se comprueba antes de fusionar, luego lo que se comprueba
vivo.

```markdown
## Intencion
Hoy el ajuste de stock se hace a mano en la consola: no queda rastro de quien lo hizo
y cuando el recuento no cuadra no hay forma de reconstruir que paso.

## Fuentes de convencion
- doc: .claude/CLAUDE.md

## Slices
- [ ] slice-01 (ajustar-stock): Caso de uso AjustarStock [pendiente]
      INTENCION: hoy el ajuste se hace a mano y no queda rastro de quien lo hizo
      AC: emite evento StockAjustado
      SENAL: prometheus rate(stock_ajustado_total[5m]) > 0 en 10m post-deploy; critical
```

### La vara: el coste de no hacerlo

Cada regla del contrato tiene su vara de falsabilidad -los AC nombran el cambio de produccion que los
rompe, la senal nombra serie, ventana y assert-. La de la intencion es: **si borras la slice, que queda
roto o imposible?** Si no puedes nombrarlo, la linea es relleno y hay que reescribirla.

- Cumple la vara: `INTENCION: hoy se pueden pedir cantidades negativas y el stock queda en negativo
  sin que nadie se entere`.
- Hay que reescribirla: `INTENCION: mejorar la validacion del dominio`. Borrala y no queda nada roto
  que puedas nombrar.

Tambien hay que reescribir la que describe el codigo en vez del problema (`introducir el value object
Cantidad en el aggregate`): eso es exactamente lo que el diff ya cuenta.

**No hay figura de exencion**, a diferencia de `SENAL: exenta - <motivo>`. Una slice sin por que no
deberia existir. Las slices sin efecto observable en produccion (refactor, value object interno)
tambien tienen intencion; su coste es interno, pero se puede nombrar. Y si al escribir la linea
descubres que no sabes nombrar nada, la senal no es "redactar mejor": es que la slice sobra o esta mal
cortada, y eso se arregla volviendo al troceo.

### El cuerpo de la PR

Desaparece "resume los cambios". El cuerpo queda:

```markdown
## Intencion
<la INTENCION de la slice, encuadrada en una frase de la del issue>

## Criterios de aceptacion cumplidos
- <un AC por linea, con donde vive su test>

## Senal a comprobar tras el despliegue
<la linea SENAL de la slice, o "exenta - <motivo>">

Part of #<N>
```

Con una regla explicita: no enumerar ficheros, clases ni modulos, ni narrar el diff.

### Issues anteriores a este mecanismo

`slice-spec` exige la intencion al crear, y su modo `validate` la trata como desviacion a corregir con
la persona. Pero `slice-runner` **no para** si falta: avisa, reconstruye la intencion desde el contexto
del issue y **lo declara en el encabezado** (`## Intencion (inferida del issue, no declarada)`). El
trato es el mismo que con `SENAL` ausente, y por el mismo criterio que gobierna toda la skill: se
degrada cuando la degradacion **se puede declarar en el artefacto que produces**. Aqui se puede, y en
el sitio donde la lee quien revisa.

Bloquear habria dejado a medias cualquier issue ya abierto, a cambio de una coherencia que no compra
nada: sin intencion se implementa igual de bien.

### Quien mas la ve

- **El implementador (paso 5): si.** Recibe la intencion junto a los AC, porque los AC dicen que tiene
  que cumplirse y la intencion dice para que. No es licencia para ampliar el alcance: si la intencion
  pide mas que los AC, eso se reporta, no se implementa de mas.
- **El verificador (paso 7): no.** Su mandato son los AC y las convenciones del repo. Darle el por que
  le invita a hallazgos fuera de contrato, y su presupuesto adversarial es escaso a proposito.

### Parte determinista

`issue_body.py` gana:

- `Slice.intencion: list[str]` y `_INTENCION_LINE_RE` (acepta `INTENCION` e `INTENCIÓN`, por el mismo
  motivo que `SENAL`: lo escribe una persona en un issue).
- `parse_intencion(body) -> str | None` para la seccion de feature.

Sin esto la intencion no habria llegado a la PR: el parser **descarta en silencio** cualquier linea
hija que no sea `AC:`/`SENAL:`/`REPO:`, asi que se habria escrito en el issue y se habria perdido entre
el paso 1 y el paso 8.

`parse_intencion` distingue tres casos a proposito: `None` (seccion ausente), `""` (presente pero
vacia) y el texto. Los dos primeros degradan igual, pero **quien decide cual es es el script, no el
criterio del agente**: es lo que impide que una PR presente como declarado algo que se invento.

## Cambios

- `skills/slice-spec/SKILL.md`: principio de la intencion con su vara; `## Intencion` e `INTENCION:` en
  el contrato de formato con sus reglas duras; paso 2a de autoria; checks nuevos en modo `validate`.
- `skills/slice-runner/SKILL.md`: principio "la PR cuenta la intencion, no el codigo"; formato de spec;
  lectura en el paso 1 (con la anotacion de "habra que inferirla"); la intencion al implementador en el
  paso 5; cuerpo de la PR del paso 8 reescrito.
- `skills/slice-runner/scripts/issue_body.py`: campo `intencion`, regex y `parse_intencion`.
- `tests/test_issue_body.py`: parseo de la linea (con y sin tilde), ausencia como lista vacia, no
  confundirse con `AC:`/`SENAL:`, los tres casos de `parse_intencion`, y preservacion de la intencion
  al reescribir estado y fuentes.
- `CLAUDE.md`, `README.md`, `smoke/README.md`, `smoke/fixture/spec.md`: el contrato nuevo y el criterio
  de smoke OK para el cuerpo de la PR.

## Lo que este diseno no hace

- **No cambia la etiqueta `AC:`** por su nombre completo, aunque sea una sigla: esta en issues vivos y
  renombrarla es otro cambio, con su migracion.
- **No pone puerta determinista sobre la calidad de la linea.** "Nombra el coste de no hacerlo" no es
  comprobable por script; la vara vive en el texto de `slice-spec` y la aplica su modo `validate` con
  la persona. Lo determinista es solo si la linea **existe**.
