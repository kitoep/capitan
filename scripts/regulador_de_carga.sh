#!/usr/bin/env bash
# Regulador de carga del método Capitán.
#
# Mientras corren varios trabajos pesados a la vez (cada uno con su proyecto de
# docker compose, `-p <prefijo><n>`), vigila la carga de 1 minuto:
#   - si pasa del número de núcleos, PAUSA los contenedores del proyecto más
#     nuevo (`docker pause`): sus pruebas se congelan, no se pierden;
#   - cuando baja de ~60 % de los núcleos, los REANUDA (`docker unpause`).
# Cada pausa y reanudación se imprime con la hora, para el reporte.
#
# Uso: regulador_de_carga.sh <prefijo-de-proyectos> [minutos]
#   p. ej. regulador_de_carga.sh wt- 120
# Correrlo en segundo plano y detenerlo al terminar la sesión.
set -u
prefijo="${1:?prefijo de los proyectos de compose, p. ej. wt-}"
minutos="${2:-120}"
nucleos=$( (nproc 2>/dev/null || sysctl -n hw.ncpu) | head -1 )
reanudar=$(( nucleos * 6 / 10 ))
vueltas=$(( minutos * 6 ))

carga() {
  if [ -r /proc/loadavg ]; then cut -d' ' -f1 /proc/loadavg
  else sysctl -n vm.loadavg | awk '{print $2}'; fi
}

for _ in $(seq 1 "$vueltas"); do
  l=$(carga); l=${l%.*}
  pausados=$(docker ps --filter status=paused --format '{{.Names}}' | grep "^${prefijo}" || true)
  if [ "$l" -ge "$nucleos" ] && [ -z "$pausados" ]; then
    proyecto=$(docker ps --format '{{.Names}}' | grep "^${prefijo}" \
      | sed -E 's/-(postgres|redis|pruebas|db|cache)[-0-9a-z]*$//' | sort -u | tail -1)
    if [ -n "$proyecto" ]; then
      docker ps --format '{{.Names}}' | grep "^${proyecto}-" | xargs -r docker pause >/dev/null \
        && echo "$(date +%H:%M) carga $l ≥ $nucleos núcleos → pauso $proyecto"
    fi
  elif [ "$l" -lt "$reanudar" ] && [ -n "$pausados" ]; then
    echo "$pausados" | xargs docker unpause >/dev/null \
      && echo "$(date +%H:%M) carga $l < $reanudar → reanudo $(echo "$pausados" | tr '\n' ' ')"
  fi
  sleep 10
done
