# Cerebro de slicing

Reference-doc de `slice-spec`. Se carga **solo cuando toca cortar** (`reference-docs` +
`context-management`): el `SKILL.md` no lo paga y el modo `validate` tampoco salvo que lo necesite.

Es la **fuente de verdad** del troceo para cualquier repo. Universal por defecto; los detalles
mecanicos (limite exacto de lineas, forma de la verificacion post-deploy) son *defaults* que un repo
puede afinar, no dogma.

## Filosofia

Cada cambio llega a produccion en la **slice mas pequena que aporta valor o reduce riesgo**. Slices
pequenas se revisan, despliegan y revierten mas rapido y con menor blast radius. El corte es
**vertical por defecto**: cada slice atraviesa las capas necesarias para entregar un cambio de
comportamiento observable, no una capa tecnica suelta que no vale nada hasta combinarse con otras.

## Criterios de validez (rasero de aceptacion)

Antes de dar una slice por buena, comprueba las cinco condiciones **y** el rasero INVEST:

1. **Reversible** — `git revert` deja el sistema coherente. Si la slice sustituye comportamiento ya
   en produccion, "reversible" incluye **reversible en runtime**: volver al anterior sin redeploy
   (feature flag o expand-contract).
2. **Desplegable sola** — no depende de codigo no mergeado ni de un orden de despliegue concreto.
3. **Sin work in progress oculto** — no introduce clases, campos ni ramas muertas que solo cobran
   sentido en una slice futura.
4. **Aporta valor o reduce riesgo** — entrega comportamiento, prepara infraestructura, o desbloquea
   la siguiente slice.
5. **Dentro del limite de tamano** — el diff cabe en el budget (ver "Defaults universales").

**INVEST** (Bill Wake) como chequeo rapido: *Independent, Negotiable, Valuable, Estimable, Small,
Testable*. "Small + Independent + Valuable" es, en la practica, tu "desplegable sola dentro del
budget".

## Procedimiento de corte

Guia eficiente: aplica de forma autonoma los pasos 1-2, presenta el set de slices con su
razonamiento, y **abre dialogo con la persona solo cuando el corte no es obvio o una slice se pasa
de tamano** (paso 3).

### 1. Walking skeleton / tracer bullet — la slice #1

La primera slice de una feature nueva es el **esqueleto andante**: la loncha mas fina de
funcionalidad real que se construye, despliega y prueba end-to-end de forma automatica. Prueba la
**arquitectura y el pipeline**, no la logica de negocio. El "tracer bullet" (Hunt & Thomas) es el
mismo concepto operativo: un disparo que atraviesa todas las capas y cuyo codigo **se queda**.

Si la feature toca arquitectura o integracion nueva, empieza siempre por aqui: el resto de slices
son incrementos que caen sobre este andamio.

### 2. Heuristica ordenada

Aplica la primera que funcione. Si una sola no basta para entrar en el budget, **combinala** con
otra (tipicamente vertical + horizontal). Este catalogo deriva de los *Patterns for Splitting User
Stories* (Richard Lawrence / Humanizing Work) y de SPIDR (Mike Cohn):

1. **Workflow steps** — divide por pasos del flujo. Camino feliz minimo primero, pasos opcionales
   despues.
2. **Happy path / casos borde** — el caso principal sin manejo sofisticado de errores primero; los
   bordes (validaciones, fallos, retries) en slices posteriores.
3. **Variaciones de input/datos** — soporta un tipo/formato/region primero, anade los demas despues.
4. **Reglas de negocio** — la regla por defecto primero; excepciones y calculos especiales aparte.
   (Tecnica valida: **relajar** temporalmente una regla y reimplementarla en una slice posterior.)
5. **Interfaces** (eje de SPIDR) — corta por **plataforma, navegador o dispositivo**: soporta una
   variante esta slice, las demas despues. Tambien: interfaz simple primero, enriquecida despues.
6. **CRUD** — Read antes que Create antes que Update antes que Delete, segun valor.
7. **Horizontal por capa** — cuando el vertical no cabe en una PR: infra/migracion, dominio,
   aplicacion, presentacion en PRs separadas. Ver "Aislamiento de infra". No es anti-patron: es la
   herramienta para no superar el budget cuando el vertical no entra.
8. **Esfuerzo / simple-complejo** — version hardcodeada o manual primero, automatizacion despues. O
   extrae el nucleo de complejidad como slice aparte (**major effort**: construye la infra con el
   primer caso y los demas salen casi gratis).
9. **Capacidades transversales aplazables** — performance, i18n, accesibilidad fina, **alertas y
   paneles**: slices propios cuando aporten valor, no bloqueando el core. **Ojo con la telemetria**:
   lo aplazable es la telemetria *fina* (dashboards, alerting calibrado, tracing exhaustivo); la
   **senal minima que hace observable la slice no es aplazable** y va dentro de ella (ver
   "Observabilidad de la slice").
10. **Spike** — si hay incertidumbre tecnica, un spike timeboxed que produce **conocimiento** (no
    codigo a prod) es una slice valida y explicita.

### 3. Hamburger method — motor de composicion (cuando ninguna heuristica dispara)

Cuando la feature es grande pero no tiene indicadores linguisticos de corte y las heuristicas de
arriba no dan un corte obvio, usa el metodo de la hamburguesa (Gojko Adzic) **con la persona**:

1. Lista las **tareas/capas** del flujo (consultar datos -> procesar -> notificar -> ...).
2. Para **cada capa**, genera 4-5 **opciones graduadas de calidad/esfuerzo**, de la mas cutre que
   aun vale a la mas completa (p.ej. "enviar email": manual -> automatico generico -> personalizado
   -> con unsubscribe -> integracion externa).
3. **Recorta la hamburguesa**: quita los niveles de calidad que el negocio no necesita.
4. **Primer bocado** = el nivel minimo aceptable de **cada** capa. Esa combinacion es la primera
   slice vertical.
5. **Siguientes bocados** = subir calidad de capas manteniendo consistencia entre ellas.

Es la unica tecnica que **genera opciones graduadas por capa** y las hace tangibles. La skill
`hamburger-method` es una profundizacion opcional si quieres facilitarlo mas a fondo; no es
necesaria para aplicar el procedimiento.

### 4. Calibrador de tamano — Elephant Carpaccio

Si una slice no cabe en el budget, **sigue lonchando**: casi todo se puede cortar mas fino de lo que
parece manteniendo la loncha vertical (Kniberg / Cockburn). El listón mental: cada loncha deberia ser
diminuta y seguir siendo entregable end-to-end.

Ejemplo canonico (calculadora de descuentos): entrada = items, precio, estado; salida = total con
descuento e impuesto. Lonchas: (1) leer dos numeros y multiplicar, imprime subtotal; (2) impuesto
fijo hardcodeado; (3) leer estado y elegir tax de una tabla; (4) primer tramo de descuento; (5)
resto de tramos; (6) formato de salida. Cada loncha se commitea, prueba y "entrega" antes de la
siguiente.

## Observabilidad de la slice

Cortar bien incluye decidir **como se vera vivo** lo que cortas. La regla: toda slice que cambia
comportamiento observable en produccion declara su linea `SENAL:` (como se comprueba viva); las demas
declaran `SENAL: exenta - <motivo>`. Ausencia silenciosa no es exencion.

El detalle -la escalera para decidir si hace falta instrumentar o la senal ya existe, el stack
concreto (libreria de monitoring, repo de alertas, repo de paneles), y como se redacta la linea- vive
en **`observabilidad.md`**: cargalo cuando el corte tenga senal que disenar.

Lo que si es del troceo:

- **Alertas y paneles son slices propias.** Viven en otros repos (⇒ PRs distintas por definicion) y se
  declaran con `REPO:` en su linea de slice.
- **Orden forzoso**: no se puede alertar ni pintar una serie que nadie emite. Primero la slice que
  emite la senal, luego (tras deploy y senal viva) la alerta, y por ultimo el panel. Es el mismo
  razonamiento que "Aislamiento de infra": despliega, observa, y luego el paso siguiente.
- **El panel es el mejor candidato al test de despriorizacion**: si tu set de slices no tiene ninguna
  posponible, el panel casi siempre lo es.

## Validacion del corte

Ademas de validar cada slice contra los criterios, valida el **conjunto**:

- **Test de despriorizacion** (Lawrence) — un buen set de slices tiene **al menos una que podrias
  tirar o posponer** sin perder el core. Si no puedes despriorizar ninguna, probablemente cortaste
  por trocear (horizontal disfrazado) en vez de por valor. Es el mejor detector de "slices sin
  valor".
- **Cadena de observabilidad completa** — si alguna slice emite una senal nueva relevante, el conjunto
  debe tener su slice de alerta (y de panel si aporta), o una **decision explicita** de no tenerlas. Que
  falten por olvido es como cortar sin criterios de aceptacion: se descubre en el incidente.
- **Igualdad de tamano** — prefiere slices de tamano parecido (cuatro de ~2 mejor que una de 5 + una
  de 3): maximiza la flexibilidad de priorizacion y evita la slice-monstruo escondida.

## Mecanismos de slicing seguro

Como llega una slice vertical a prod siendo reversible y desplegable sola sin romper nada:

- **Expand / migrate / contract** — (1) anade lo nuevo sin retirar lo viejo; (2) activa el nuevo
  camino (flag, dual-write, doble lectura); (3) retira el viejo cuando nadie lo usa.
- **Parallel changes** — para cambios que **sustituyen comportamiento ya en produccion**, es el
  **default**, no una opcion: nuevo adaptador/proveedor/regla detras de flag, viejo activo por
  defecto, y contract cuando el flag este al 100% tras un periodo de observacion. Sustituir in-place
  solo si la ruta no esta expuesta, no hay implementacion previa, o la conmutacion runtime es
  inviable (justificar).
- **Feature flags** — desplegar codigo oculto tras un flag permite mergear slices pequenas de forma
  continua; apagar el flag = rollback instantaneo. El walking skeleton suele vivir tras un flag
  hasta estar listo.
- **Branch by abstraction** — para reemplazos/migraciones grandes sin ramas largas: introduce una
  capa de abstraccion, migra la implementacion por debajo en slices pequenas, retira la vieja al
  final. Complementa expand/contract.
- **Dark launching** — ejecutar el camino nuevo en produccion sin exponerlo al usuario para validar
  con trafico real.
- **Aislamiento de infra y migraciones** — las migraciones de schema y los cambios de infra van en
  **PRs distintas** del codigo aplicativo que las consume: se despliega la migracion, se observa, y
  luego el codigo; permite rollback del codigo sin tocar la BD. Orden tipico para un campo nuevo:
  (1) migracion + columna nullable + modelo; (2) dominio + aplicacion + vistas que lo usan; (3)
  cleanup/backfill/contract.

## Defaults universales

- **Budget de tamano:** **~300-400 lineas de diff por PR** como default recomendado. Es una guia de
  blast radius, no una ley fisica; un repo puede afinarlo. Si una slice lo supera, trocearla.
- **Verificacion post-deploy:** cada slice que llega a prod define **como se comprueba su
  comportamiento vivo** — evidencia observable, ejecutable, con su assert y su via de rollback. Eso
  es exactamente la linea `SENAL:` del contrato de la spec, y quien la consume es `deploy-watch`. La
  **forma** depende del repo: un servicio HTTP mirara errores/latencia en el edge; una lib o CLI, una
  invocacion + salida esperada; un job, un efecto observable. No hardcodees el mecanismo HTTP como si
  fuera universal.

## Anti-patterns

- Mezclar migracion de schema con el codigo que la usa en la misma PR.
- Mezclar refactor con feature en la misma PR.
- Sustituir in-place un adaptador/proveedor ya en produccion sin flag ni expand-contract cuando
  existe implementacion previa (rollback solo via redeploy = blast radius innecesario).
- Slices que solo aportan andamiaje y no son desplegables solas.
- Anadir campos, metodos o clases "que necesitaremos en la slice siguiente".
- PRs que dependen de un orden concreto de merge para no romper produccion.
- Nombrar slices por capa tecnica cuando el corte vertical SI cabia en el budget (el horizontal es
  para cuando el vertical no entra, no por defecto).
- Slices que cambian comportamiento en prod **sin senal declarada** (ni exencion escrita): el deploy se
  valida entonces con el veredicto generico y nadie lo decidio.
- Meter la alerta o el panel **en la misma PR** que la metrica que consumen.
- Dejar el caso mas arriesgado para el final.
- Slices con "y"/"o" en el titulo que esconden varias features.
- Un set de slices donde **no puedes despriorizar ninguna** (senal de corte horizontal disfrazado).

## Fuentes

- Bill Wake — *INVEST in Good Stories, and SMART Tasks* (xp123.com, 2003).
- Richard Lawrence / Humanizing Work — *The Guide to Splitting User Stories* y *Story Splitting
  Flowchart* (patrones de corte + test de despriorizacion + igualdad de tamano).
- Gojko Adzic — *Splitting user stories: the hamburger method* (gojko.net, 2012).
- Mike Cohn — *SPIDR: Five Simple but Powerful Ways to Split User Stories* (Mountain Goat).
- Henrik Kniberg — *Elephant Carpaccio facilitation guide* (Crisp, 2013); ejercicio de Alistair
  Cockburn.
- Cockburn; Freeman & Pryce (*GOOS*) — walking skeleton. Hunt & Thomas (*The Pragmatic Programmer*)
  — tracer bullets.
