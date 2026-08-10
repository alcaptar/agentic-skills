# Rama, pull request, merge

Esto es para el trabajo **sobre este repo**. Las ramas de una slice (`slice/NN-name`) las gestiona
`slice-runner`, que ya trabajaba asi.

## Nada se commitea directamente en `master`

Ni siquiera un typo: hay un hook que bloquea el push sobre la rama protegida, asi que descubrirlo tarde
cuesta rehacer el trabajo de sacarlo de `master`.

```bash
git switch -c <type>/<slug>          # refactor/contexto-del-orquestador, docs/flujo-rama-pr-merge
git push -u origin <type>/<slug>
gh pr create                          # cuerpo con la intencion: que estaba mal y deja de estarlo
gh pr merge <N> --merge --delete-branch
git switch master && git pull --ff-only
```

## Las reglas y su motivo

- **`--merge`, no `--squash` ni `--rebase`**: los dos ultimos reescriben los hashes y dejan tu `master`
  local divergido de `origin/master`, con lo que el `git pull --ff-only` de despues falla y hay que
  resolverlo a mano justo cuando crees que has terminado.
- **El cuerpo de la pull request cuenta el por que**, no el diff -misma vara que las pull requests que
  abre `slice-runner`: si borras el cambio, ¿que queda roto o imposible?-. Es el registro duradero de
  las decisiones, porque el codigo no lleva prosa.
- **`make check` en verde antes de abrir la pull request.** `.github/workflows/check.yml` lo corre
  tambien en **toda** pull request, sin filtro de `paths`, asi que la vara se mide donde se decide
  mergear; el local es para no descubrirlo en la integracion continua.
  `.github/workflows/smoke-fixture.yml` sigue aparte porque mide otro proyecto (`smoke/fixture/`, con su
  propio lockfile) y si esta filtrado por `paths`.
- **`git add` con rutas explicitas, nunca `-A` ni `.`** Lo que evita es arrastrar al commit lo que nadie
  declaro; para lo que **no** sirve es para stagear borrados, y la diferencia esta medida: `git add --`
  con la ruta de un fichero borrado del arbol **si** lo stagea, pero con la de uno que tampoco esta en el
  indice -tras un `git rm`- **aborta entero**, y con `-A` tambien. Abortado el `add`, el indice se queda
  con una ronda de retraso mientras la higiene, los controles y el bundle siguen saliendo verdes sobre el
  indice viejo. **Para borrar, saca el fichero del arbol y deja que el `add` lo recoja**; antes de dar un
  commit por hecho, `git diff --name-only` tiene que salir vacio.
- **La integracion continua se comprueba contra el SHA que vas a mergear**, no contra "la rama": un
  `success` heredado del commit anterior se lee igual en la interfaz.

## Dos slices en paralelo

Dos slices se conducen a la vez en **worktrees distintos**, cada una en su rama. Lo que decide si pueden
ir juntas no es el enunciado de la slice sino **los ficheros que acaba tocando**, y eso no se sabe hasta
implementarla.

- **No estimes el territorio por el nombre de la slice.** Se ha fallado dos veces haciendolo: una pareja
  elegida como "la mas disjunta" mirando su fichero protagonista compartio cuatro ficheros, y otra
  compartio siete, incluido uno que **las dos crearon**.
- **Hay ficheros iman que toca casi cualquier slice**: `infrastructure/cli.py` -ahi se monta el grafo de
  dependencias entero-, `src/slice_runner/tests/doubles.py`, `domain/exceptions.py`, `infrastructure/subcommand.py`, el
  `README.md` y `docs/conventions/`. Compartir uno de esos no impide lanzar, pero garantiza una fusion.
- **`application/actions/conduct_slice.py` es el cuello de botella del programa.** Dos slices que lo
  toquen no van juntas: ahi el conflicto deja de ser cosmetico.
- **Al lanzar en paralelo, declara el riesgo en vez de prometer que no lo hay**: "comparten `cli.py`, si
  hay conflicto sera pequeno" es honesto; "son disjuntas" ha resultado falso mas veces de las que ha
  resultado cierto.
- **La segunda en mergear fusiona `master` en su rama, y eso no obliga a volver a juzgar.** Una fusion
  no es codigo nuevo: se resuelve el conflicto, se pasan los controles y se sube. Volver a pagar al juez
  por una resolucion de conflicto es gastar la garantia donde no aporta.

## Antipatrones

- Un commit en `master`.
- Dar dos slices por disjuntas sin haber mirado que ficheros toca cada una.
- `--squash` o `--rebase` al mergear.
- Un cuerpo de pull request que resume el diff.
- `git add -A`, o dar por bueno un commit sin comprobar que el indice iguala el arbol.
- Leer la integracion continua sin comprobar a que SHA corresponde.
