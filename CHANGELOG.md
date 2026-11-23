# Cambios

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
