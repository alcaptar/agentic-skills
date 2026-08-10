# Como se escribe una convencion

Esta es la vara de las varas. Rige para todo `.md` de `docs/conventions/` **y para cualquier otro que un
contrato mida o que un agente lea como vara** -hoy, el `README.md`-. Lo que obliga a mantener un
documento no es la carpeta en la que vive: es que algo se rompa cuando deje de ser verdad.

Quedan fuera los `.md` del flujo viejo (`skills/`), que son codigo que no es referencia (ver
`CLAUDE.md`): estan congelados a proposito y reescribirlos no compra nada.

Una convencion la leen dos agentes que no pueden preguntar -el implementador antes de escribir, el
juez antes de bloquear- y una persona que llega nueva. Los tres necesitan lo mismo: **la regla con la
que se mide el codigo**, en una forma que siga siendo verdad dentro de veinte slices.

## Un dato del codigo escrito en prosa: las tres formas

No todas cuestan lo mismo, y la diferencia no es el estilo sino **quien avisa cuando el codigo cambia**:

| | quien avisa | coste |
|---|---|---|
| **Regla atemporal** | nadie tiene que avisar: sigue siendo verdad | ninguno |
| **Copia medida por un contrato** | `make check`, al instante | se arregla en la misma vuelta |
| **Censo sin contrato** | el juez, dos pasos despues | una vuelta entera al implementador |

La segunda **es aceptable**: la tabla de codigos de salida del `README.md` repite el `IntEnum` del
programa y un test compara los dos conjuntos, asi que anadir un miembro sin documentarlo pone `make
check` en rojo antes de que nadie juzgue nada. Lo que la hace aceptable no es estar en una tabla: es que
el contrato **compara vocabulario y no prosa**, de modo que reescribir el texto no rompe nada mientras
los dos lados digan lo mismo.

Lo que sigue prohibe la tercera. Si un dato del codigo tiene que estar escrito, **se le pone contrato o
no se escribe**.

## Reglas criticas

- **Una convencion no cuenta cuantos hay.** Ni "los tres reintentos", ni "las nueve etiquetas", ni
  "el unico codigo que emiten los dos subcomandos". Un conteo es una foto del codigo, y la proxima
  slice que anada un miembro la convierte en mentira.
- **Ni enumera en lista cerrada.** "Lo que acumula por invocacion son estos tres" caduca igual que un
  numero, y una enumeracion **al lado de una tabla que si tiene contrato** caduca igual que si estuviera
  sola: lo que protege es el contrato, no la vecindad. Si la lista importa, vive en el codigo, que es
  donde se puede comprobar.
- **Ni narra la historia.** Que algo vivio antes en otro sitio, que se descarto una alternativa o que
  un fallo costo un run es el **por que**, y su casa es `docs/design-notes.md`. La convencion dice la
  regla; el registro duradero dice como se llego a ella.
- **Ni senala ficheros reales como ancla normativa.** "Es el caso de este adaptador concreto" obliga
  a mantener la prosa cada vez que ese fichero se mueve. Si la regla necesita ancla, se da como
  **molde**. Lo que si se nombra es **la herramienta que mide** -el test que compara las dos copias de
  un contrato, el linter que caza la firma larga-: eso no es un ejemplo de como se hace, es donde falla
  si no se hace.
- **Cada fichero cubre una capa, y un tema que se quiera cargar solo se saca a fichero propio.** No por
  tamano: un documento largo y enfocado se cumple igual que uno corto -esta medido, y el como esta en
  `docs/design-notes.md`-. Es por **poder cargar solo lo que toca**: mientras un tema viva dentro de
  otro, quien solo necesita ese tema se lleva los dos.

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
- **El molde no mejora el acierto: ahorra el trabajo de averiguarlo.** Sin el se acierta igual, pero se
  gastan turnos yendo a mirar el arbol para confirmar. Por eso el molde se pone donde el caso es
  frecuente, no en todas las reglas. La medicion, en `docs/design-notes.md`.

## Antipatrones

- Un numero escrito en prosa que cuente miembros, ramas, contadores o ficheros.
- Una lista cerrada de lo que hay hoy, presentada como si fuese la regla.
- Un parrafo que cuenta lo que se intento antes. **Va a `docs/design-notes.md`.**
- Una ruta de este repo usada como ejemplo de "asi se hace" en vez de un molde plantilla.
- Una regla que obliga al implementador a editar `docs/conventions/` para dejarla veraz: si mantener
  la convencion es parte de cada slice, la convencion ha dejado de ser vara y es un fichero de codigo
  mas. Quien escribe no puede ser quien mueve la vara con la que se le mide.
