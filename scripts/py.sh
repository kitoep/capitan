#!/bin/sh
# Lanza un script del plugin con el Python 3 que haya en la máquina.
# En Windows, `python3` suele ser el atajo de la Microsoft Store (no corre
# Python y sale con 49); ahí el real responde a `py -3` o `python`.
# Se prueba que cada candidato DE VERDAD ejecute Python 3 antes de usarlo.
export PYTHONIOENCODING=utf-8 PYTHONUTF8=1
dir=${0%/*}
script="$dir/$1"; shift
for cand in "python3" "py -3" "python"; do
  if $cand -c 'import sys; sys.exit(0 if sys.version_info[0] == 3 else 1)' >/dev/null 2>&1; then
    exec $cand "$script" "$@"
  fi
done
echo "capitan: no encontré Python 3 (probé python3, py -3 y python); el hook no corrió." >&2
exit 0
