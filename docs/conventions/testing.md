# Tests

## Como se mide todo

```bash
make check   # ruff check + ruff format + mypy strict + pytest; todo verde
```

Targets sueltos: `make test`, `make check-types`, `make check-style`, `make check-format`,
`make fix-linting`.

**Lanzalo siempre con `uv`.** El programa depende de terceros, así que un `python3 -m pytest` con el
interprete del sistema pasa o falla según lo que tengas instalado, y eso no es una vara.

Para acortar el ciclo:

```bash
make test PYTEST_ARGS="-m 'not integration' --nf -x --tb=short --disable-warnings --color=no --no-header"
```

## El marcador `integration`

Un solo marcador, con un criterio que no se discute en review: **el test lanza un subproceso de
verdad**. Es lo que cuesta tiempo y lo que depende de la maquina. Escribir en `tmp_path` no entra.

- Se aplica a la **clase** cuando el árbol nuevo la agrupa, y a la función donde el árbol todavía es
  function-based.
- `-m "not integration"` es el subconjunto rapido para el ciclo; **la suite entera sigue siendo la vara
  al cerrar una slice y en la integración continua**. El marcador acorta el bucle, no lo que se exige.

## Los dos árboles, y por que

| | Que cubre |
|---|---|
| Dentro del paquete | El programa. Co-localizado, espejando las capas. |
| `tests/` en la raíz | Los scripts de `skills/` y los contratos que no tienen paquete donde vivir: entre el programa y su documentación, entre dos vocabularios del propio dominio, y los invariantes que escanean el árbol. |

**Lo que comparten los dos árboles vive dentro del paquete**, no en la raíz, porque `src` entra en el
`pythonpath` y el directorio de `conftest` no: el árbol de dentro no puede consumir del de fuera y al
reves si.

**La rama base de un repo de test se fija explicitamente al inicializarlo**, porque la rama por omisión
es configuración de la maquina y un test que la asuma se cae en la de otra persona.

**Lo compartido por la suite de la raíz vive en su `conftest.py`.** No vuelvas a definir un helper en un
fichero de tests: con varias copias de firmas distintas, leer cualquier test obliga a subir a la cabecera.

## Forma de un test

- **Dentro de una clase**, agrupados por el comportamiento que fijan. Nunca funciones sueltas en el
  árbol nuevo.
- **Cero prosa**, igual que el código de producción: el nombre del test es la frase.
- El nombre dice **que se garantiza y por que**, no que metodo se llama:
  `test_a_finding_without_a_line_leaves_the_key_out_instead_of_emitting_null`.
- Los helpers de un test son `@staticmethod` de su clase de test, o viven en un módulo compartido, pero
  **nunca sueltos a nivel de módulo**.
- **Lo que comparten varias clases de test del mismo módulo vive en una clase de ese módulo que esas
  clases heredan**, no en una función suelta ni en un módulo compartido que solo se importa desde un
  sitio. Cubre tanto un helper como un `@pytest.fixture(autouse=True)` que solo protege a esas clases, y
  es lo que hace que la regla de arriba no tenga hueco: un helper de dos clases del mismo fichero no
  tiene por que salir del fichero.

  ```python
  # ejemplo/tests/test_{cosa}.py
  class {LoQueComparten}:
      @staticmethod
      def _{helper}() -> None: ...


  class Test{UnComportamiento}({LoQueComparten}): ...
  ```
- **En un fixture `autouse`, donde se declara es su alcance, y eso decide donde va.** Dentro de la clase
  cuando protege a esa clase; en la clase que se hereda cuando protege a un grupo; **a nivel de módulo
  cuando lo que protege es que ningún test del fichero toque algo de la maquina de quien lo corre**. Ese
  último caso es el único en el que un `def` a nivel de módulo es correcto en el árbol de test: bajarlo a
  una clase le recorta el alcance en silencio, y el mecanismo que lo sustituiria -que cada clase nueva se
  acuerde de heredar- falla sin avisar justo en la que se olvide.

## Object Mothers

**Los objetos de un test los construye un mother**, no el propio test:
`{paquete}/tests/mothers/{cosa}_mother.py`.

Un mother da defaults sensatos y deja que cada test nombre **solo lo que su caso cambia**, que es lo que
hace legible el assert. Sin ellos, el mismo objeto se copia en dos ficheros con valores distintos y
ninguno dice por que.

Los metodos son **escenarios con nombre**, no un `create(...)` con todo por defecto: así el test dice de
que caso va sin leer los argumentos.

## Payloads grabados

`{paquete}/tests/payloads/` son respuestas de llamadas **reales** guardadas tal como llegaron. Es lo que hace que
el test de frontera mida la carga literal en vez de un modelo nuestro de ella, y de ahi salen datos que
nadie escribiria a mano.

**Cuando cambia el contrato del contenido, se reescribe a mano el campo afectado -en todas las copias que
el otro lado escriba- en vez de regrabar.** Es divergencia declarada de "grabados", y el motivo es que no
hay nada que grabar: ninguna llamada vieja puede traer el campo con la forma nueva, y regrabar arrastraria
de paso el resto de la respuesta, que es justo lo que otros tests fijan. Lo que **no** autoriza es tocar
la respuesta: si lo que cambia es una clave del otro lado, hay que regrabar, porque ahi la forma real es
lo único que se esta midiendo.

## Dobles

- **`create_autospec(X, spec_set=True, instance=True)`** para puertos sin estado.
- **Dobles con estado a mano** cuando el test necesita preguntar por lo que se le paso: un `Mock` no
  sirve para eso.
- **Un doble dobla lo que su nombre dice y nada más.** Si un solo puerto sirve a dos consumidores, el
  doble intercepta a uno y deja pasar al otro de verdad. Uno que respondiera a cualquier entrada con la
  respuesta del otro haría que el test pasara o fallara por el motivo equivocado.
- **El doble de una conversación entera contesta por lo que se le pide, no por orden.** Devolver salidas
  en el orden en que se pasaron sirve para **un** adaptador, donde el orden es parte de lo que se mide;
  en un flujo que pasa por varias herramientas el orden es detalle de implementación, así que el doble
  responde según la petición y **lanza cuando nadie escribió respuesta** para ella. Eso es lo que
  convierte "no repite el trabajo ya hecho" en algo comprobable: si lo repitiera, el doble no tendría que
  contestar y el test se cae con la petición delante, en vez de pasar por casualidad.
- **El adaptador de verdad también se pide a un sitio**, cuando su configuración entra por constructor y
  **no tiene default** (ver `docs/conventions/infrastructure.md`): sin un sitio comun, cada llamada de
  test elegiria su propio presupuesto, que es la política repartida que el default existe para impedir.
- **Nada de mockear value objects**: se usan instancias reales.
- El arrange **no se construye con la pieza bajo prueba**: el estado que un adaptador va a leer se monta
  con la herramienta de verdad, no con el propio adaptador.

## Que se testea y que no

- **Outside-in, y en este orden**: primero los tests de la **capa de aplicación** con los puertos
  doblados, luego los de **infraestructura**. Lo de dentro del dominio se cubre **por ese camino**, no
  con tests propios.
- **No hay tests unitarios de dominio**, ni siquiera cuando el dominio tiene comportamiento: se comprueba
  por el camino real por el que ese comportamiento llega. La única excepción es un value object con
  validación propia que no se pueda alcanzar de otra forma. Un test que solo comprueba que un dataclass
  guarda lo que le pasas mide el lenguaje, no el código.
- **Aplicación**: puertos mockeados por constructor, y el assert sobre el **efecto observable** (que
  recibio el puerto, que devolvio el caso de uso), no sobre la llamada.
- **Frontera**: el assert es la **carga literal** que se envia o se recibe, no un modelo de ella
  reimplementado en el test. Comparar contra un modelo propio del formato es reescribir el mapeo y
  aprobarlo por construcción.
- **Antes de añadir un test, comprobar si el comportamiento ya está cubierto.** Solo entra si aporta
  una dimensión distinta.

## Los contratos que viven fuera del paquete

`make check` **también cubre los `.md`**, y esos contratos se reparten por lo que miden, no por comodidad,
para que lo que dependa de un consumidor condenado se retire sin tocar los demas. Tres reglas los
gobiernan:

- **Un contrato extrae el vocabulario de los dos lados y los compara.** Así reescribir las dos copias a
  la vez pasa y tocar solo una falla. Si editas un documento y su contrato se pone rojo, es que has movido
  una mitad: mueve la otra.
- **Un invariante que escanea el árbol vale más que dos copias de la misma prosa.** Una regla escrita solo
  para una parte del árbol no puede fallar en la otra: cuando el tope por llamada estaba escrito solo para
  los scripts, quien juzgaba el programa no tenía con que fallarlo. El alcance es "todo", así que ni el
  árbol de test ni las formas menos usadas de hacer algo quedan fuera -una vara que solo mira donde ya se
  cumple no mide nada-.
- **Una lista de excepciones nombra lo que NO cuenta, no lo que si.** Un allow-list de los casos conocidos
  no puede fallar ante uno nuevo añadido sin tratamiento; invertir el criterio -nombrar lo que se sabe que
  es inocuo, y tratar como sospechoso todo lo que el escaneo no reconoce- si. El coste es mantener esa
  lista, y lo fija un meta-test sobre una fuente sintetica: algo que el escaneo nunca ha visto cuenta como
  sin tratar por defecto, en vez de pasar en silencio.

Y hay un contrato de rutas: **toda ruta de este repo citada en un `.md` existe**. No se enlaza con
markdown, se cita en backticks, así que lo que se valida es el token, y solo entran los que empiezan por
un directorio de primer nivel. Por eso una ruta de ejemplo se escribe como **molde**, con nombres
plantilla que no apuntan a nada del árbol (ver `docs/conventions/como-se-escribe.md`).

## Antipatrones

- Un test como función suelta en el árbol nuevo.
- Un comentario o un docstring en un test.
- Un test que lanza un subproceso y no lleva `@pytest.mark.integration`.
- Construir un objeto de dominio a mano en el test cuando hay mother, o duplicar en el test las
  constantes del mother.
- Un helper de test suelto a nivel de módulo, o repetido en dos ficheros.
- Arrange construido con la pieza bajo prueba.
- Assert contra un modelo del formato reimplementado en el test, en vez de contra la carga literal.
- Un test de dominio. Lo que hay dentro se cubre desde aplicación y desde la frontera.
