---
name: configurar
description: Deja un repo listo para el método Capitán — revisa herramientas, elige el tracker (uno externo conectado por MCP o el tablero local), ubica o manda a hacer el plan, detecta las pruebas, escribe `.claude/capitan.md`, crea `docs/capitan/` (estado, decisiones, aprendizajes, sesiones) y concilia plan contra tracker. Guía y pregunta en cada decisión. Úsala al adoptar el método en un repo, o si /capitan:trabajar se detuvo por falta de configuración.
---

# Capitán · configurar

Dejas el repo listo para `/capitan:trabajar`. **Guías y preguntas**; no supones.
Cada paso termina con algo verificado, no con «debería estar». Si un paso no
se puede completar, lo dices y dices cómo resolverlo.

Al final el repo tiene **`.claude/capitan.md`** (la config) y
**`docs/capitan/`** (la memoria del proyecto), el plan está ligado a su
tracker, y el dueño sabe exactamente qué falta.

`{CAPITAN}` es la carpeta del plugin: **dos niveles arriba del directorio base
de este skill**.

## Paso 0 — ¿Ya hay configuración?

- Si `.claude/capitan.md` existe: enseña un resumen y pregunta si se **revisa**
  (repasar cada paso contra lo que dice) o se **rehace**. No la sobrescribas
  sin respuesta.
- Si existe una config de la versión anterior del método
  (`.claude/work-tracker-plan.md`) o reportes en `docs/sesiones/`: ofrece
  **migrar** (§Migrar) en vez de empezar de cero.

## Paso 1 — Herramientas (verificadas, no supuestas)

| Qué | Cómo se verifica | Si falla |
|---|---|---|
| Skills `senior-engineer-es` | cargar `senior-engineer-es:orquestador` con la herramienta Skill | sin ellas no hay puertas: que instale el plugin y reinicie Claude Code |
| GitHub | `gh auth status` y que el repo tenga remoto | `gh auth login` (con `!` en el prompt) |
| Git limpio | `git status` | cambios ajenos se reportan, no se tocan |
| Python 3 | `python3 --version` | lo necesitan los hooks y el tablero |
| Medidor de uso (recomendado) | `~/.claude/usage-now.json` y `~/.claude/capitan-sesiones/<proyecto>.json` con `written_at` de menos de 10 min | ver §El medidor. Sin él, el colchón de uso no funciona y el tablero no mide sesiones; anótalo |
| Hooks del plugin | `claude plugin list` muestra `capitan` habilitado | si hay copias personales de los mismos hooks en `~/.claude/settings.json`, avísalo: correrían dos veces. **Pregunta antes de tocar su configuración** |

Reporta la tabla con ✅/❌. Con algún ❌ bloqueante, detente aquí.

### El medidor

Claude Code le pasa a la barra de estado el uso de la cuenta y el costo de la
conversación; `{CAPITAN}/scripts/medidor.py` lo lee y escribe dos archivos:

- `~/.claude/usage-now.json` — uso de **toda la cuenta** (5 h y semanal). Solo
  para el colchón de uso de `/capitan:trabajar`.
- `~/.claude/capitan-sesiones/<proyecto>.json` — consumo de **la conversación
  que trabaja en ese proyecto**: costo y duración exactos y el % semanal que
  subió desde que empezó (aproximado). Es lo único que mide el tablero; jamás
  muestra el consumo de toda la cuenta.

Si falta, ofrécelo y **pide permiso antes de tocar su configuración**:

1. Copia `{CAPITAN}/scripts/medidor.py` a `~/.claude/capitan/medidor.py`
   (ruta estable: la carpeta del plugin cambia con cada versión; el hook de
   inicio mantiene esa copia al día).
2. En `~/.claude/settings.json`, envuelve su barra de estado actual sin
   reemplazarla: `"command": "python ~/.claude/capitan/medidor.py -- <su
   comando actual>"` (sin barra previa: sin `--`). Usa el Python que respondió
   en el Paso 1.
3. Verifica: tras el siguiente refresco de la barra, los dos archivos existen
   con `written_at` reciente.

## Paso 2 — ¿Con qué tracker?

El tracker es la herramienta donde viven las tareas (Jira, Linear, GitHub
Projects, Trello…). Capitán lo usa por **MCP**, con las herramientas que ese
conector traiga; si no hay ninguno, usa el **tablero local**. No supongas
nombres de herramientas: se descubren y se confirman aquí.

**1. Busca los conectores MCP que ya tienes.** Revisa las herramientas
disponibles en esta sesión cuyo nombre empieza con `mcp__` (las diferidas
también cuentan: búscalas con ToolSearch) y, si hace falta, `claude mcp list`.
Quédate con los servidores que **parecen de seguimiento del trabajo del
proyecto**: los que traen herramientas para listar, crear y mover tareas,
issues, historias o tarjetas **de desarrollo** (no de ventas, clientes, CRM ni
seguimiento comercial, aunque también hablen de «tareas»). Decide por sus
herramientas, no por el nombre. Si un servidor **pide autenticarse** y no
muestra sus herramientas, solo cuenta si su nombre es claramente de un tracker
(jira, linear, github, trello, asana, clickup…): se ofrece marcado «sin
autenticar» y, si lo eligen, se le pide al dueño autenticarlo y se repite este
paso. Para ordenar los candidatos, el más probable es el que cubre más
operaciones de la tabla de abajo.

**2. Pregunta con `AskUserQuestion`:** *«¿En qué sistema se siguen las tareas
de este proyecto?»*. Opciones, en este orden:

- **Cada servidor candidato** (hasta tres, el más probable primero), con la
  descripción de qué herramientas de seguimiento le encontraste.
- **Tablero local** — siempre, como última opción.
- La opción **«Otro»** de la herramienta deja que el dueño **escriba** su
  sistema a mano.

Si no encontraste ningún candidato, dilo en la pregunta y ofrece igual el
tablero local y la opción de escribirlo.

**3. Según lo que conteste:**

- **Un servidor MCP** → arma la **tabla de equivalencias**: qué herramienta de
  ese servidor hace cada operación de `/capitan:trabajar`.

  | Operación | Qué debe hacer |
  |---|---|
  | Ver el tablero | Listar las actividades abiertas del proyecto |
  | Ver una actividad | Traer una con su descripción, criterios, subtareas y estado |
  | Crear | Crear una actividad con título, descripción y, si se puede, subtareas, dependencias y fechas |
  | Mover | Cambiarla de columna o de estado |
  | Subtareas | Marcar una subtarea (o casilla de la lista) como hecha |
  | Comentar | Dejar un comentario en la actividad |
  | Bloquear | Marcarla bloqueada con su motivo |
  | Nombre de rama | Pedirle al tracker el nombre de la rama, si lo da |

  En este paso **solo se llaman herramientas que leen**. Lee la descripción de
  cada herramienta antes de asignarla. Lo que el conector no permita, o que
  solo se pueda obtener **escribiendo**, queda como **«no tiene»** con su
  sustituto. Por ejemplo, si la única forma de obtener el nombre de rama es
  una herramienta que *crea* la rama, no la llames: el sustituto es el formato
  que diga su descripción o `<prefijo>-<clave>-<titulo-corto>`. Bloquear sin
  herramienta propia → comentario «BLOQUEADA: <motivo>».

  En este orden:
  1. **Busca el proyecto** (por el nombre del repo y el del README), sugiere
     los candidatos con el más probable primero y confirma con el dueño. Su
     **clave** se guarda en el Paso 5. Si no existe, crearlo es decisión del
     dueño. **Nunca pruebes con el proyecto de otro.**
  2. **Prueba la tabla leyendo** ese proyecto: ver el tablero y ver una
     actividad. Si el proyecto todavía no existe, prueba solo lo que no lo
     necesita (listar proyectos) y anota que el resto queda sin probar. Las
     escrituras **no se prueban**, salvo que la herramienta tenga un modo de
     simulación explícito (p. ej. un parámetro `simular` o `dry_run`). Las
     que no se probaron quedan marcadas «sin probar» en la tabla.
  3. **Anota las columnas:** las de Capitán son Backlog, Por hacer, En curso,
     Revisión de código, Pruebas funcionales, Por desplegar y Listo. Para cada
     una, escribe el valor exacto que acepta la herramienta de mover (el
     código, p. ej. `in_progress`) y cómo se ve en el tracker; si alguna no
     existe ahí, dilo.
  4. **Anota lo que el tracker hace solo**, porque cambia cómo trabaja
     `/capitan:trabajar`. Por ejemplo, que marcar subtareas mueve la tarjeta,
     que solo se puede mover a la columna contigua, o que el merge en GitHub
     la mueve. Sale de las descripciones de las herramientas.
  5. **Enséñale la tabla al dueño** antes de guardarla: las escrituras
     (mover, comentar, bloquear) se harán en su tracker.
- **Lo escribió a mano** → si ese sistema tiene un conector MCP que no está
  instalado, dile cuál es y cómo agregarlo (`claude mcp add …` o el conector de
  su organización), y que al tenerlo vuelva a correr este paso. Mientras tanto,
  o si no tiene conector, ofrécele el tablero local. **No inventes** una tabla
  para herramientas que no puedes ver.
- **Tablero local**, o dice que no tiene sistema de seguimiento → se crea con
  `python3 {CAPITAN}/scripts/tablero.py init "<nombre>"` en `docs/capitan/`:
  un JSON versionado en git y una página `tablero.html` que se abre en el
  navegador. Pregunta el prefijo de ramas (por omisión, el nombre del repo).

## Paso 3 — El plan

Busca el plan general (`TRACKER.md`, `PLAN.md`, `ROADMAP.md`, `docs/plan*`, lo
que `CLAUDE.md` o el README señalen). Cuenta como plan: **épicas con alcance y
orden**, no una lista suelta.

- **Hay plan** → confírmalo.
- **Hay algo, pero no es plan** → dilo y ofrece convertirlo con
  `senior-engineer-es:planeacion`.
- **No hay plan** → **no lo improvises aquí.** Idea difusa →
  `senior-engineer-es:aterrizar`; repo vacío → `senior-engineer-es:arranque`;
  idea clara → `senior-engineer-es:planeacion`. Con el plan aprobado, se vuelve
  a correr esta configuración. Termina aquí diciendo eso.

## Paso 4 — Lo demás que el plan necesita saber

Encuéntralo tú y **pide confirmación en bloque**:

| Campo | Dónde buscar |
|---|---|
| El dueño | quién decide y prueba; cómo se le avisa (`PushNotification`) |
| Registro de defectos | `docs/hallazgos.md`, `BUGS.md`… — si no hay, proponer uno con sus puertas |
| Reglas del repo | `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md` |
| Puerta visual y design system | docs de UI, paquete de design system |
| CI-equivalente local | `Makefile`, `package.json`, `pyproject.toml`, `.github/workflows/` — **los comandos que corre el CI**, no los que parecen |
| CI local (un comando) | El mismo CI-equivalente en UN comando (p. ej. `make ci`); si el repo no lo tiene, proponer crearlo. Va en la config como fila `| CI local | `<comando>` |`: lo usa el candado de push |
| Rama principal | `git symbolic-ref refs/remotes/origin/HEAD` |
| Ambiente de verificación | docs de deploy, workflows — o «no hay» y qué cuenta como Listo |
| Entorno local | `docker-compose*`, `Makefile` — y cómo se apaga |
| Canal de prueba permitido | el teléfono o correo del propio dueño, o «no hay envíos» |
| Alcance vigente | qué entra en la próxima release, qué está pausado |
| Reglas propias que no se negocian | `CLAUDE.md` |

Lo que no encuentres se pregunta; lo que el dueño no sepa queda como
`(pendiente)`, nunca inventado.

## Paso 5 — Escribir la configuración y la memoria

**Enséñalo antes de escribirlo.**

1. `.claude/capitan.md`: tabla de campos (incluido `Tracker: mcp <servidor>
   <clave>` o `Tracker: local · prefijo <x>`), CI-equivalente, alcance vigente
   y reglas propias. Con tracker MCP, además, una sección `## Tracker` con
   todo lo del Paso 2: la tabla de equivalencias (operación → herramienta, o
   «no tiene» y su sustituto, y cuáles quedaron «sin probar»), las columnas
   con su valor exacto y lo que el tracker hace solo. Su existencia es lo que **enciende los hooks** del plugin
   en este repo.
2. `docs/capitan/`:
   - `estado.md` con el formato de `/capitan:trabajar` (§La memoria del proyecto):
     `**Actualizado:**`, `## Dónde quedó`, `## Lo que sigue`, `## Esperando al
     dueño`, `## Cuidado`;
   - `decisiones.md` con las decisiones que ya existan (en `CLAUDE.md`, en la
     memoria, en lo que el dueño diga ahora), cada una con fecha y porqué;
   - `decisiones-historial.md` y `aprendizajes.md` vacíos con su encabezado;
   - `sesiones/` (con un `.gitkeep`);
   - con tablero local, `tablero.json` y `tablero.html` (Paso 2).
3. No commitees: eso lo decide el dueño.

## Paso 6 — Conciliar plan contra tracker

Trae las actividades y compáralas con el plan:

- actividades que el plan no menciona;
- pendientes del plan sin actividad;
- vencidas, o con un estado que el código contradice;
- de alcance pausado que siguen abiertas.

Propón los cambios (crear, bloquear con motivo, renombrar con su épica,
subtareas de prueba) y **no escribas nada en el tracker sin su OK**. Las fechas
las decide el dueño. Con tablero local recién creado, ofrece poblarlo desde el
plan (una épica por épica del plan, una actividad por pendiente).

## Migrar desde la versión anterior

Si el repo venía con `.claude/work-tracker-plan.md`:

1. Su contenido pasa a `.claude/capitan.md` (añadiendo la línea del tracker).
2. `docs/sesiones/*` se mueve con `git mv` a `docs/capitan/sesiones/`, y se
   actualizan las referencias (`grep -rn "docs/sesiones"`).
3. `estado.md` se escribe desde la última sesión y el tracker;
   `decisiones.md`, desde `CLAUDE.md`, la config y la memoria.
4. La config vieja se borra solo con el OK del dueño.

## Paso 7 — Cierre

```
Listo para /capitan:trabajar: sí / no
Tracker: mcp <servidor> <clave> — <nombre> (equivalencias en .claude/capitan.md)  |  local (docs/capitan/tablero.html)
Config: .claude/capitan.md (sin commit) · Memoria: docs/capitan/
Herramientas: <✅/❌ por línea>
Falta: <lo pendiente, con quién lo resuelve>
Siguiente paso: /capitan:trabajar
```
