# Panel de estado (TUI)

`slice-panel.py` pinta el estado del pipeline en vivo leyendo tres fuentes de `<repo>/.slice-runner/` mas la spec:

- `state.json` — estado vivo (`spec_path`, `slice_actual`, `fase`), para mostrar la slice en curso y si esta **esperando una decision tuya**.
- `runs.jsonl` — ledger (una linea por slice/deploy al cerrar).
- `stream.log` — stream en vivo.
- la **spec** (via `spec_path` del `state.json`, o `--spec`) — para listar **todas** las slices, incluidas las **pendientes** que aun no estan en el ledger.

Sin dependencias (solo stdlib).

## Uso

```bash
# live, refresco cada 2s (Ctrl+C para salir)
python3 panel/slice-panel.py /ruta/al/repo

# un solo render (para captura o test)
python3 panel/slice-panel.py /ruta/al/repo --once

# otro intervalo
python3 panel/slice-panel.py /ruta/al/repo --interval 5

# forzar la spec (si aun no hay state.json)
python3 panel/slice-panel.py /ruta/al/repo --spec spec.md
```

Muestra **todas** las slices de la spec en cuatro columnas: `SLICE` (id), `NAME` (nombre kebab-case), `ESTADO` (`pendiente`/`en curso`/`esperando-merge`/`hecha`/`bloqueada`/`abortada-presupuesto`) y `PR`. Encima de la tabla, un banner destaca si el pipeline esta **esperandote a ti** (p. ej. el merge) frente a parado. El resumen cuenta hechas, esperando merge, bloqueadas, pendientes y el total. Abajo, el tail del stream con fecha completa.

## Qué muestra y qué no

- **Sí**: el **estado** del pipeline en vivo (por donde va cada slice y si te esta esperando).
- **No**: consumo de tokens/$ (ni en tiempo real ni al cierre). Una skill no puede auto-reportar su burn de tokens de forma fiable, asi que el panel no lo intenta.

Para el consumo de tokens/$/sesiones/agentes, la fuente correcta es la **telemetria de Claude Code**:
- Exportar metricas por **OpenTelemetry** a tu stack (Prometheus/Grafana de monline).
- O la **Analytics API** de Claude Code.

Es lo que el modelo de madurez de Cherny lista como monitorizacion para los steps 1-3 (ver `../docs/maturity-map.md`). No hand-rollear contabilidad de tokens: enchufar OTel a Grafana.
