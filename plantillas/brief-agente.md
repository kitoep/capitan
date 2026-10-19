# Brief base para CADA agente de una actividad

Copia este bloque TAL CUAL al inicio del encargo y debajo pon lo propio de la
tarea. No se resume ni se omite: es lo que evita los errores del 2026-10-02.

---

**Reglas que no se negocian en este encargo:**

1. **Git prohibido.** No corras ningún comando git que cambie estado: `stash`,
   `checkout`, `switch`, `reset`, `restore`, `merge`, `rebase`, `commit`,
   `push`, `branch`, `clean`, `worktree`, `cherry-pick`. Solo lectura (`git
   log`, `git show`, `git diff`, `git status`). Para ver una prueba fallar
   contra el código anterior: copia de respaldo del archivo en /tmp →
   `git show <ref>:<ruta> > <ruta>` → corre → restaura con `cp` desde tu copia.
   Al terminar, `git diff --stat` solo debe mostrar tus archivos. Si algo te
   exige un comando prohibido, detente y repórtalo.
2. **Si escribes pruebas de frontend, corre también el build** (`npm run
   build`, incluye `vue-tsc`), no solo la suite. Unas pruebas que no compilan
   rompen el build de todos.
3. **No dejes nada corriendo en segundo plano** al reportar. Si lanzaste algo,
   espéralo o detenlo, y dilo.
4. **No afirmes lo que no comprobaste.** Cada cosa que digas que hace un
   commit, un doc o un paso de CI tiene que haberse visto pasar o fallar aquí.
   Si no lo corriste, escríbelo como «no verificado».
5. **PROHIBIDO cambiar un resultado esperado para que una prueba pase.** Si
   falla con el cambio, es un defecto y se reporta.
6. **No apagues contenedores** que no levantaste tú, y no toques ambientes
   compartidos (dev, producción, el tracker, GitHub) salvo que el encargo lo
   pida expresamente.

**Si eres el desarrollador**, esto es lo que la revisión de seguridad suele
encontrar; ciérralo de entrada:
- filas o registros ajenos que el código pisa o «adopta» por tener el mismo
  nombre;
- datos personales en mensajes de error, salidas de comandos o logs;
- valores que manda quien llama y terminan en un atributo HTML, una URL o una
  consulta sin validar;
- guardas que fallan ABIERTAS con un valor vacío o ausente;
- instalaciones o pasos de CI sin endurecer (sin hashes, sin pin, con `:` sin
  comillas en YAML).

**Reporte (español):** lo que hiciste, la salida ROJA antes y la VERDE después
de cada prueba (pegadas), archivos tocados, desvíos y su porqué, lo que NO se
pudo verificar, y `git status` al final.
