# Panel de estado (TUI)

`slice-panel.py` pinta el estado del pipeline en vivo leyendo `<repo>/.slice-runner/runs.jsonl` (ledger) y `stream.log`. Sin dependencias (solo stdlib).

## Uso

```bash
# live, refresco cada 2s (Ctrl+C para salir)
python3 panel/slice-panel.py /ruta/al/repo

# un solo render (para captura o test)
python3 panel/slice-panel.py /ruta/al/repo --once

# otro intervalo
python3 panel/slice-panel.py /ruta/al/repo --interval 5
```

Muestra por slice: ESTADO (hecha/bloqueada/abortada-presupuesto), intentos, VERIFY, COSTE (al cierre), CI, PR; un resumen (hechas/bloqueadas, coste total y por slice mergeada); las entradas de `deploy-watch`; y el tail del stream.

## Qué muestra y qué no

- **Sí**: estado del pipeline en vivo y coste **al cierre de cada slice** (lo que hay en el ledger).
- **No**: consumo de tokens/$ en **tiempo real** durante un run. Una skill no puede auto-reportar su burn de tokens fiablemente en streaming.

Para el consumo en vivo de verdad (tokens/$/sesiones/agentes al momento), la fuente correcta es la **telemetria de Claude Code**:
- Exportar metricas por **OpenTelemetry** a tu stack (Prometheus/Grafana de monline).
- O la **Analytics API** de Claude Code.

Es lo que el modelo de madurez de Cherny lista como monitorizacion para los steps 1-3 (ver `../docs/maturity-map.md`). No hand-rollear contabilidad de tokens: enchufar OTel a Grafana.
