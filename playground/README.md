# Playground

Banco de experimentos controlados sobre **como se le habla al modelo**. Responde preguntas de
componente -¿se cumple esta regla si la entrego asi?- por unos dolares y en minutos, en vez de
deducirlas de slices reales que cuestan entre 5 y 26 dolares cada una.

No responde preguntas de sistema (¿bajar los reintentos cierra mas slices?): esas se miden con el
rastro durable de `~/.claude/slice-runner/`, y hasta que no haya del orden de treinta slices
comparables no hay nada que mirar. El playground mide componentes; el rastro mide el sistema.

## Como se lanza

```bash
uv run python playground/harness.py <tarea> --label <etiqueta> \
  --variants none pointer injected skill --seeds seed-bare --repetitions 5
uv run python playground/harness.py <tarea> --label <etiqueta> --report-only
```

Los arboles de trabajo se escriben en `~/repos/as-playground/runs/<etiqueta>/`, **fuera del repo**, y
ahi se quedan para poder mirarlos. El motivo esta abajo y no es cosmetico.

## Que es una tarea

Un directorio en `tasks/` con:

| Que | Para que |
|---|---|
| `seed-*/` | El arbol que se copia limpio a cada repeticion |
| `task.py` | `VARIANTS` (cada una compone el prompt y prepara el arbol) y `measure(tree)` |

`measure` devuelve **un resultado por regla**, no un booleano: `True`, `False`, o `None` cuando la
regla no aplica a lo que se escribio. Con una medida binaria unica te quedas sin experimento en cuanto
la tarea satura; con doce reglas, la que satura se tira y quedan once.

El arnes **no juzga**: la medida la escribe la persona por tarea, y es una funcion determinista del
arbol resultante. En cuanto el que mide es un modelo, su varianza se suma a la del sujeto y hacen
falta muchas mas repeticiones para el mismo poder.

## El metodo, que es lo unico que se ha validado tres veces

Tarea fija, **una sola variable**, cinco repeticiones, medida objetiva sobre el arbol resultante. De
las hipotesis medidas asi hasta hoy, **dos de tres resultaron falsas**: medir antes de construir es la
norma y no el adorno. Los resultados se escriben en `docs/design-notes.md` con sus numeros,
**incluidos los empates**: un experimento que no distingue tambien es un resultado.

## Los cinco fallos que ya se han cometido

Estan aqui porque los cinco cuestan dinero y ninguno avisa: el experimento sale, da un numero, y el
numero miente.

1. **Contaminacion por disco.** La variante "sin el documento" tiene que ser un arbol donde el
   documento **no exista**, no un arbol donde se pida no mirarlo. La primera version copiaba el
   fichero al arbol de las dos variantes y el modelo lo abria con `Read`. Por eso el prompt se compone
   fuera del arbol y cada variante prepara el suyo.
2. **El `CLAUDE.md` del repo anfitrion.** Si el arbol de trabajo vive dentro de `agentic-skills`,
   `claude -p` carga su `CLAUDE.md`, que ordena leer las convenciones: las cuatro variantes quedan
   contaminadas y la de control deja de ser control. Por eso `RUNS` apunta fuera del repo.
3. **Techo.** Una tarea que la linea base ya cumple no discrimina, y el empate se lee como "da igual"
   cuando lo que pasa es que no habia nada que medir. Se calibra corriendo **la variante de control
   primero** y tirando lo que satura. La tarea `conventions-channel` satura en ocho de sus doce reglas
   y mide con las otras cuatro.
4. **Respuesta deducible del contexto.** Si el modelo puede inferir la regla del codigo de alrededor,
   quitarle el documento no cambia nada. Por eso hay dos semillas: `seed-bare` mide el poder del
   documento solo, y una semilla poblada mediria lo que anade **encima de** la imitacion, que es el
   escenario real.
5. **Medida fragil.** Antes de gastar, la medida se calibra contra un arbol que **si** cumple
   -`src/slice_runner/`-: si ahi no sale todo verde, el instrumento esta roto y el experimento
   mentiria. Asi se cazaron tres reglas malas: una que ni el repo de referencia cumple, otra que
   contaba los `*_mother.py` como modulos de test, y otra que aplicaba a la capa de aplicacion una
   regla que solo rige en dominio.

## El `CLAUDE.md` global no se puede quitar, y esta declarado

`~/.claude/CLAUDE.md` se carga siempre, y dice cosas que solapan con lo que se mide ("NUNCA metas
comentarios", "Object Mothers", "type hints"). No es contaminacion entre variantes -entra igual en las
cuatro- pero **sube el suelo**: parte de lo que cumple la variante de control lo cumple por ahi y no
por meritos del modelo. Es ademas el escenario real, porque en produccion el implementador tambien lo
lleva.
