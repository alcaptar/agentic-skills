# Como se escribe una convencion

Esta es la vara de las varas: rige para todo `.md` de `docs/conventions/`.

Una convencion la leen dos agentes que no pueden preguntar -el implementador antes de escribir, el
juez antes de bloquear- y una persona que llega nueva. Los tres necesitan lo mismo: **la regla con la
que se mide el codigo**, en una forma que siga siendo verdad dentro de veinte slices.

## Reglas criticas

- **Una convencion no cuenta cuantos hay.** Ni "los tres reintentos", ni "las nueve etiquetas", ni
  "el unico codigo que emiten los dos subcomandos". Un conteo es una foto del codigo, y la proxima
  slice que anada un miembro la convierte en mentira.
- **Ni enumera en lista cerrada.** "Lo que acumula por invocacion son estos tres" caduca igual que un
  numero. Si la lista importa, vive en el codigo, que es donde se puede comprobar.
- **Ni narra la historia.** Que algo vivio antes en otro sitio, que se descarto una alternativa o que
  un fallo costo un run es el **por que**, y su casa es `docs/design-notes.md`. La convencion dice la
  regla; el registro duradero dice como se llego a ella.
- **Ni senala ficheros reales como ancla normativa.** "Es el caso de este adaptador concreto" obliga
  a mantener la prosa cada vez que ese fichero se mueve. Si la regla necesita ancla, se da como
  **molde**.

## El molde, cuando hace falta

Un molde es codigo de ejemplo con rutas y nombres **plantilla**, que no apuntan a nada del arbol:

```python
# ejemplo/infrastructure/{cosa}.py  -- puerto y adaptador juntos
class {Cosa}(ABC):
    @abstractmethod
    def hacer(self) -> None: ...


class Local{Cosa}({Cosa}):
    def hacer(self) -> None: ...
```

- **La ruta del molde no empieza por una carpeta de este repo.** Si empezara por una, el contrato de
  rutas citadas (`tests/test_skill_contracts.py`) la leeria como una afirmacion sobre el arbol y
  fallaria, con razon: en backticks, una ruta de este repo es una promesa de que existe.
- **El molde no mejora el acierto: ahorra el trabajo de averiguarlo.** Medido en un playground con la
  regla del puerto que solo consume la infraestructura: con molde y sin molde se acierta igual, pero
  sin molde se gastan tres veces mas turnos yendo a mirar el arbol para confirmar. Por eso el molde se
  pone donde el caso es frecuente, no en todas las reglas.

## Antipatrones

- Un numero escrito en prosa que cuente miembros, ramas, contadores o ficheros.
- Una lista cerrada de lo que hay hoy, presentada como si fuese la regla.
- Un parrafo que cuenta lo que se intento antes. **Va a `docs/design-notes.md`.**
- Una ruta de este repo usada como ejemplo de "asi se hace" en vez de un molde plantilla.
- Una regla que obliga al implementador a editar `docs/conventions/` para dejarla veraz: si mantener
  la convencion es parte de cada slice, la convencion ha dejado de ser vara y es un fichero de codigo
  mas. Quien escribe no puede ser quien mueve la vara con la que se le mide.
