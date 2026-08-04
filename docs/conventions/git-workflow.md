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
- **`git add` con rutas explicitas, nunca `-A` ni `.`** El fallo real que esto evita: un `git add` con
  un pathspec de un fichero ya borrado **aborta entero** y deja el indice con dos rondas de retraso,
  mientras la higiene, los controles y el bundle siguen saliendo verdes sobre el indice viejo. Antes de
  dar un commit por hecho, `git diff --name-only` tiene que salir vacio.
- **La integracion continua se comprueba contra el SHA que vas a mergear**, no contra "la rama": un
  `success` heredado del commit anterior se lee igual en la interfaz.

## Antipatrones

- Un commit en `master`.
- `--squash` o `--rebase` al mergear.
- Un cuerpo de pull request que resume el diff.
- `git add -A`, o dar por bueno un commit sin comprobar que el indice iguala el arbol.
- Leer la integracion continua sin comprobar a que SHA corresponde.
