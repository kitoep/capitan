# Cambios

## 0.8.2 — Revisores en paralelo

Una actividad chica (un solo script) tardó 61 minutos medidos. Unos 27 se
fueron en agentes esperándose uno a otro. Las revisiones sí valieron: dieron
con 7 huecos reales. Lo que sobraba era la espera, no las revisiones.

**Qué cambia**

- **Los revisores que no dependen uno del otro corren a la vez.** Hay dos
  pares:
  - crítica y plan de pruebas (4 y 5): el 5 solo recibe los criterios, no el
    plan, así que no tiene que esperar;
  - probador y seguridad del diff (10 y 11), sobre el mismo commit.

  Los dos de un par se lanzan en el mismo mensaje y cualquiera puede cerrarse
  primero. El paso que sigue al par no empieza hasta cerrar los dos.
- **Si uno provoca un cambio, el otro lo revisa antes de cerrar su paso.**
  - Si la crítica cambia el alcance o los criterios, el cambio llega al plan
    de pruebas por el paso 9.
  - Si el probador pide un arreglo, seguridad revisa solo el diff de ese
    arreglo.
  - Si seguridad pide un arreglo, el probador corre sus casos sobre él.

  La evidencia del 10 y del 11 dice qué commit revisó cada uno.
- **Tablero local.** `tablero.py paso` lee los pares de la línea
  «**En paralelo:**» del SKILL y deja cerrar un paso con su par abierto. Fuera
  de los pares, el orden sigue estricto.
- **El candado del tracker ya no se apaga en silencio.** Si `## Tracker` no
  trae «Mover» y «Revisión de código» en la forma fija (las configs anteriores
  a la 0.8.1), el candado no sabe qué revisar. Ahora, al abrir la sesión,
  Capitán le avisa al dueño que está apagado y le pide correr el Paso 2 de
  `/capitan:configurar`.

## 0.8.1 — Candados donde el checklist no alcanzaba

La 0.8.0 hizo visible el ciclo, pero con un tracker por MCP el checklist
seguía siendo una regla de palabra. En una sesión real, con varias
actividades:
- ninguna tuvo hora ni uso medidos;
- el relevo se escribió solo al final;
- se declaró «CI verde» cuando parte de la suite nunca corrió por un error
  del shell.

**Qué cambia**

- **Candado al pasar a Revisión con tracker MCP** (`hook_tracker.py`). Corre
  cuando la herramienta «Mover» de `## Tracker` lleva una tarjeta a «Revisión
  de código», y bloquea si:
  - `docs/capitan/estado.md` no se reescribió después del merge de la
    actividad;
  - o su línea no trae la hora de inicio y de cierre (`HH:MM → HH:MM`) y el
    uso gastado.

  Si no puede leer la config o no encuentra el merge, avisa y no bloquea.
- **La medición entra al checklist.** La evidencia del paso 2 trae la hora y
  el uso de inicio; la del 16, los de cierre. La línea de cada actividad en
  `estado.md` los lleva.
- **El paso 12 exige prueba.** La evidencia es el conteo literal de la salida
  («412 passed, 0 failed») y el commit registrado por `ci_local.py`. Ahora
  `ci_local.py`:
  - guarda las últimas líneas de la salida en `.git/capitan/ci-registro.log`;
  - no da por verde una corrida con errores del propio shell (comando no
    encontrado, error de sintaxis), aunque salga 0.
- **Aviso de versión.** Al abrir, una vez al día, se compara la versión
  instalada con la del repo del plugin. Si hay una más nueva, avisa; si la
  copia local del marketplace divergió de su remoto y por eso no se actualiza
  sola, también lo dice.
- **`/capitan:configurar`** escribe `## Tracker` con forma fija (operación o
  columna en la primera celda, herramienta o valor entre backticks), porque el
  candado la lee.

**Proyectos ya configurados:** si su `## Tracker` no trae las filas «Mover» y
«Revisión de código» con la herramienta y el valor entre backticks, el candado
avisa y no bloquea. Corre el Paso 2 de `/capitan:configurar` para dejarlo en
forma.

## 0.8.0 — El checklist del ciclo

Cada actividad lleva en su tarjeta un checklist con los 16 pasos de su ciclo,
y Capitán lo marca conforme los cumple, con la evidencia de cada uno.

**Por qué:** las subtareas eran un desglose escrito a mano y distinto en cada
actividad. No se sabía si un paso como la crítica o la seguridad del diff se
había saltado o solo no se había anotado, y mientras la actividad corría nadie
veía en qué paso iba.

**Qué cambia**

- **El checklist del ciclo.** En el paso 2, la actividad recibe un checklist
  con los pasos de la tabla del SKILL («Ciclo 4 · Crítica + seguridad del
  plan»), separado de las subtareas propias del trabajo. Cada paso se cierra
  en el momento, de una de tres formas:
  - hecho, con su evidencia;
  - «no aplica», con su motivo;
  - omitido, con quién lo permitió y por qué.

  Nunca se marca un paso que no se hizo.
- **El checklist manda.** Un paso no empieza sin cerrar el anterior, y la
  columna «Puerta» dice cuándo puede marcarse. Antes de pasar a Revisión de
  código y antes de tomar otra actividad, Capitán revisa el checklist
  completo. Al retomar, sigue en el primer paso abierto. Ni la prisa ni el
  colchón de uso hacen excepciones.
- **Puertas en todos los pasos.** Los pasos que no tenían puerta (2, 5, 9 y
  16) ya tienen una, y la columna se llama «Puerta: cuándo se puede marcar».
- **Documentar es siempre lo último.** El final del ciclo cambia de orden:
  14 Hallazgos, 15 Relevo, 16 Documentar en el tracker. Así, marcar el último
  paso coincide con el paso a Revisión de código en los trackers que mueven la
  tarjeta solos, y Capitán nunca depende de ese movimiento.
- **La crítica alimenta las pruebas.** Lo que la crítica (paso 4) obliga a
  cambiar del plan entra a la lista de desvíos, y el paso 9 ajusta el plan de
  pruebas cuando la crítica cambió algo o hubo desvíos. El 5 no arranca hasta
  cerrar el 4.
- **Actividad chica.** Cierra la crítica como «no aplica: actividad chica».
  Las pruebas y la seguridad del diff nunca se saltan.
- **Tablero local.**
  - `tablero.py ciclo --listar` lee los pasos de la tabla del SKILL.
  - `tablero.py ciclo ACT-0xx` los agrega a una actividad.
  - `tablero.py paso ACT-0xx <n> --hecho | --no-aplica | --omitido "<texto>"`
    cierra un paso.
  - Candados: `paso` se niega con un paso anterior abierto, y `mover …
    revision` se niega con pasos abiertos.
  - La página pinta cada estado con su marca y su evidencia.
  - Pruebas nuevas en `tests/`.
- **`/capitan:configurar`** mapea también «agregar subtarea» y «renombrar
  subtarea». Anota en `### Lo que hace solo` si marcar subtareas mueve la
  tarjeta, a qué columna y si el proyecto tiene repositorio ligado; lo que el
  conector no diga, se lo pregunta al dueño.
- **Operaciones del tracker con nombres genéricos.** La tabla de «El tracker:
  una interfaz, dos motores» ya no trae nombres de herramientas de un conector
  concreto. Si la config no trae `## Tracker`, Capitán se detiene y pide
  correr el Paso 2 de `/capitan:configurar` en vez de probar nombres.

**Proyectos ya configurados:** su `## Tracker` ya trae los nombres reales de
sus herramientas y no cambia. Para llevar el checklist con un tracker MCP, hay
que volver a correr el Paso 2 de `/capitan:configurar`: así quedan mapeadas
«agregar subtarea» y «renombrar subtarea» y anotado lo que el tracker hace
solo. Las actividades que ya existían no se tocan; el checklist aplica a las
que se tomen desde ahora.
