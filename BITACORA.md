# Sábado Ago 2 — HITO: motor io_uring funcionando + métricas reales + el dato que motiva F3

Sesión larga (mucha depuración de infraestructura, toda resuelta). Objetivos del día cumplidos: motor io_uring, métricas reales, escala a 1 GB.

## 1. Motor io_uring (`one_to_one.cpp`)

- **Submit-and-wait de a uno** primero (corrección), luego **batching por `-q`**: encola hasta `queue_depth` SQEs, un solo `io_uring_submit_and_wait`, y asocia cada completion con su chunk vía `user_data` (`io_uring_sqe_set_data64`/`io_uring_cqe_get_data64`) porque **las completions llegan fuera de orden**. Este mecanismo user_data es justo lo que se emula en F3. Checksum plegado en orden de offset (independiente del orden de completion). Completions cortas/`EINTR` se rematan con el helper `uring_rw_all` de a uno ya probado. Sin fixed buffers, sin SQPOLL.
- **Ring reuse (`struct UringCtx`)**: el ring y los buffers se asignan una vez y se reutilizan entre archivos, no por archivo. `main` despacha por motor con `std::function` + un `UringCtx` opcional. Esto fue crítico para un benchmark justo (ver punto 3).
- **Equivalencia demostrada**: los checksums del motor uring son idénticos a los POSIX byte a byte; escribir con uno y leer con el otro verifica.

## 2. Tests (`engine_test.cpp`, renombrado desde `posix_test.cpp`)

La misma batería de 8 propiedades corre contra AMBOS motores vía punteros `WRITE`/`READ` → prueba objetiva de equivalencia. Añadido **T11 (equivalencia cruzada)**: escribir con un motor, leer con el otro, checksums iguales. Verificado con mutación que la batería del motor uring también tiene dientes (inyecté verificador-siempre-acepta → aborta).

## 3. Métricas e instrumentación

- Cronómetro `CLOCK_MONOTONIC` alrededor del bucle de I/O (el `printf` de checksums queda FUERA de la región medida). Línea `clave=valor` cosechable: `engine=... role=... bytes=... secs=... MBps=...`.
- **Hallazgo de rendimiento (matizado, va a la tesis):**
  - 100×1MB en tmpfs: io_uring ≈ POSIX (completions inline; el kernel completa síncrono, no hay asincronía que ocultar — como anticipa el plan §2).
  - 1×1GB: io_uring > POSIX (338 vs 300 MB/s) — con volumen, el batching amortiza el overhead del ring.
  - Antes del ring reuse, `-q` altos se penalizaban (artefacto de asignación por archivo). Tras el fix, `q=32` pasó 232→314 MB/s. El reuse NO es gaming: es metodología correcta.
- **1 GB verificado correcto en ambos motores.** Nota: `/tmp` es tmpfs (RAM) → para números de tesis usar disco real (`/var/tmp`, ext4).

## 4. `bench.sh` — las 4 configuraciones (FS/CAPIO × posix/uring)

N reps, mediana, tabla + CSV. Corre productor y consumidor bajo el server CAPIO reutilizando el patrón de `run_capio_test.sh`.

## 5. EL DATO CENTRAL: CAPIO-uring falla con EBADF

`CAPIO-uring` NO cuelga — **falla con `io_uring write failed: Bad file descriptor`**. Es la tesis en una línea: CAPIO intercepta `open()` y devuelve un **fd falso** que solo la librería POSIX entiende, pero io_uring lo pasa **directo al kernel** vía el ring → el kernel no conoce ese fd → `EBADF`. Demostración perfecta de por qué la intercepción a nivel syscall no basta y por qué CAPIO debe **poseer el ring** (F3). Capturado como evidencia en la tabla y el CSV (`bench_results.csv`).

## 6. Bugs de infraestructura resueltos (lecciones)

- **shm de CAPIO se nombra por el WORKFLOW, no `CAPIO*`**: son `/dev/shm/<workflow>*` y `sem.<workflow>*`. Un `rm /dev/shm/CAPIO*` no los borraba → servidores nuevos chocaban con canaries corruptos y abortaban. `bench.sh` ahora limpia con el patrón correcto, acotado al workflow (nunca un `rm /dev/shm/*` ciego).
- **`pkill -f one_to_one` es peligroso**: `-f` matchea la línea de comando del propio shell (que contiene la ruta del script) → se auto-mataba el comando. Usar `pkill -x one_to_one` (nombre exacto de proceso).
- **CAPIO-uring cuelga a veces** (consumer espera datos que nunca llegan) → `bench.sh` envuelve cada app en `timeout 30`.
- **Bug de calidad en `bench.sh`**: el stderr de las apps se colaba en medio de la tabla, y el mensaje de error se descartaba. Corregido: cada app va a su log, y el `reason` (p. ej. `Bad file descriptor`) se captura como evidencia en tabla + CSV. Además el `reason` ya no aparece en falso en filas exitosas.

## 7. Estado de F1

| Pieza | Estado |
|---|---|
| Motor POSIX + io_uring (batching, ring reuse) | ✅ |
| Batería T1–T11 + equivalencia cruzada | ✅ con dientes |
| Métricas + `bench.sh` 4 configs | ✅ |
| Escala 1 GB | ✅ |
| Dato EBADF (motivación de F3) | ✅ capturado |
| `README.md` del ejemplo | ⬜ vacío |
| Corrida de benchmark "de verdad" (disco real, ≥5 reps, más archivos) | ⬜ pendiente |

Pendiente inmediato: commits (motor+tests, y benchmark), luego README y la corrida real para la presentación.

# Jueves Jul 31 — HITO: motor POSIX de F1 concluido + benchmark corriendo bajo CAPIO

Estrategia del día: definir *primero* la batería de tests que fija el criterio objetivo de "F1-POSIX concluido", y luego cerrar el motor contra ella.

## 1. Motor POSIX completo (`one_to_one.cpp`)

- **Paso 2 — `posix_write_file`**: abre `O_CREAT|O_WRONLY|O_TRUNC`, buffer `std::vector` de un chunk reutilizado, bucle `fill_pattern → fnv1a → write_all`, último chunk parcial vía `std::min`, `die()` con ruta+`strerror` en error.
- **Paso 3 — `posix_read_file`** (el verificador): lee, regenera el patrón esperado con `fill_pattern` y compara checksums FNV (honra FNV como mecanismo único, sin `memcmp` redundante). Fallo de apertura → `die()` (pipeline roto); contenido/longitud mal → `false` (fallo de verificación). Verifica **independientemente** del producer — no se pasa dato entre procesos, gracias al patrón posición-estable.
- **Paso 4 — `main` cableado**: despacha por rol. Producer escribe N archivos e imprime `ruta checksum` (fingerprint reportable para F6). Consumer imprime `verified N/N files OK` y **sale ≠0 si algún archivo falla** — el exit code ES el resultado del benchmark (lo consume CI y el script de integración). Motor sin ramificar aún (solo existe POSIX; la rama io_uring entra con su motor).

## 2. Batería de tests = criterio de "F1-POSIX concluido"

- **`posix_test.cpp`** (8 checks, C++ con `assert`, sin framework, `#include` del `.cpp` por ser funciones `static`): chunk parcial + tamaño exacto en disco, multi-archivo (T1), **detección** de corrupción de 1 byte (T2), de intercambio de archivos (T3) y de truncamiento (T4), y casos de tamaño T5–T7. T7 con ponytail: 8 MB no prueba overflow de 64 bits (>4 GB), solo escala.
- **Verificado con mutación (tienen dientes):** inyecté (a) verificador que siempre acepta → T2 aborta; (b) producer que ignora el chunk parcial → check de tamaño aborta. Un test que solo pasa en verde no prueba nada.
- **`run_capio_test.sh`** — T8: pipeline bajo CAPIO, consumer reporta `verified 4/4` y sale 0. T9: intercepción real — leer sin `LD_PRELOAD` falla porque los `.dat` no existen en el FS real. Ambos en verde.

## 3. Hallazgo: CAPIO-CL acepta comodines

Verificado empíricamente (CAPIO-CL es dependencia externa, no legible en el repo): el server arranca y registra `file_*.dat` como una entrada de patrón. Por eso `capio_config.json` usa `file_*.dat` → funciona con cualquier `-n` sin hardcodear nombres. Regla de streaming `on_close` + `no_update` (CoC/FnU del paper).

## 4. Estado de F1

| Pieza | Estado |
|---|---|
| CLI, checksum FNV, patrón, helpers I/O | ✅ |
| Motor POSIX (write+read+main) | ✅ concluido |
| Batería T1–T9 (unit + integración CAPIO) | ✅ verde y con dientes |
| Motor **io_uring** (núcleo de la tesis) | ⬜ siguiente |
| `README.md` del ejemplo | ⬜ vacío |

Commits preparados (2): motor+batería, y config+integración. `test.json` (del asesor) queda fuera del PR. Pendiente: push (con chequeo anti-trailer), motor io_uring, README.

# Jueves Jul 23 — HITO: CAPIO ejecutándose end-to-end (smoke test) + limpieza de código

## 1. Smoke test de CAPIO — **objetivo cumplido**

Indicación del asesor: antes de montar el benchmark completo, ejecutar algo mínimo sobre CAPIO. Correcto — aísla fallos de CAPIO/entorno de fallos de nuestro código.

Programas triviales en `capio_smoke/` (fuera del fork de CAPIO, para no ensuciar la rama del PR): `writer.c` escribe `"hello capio\n"` en `test.txt`, `reader.c` lo lee e imprime. ~30 líneas cada uno, sin flags ni checksums.

Comandos exactos (reproducibles):

```
rm -rf /dev/shm/CAPIO*
mkdir -p /tmp/capio_mnt

# servidor (terminal aparte o en background)
cd /tmp/capio_mnt
CAPIO_DIR=/tmp/capio_mnt capio_server -c <ruta>/test.json

# writer
cd /tmp/capio_mnt
CAPIO_DIR=/tmp/capio_mnt CAPIO_WORKFLOW_NAME=test CAPIO_APP_NAME=writer \
LD_PRELOAD=libcapio_posix.so <ruta>/capio_smoke/writer

# reader
CAPIO_DIR=/tmp/capio_mnt CAPIO_WORKFLOW_NAME=test CAPIO_APP_NAME=reader \
LD_PRELOAD=libcapio_posix.so <ruta>/capio_smoke/reader
```

**Resultado y prueba de que la intercepción es real** (no basta con que "funcione"):

| Prueba | Resultado |
|---|---|
| `writer` bajo CAPIO | escribe 12 bytes en `test.txt` |
| `reader` bajo CAPIO | lee 12 bytes: `hello capio` |
| `test.txt` en el FS real | **NO existe** |
| `reader` **sin** `LD_PRELOAD` | `No such file or directory` (exit 1) |

La última fila es la evidencia concluyente: el archivo solo existe dentro de CAPIO. Metadata que lo confirma en `/tmp/capio_mnt/files_location_<nodo>.txt`: `/tmp/capio_mnt/test.txt <nodo>`.

El servidor parseó bien el workflow: `test.txt`, productor `writer`, consumidor `reader`, commit `on_close`, fire `no_update` → semántica CoC/FnU del paper aplicándose.

**Trampa evitada:** si `CAPIO_WORKFLOW_NAME` no coincide exactamente con el campo `"name"` del JSON, CAPIO no aplica reglas y el archivo va al disco normal — parecería funcionar sin estar probando nada.

**Hallazgo:** el build actual tiene `CAPIO_LOG:BOOL=OFF`, por eso el servidor no registra el manejo de peticiones y el log parece vacío. No es un fallo, pero **para F2 (tracing de syscalls) hay que recompilar con `-DCAPIO_LOG=TRUE`**.

## 2. Pasada de calidad sobre `one_to_one.cpp` (commit `f6e6dca`)

Revisión en 4 ángulos (reuse / simplificación / eficiencia / altitud). 201 → 186 líneas, comportamiento verificado idéntico (9 casos de CLI comparados contra la versión previa: stdout, stderr y exit codes → 0 diferencias; `fill_pattern` byte-a-byte idéntico).

- **Causa raíz del estilo inconsistente:** las variables se llamaban igual que sus tipos (`config config`, `role role`), lo que *obligaba* a escribir `struct config`/`enum role`. Tipos renombrados a `Role`/`Engine`/`Config` → desaparece toda la ceremonia C. (GCC 15 lo rechaza de plano: `-Wchanges-meaning`.)
- Helper `die()` colapsa ~10 repeticiones de `cerr << msg; usage(...)`; las validaciones pasan a 1 línea.
- `prog_name` como estático de archivo en vez de enhebrarlo por 3 firmas y 11 llamadas.
- Fuera 3 banners de sección + banner huérfano tras `main`; añadido salto de línea final.
- Comentarios obvios eliminados; sustituidos por uno que explica lo NO obvio (por qué el patrón usa posición absoluta).
- `parse_positive` → `std::from_chars`, que es el idiom que el repo ya usa 3× (`capio/common/env.hpp:101`).
- Invariante de bucle sacado de `fill_pattern`.

**Descartado con motivo:** reducción de fuerza manual en `fill_pattern` (`-O2` ya lo hace por variable de inducción; costaría legibilidad) y quitar la dependencia de liburing del CMake (el motor uring llega en días).

**Decisiones discutidas y mantenidas:**
- `[[noreturn]]` se queda: medido — sin él aparece `-Wimplicit-fallthrough`. Es la anotación correcta (declara un hecho) frente a un `break` que sería código muerto silenciando el síntoma. Su valor crece cuando el código de I/O use `die()` tras comprobar `fd`.
- Los 7 bloques de validación NO se convierten en tabla: la repetición es de *forma*, no de *mecanismo*, y 2 de las 7 comprobaciones no encajarían → acabaríamos con tabla + ifs sueltos (dos estilos). Regla: deduplicar mecanismo, no forma.

## 3. F1 · Hito 3 (motor POSIX) — arrancado, sin terminar

Paso 1 hecho (sin commitear): helpers `file_path()`, `write_all()`, `read_all()`.
- `write_all`/`read_all` manejan escrituras/lecturas parciales y reintentan en `EINTR`; `read_all` además detecta EOF prematuro (archivo más corto de lo esperado = fallo de verificación).
- `file_path` sin `PATH_MAX`: formatea solo el nombre (tamaño acotado) y concatena el directorio con `std::string` → sin límite artificial ni truncamiento silencioso con rutas largas.

Pendiente: Paso 2 (`posix_write_file`), Paso 3 (`posix_read_file`), Paso 4 (conectar `main`).

# Martes Jul 21 (cont.) — F1 · Hito 2 (checksum + patrón) cerrado

- **`fnv1a(hash, data, len)`** — FNV-1a de 64 bits, incremental (recibe hash actual, devuelve actualizado), para poder alimentarlo chunk a chunk. Verificado con los vectores canónicos: `""` → `0xcbf29ce484222325`, `"a"` → `0xaf63dc4c8601ec8c`. Constantes: OFFSET_BASIS `0xcbf29ce484222325`, PRIME `0x100000001b3`.
- **`fill_pattern(buf, len, file_idx, offset)`** — genera bytes deterministas. Fórmula final: `buf[i] = (offset + i) * 31 + file_idx * 131 + 7` (trunca a `unsigned char`).
- **Bug corregido en la 1ª versión (importante, va al cap. de diseño como lección):** el patrón inicial usaba `hash(offset) ^ file_idx ^ i`, que trata el inicio de chunk `offset` y el índice intra-chunk `i` por separado → el byte en la MISMA posición absoluta del archivo cambiaba según el troceo. Como producer y consumer son procesos separados y `-c` (chunk) es parametrizable, la verificación habría fallado en falso al usar chunks distintos. Regla: **el patrón debe ser función pura de la posición absoluta `offset + i`**, no de `offset` e `i` por separado. Además, la 1ª versión llamaba a `fnv1a` por cada byte → coste de CPU que contaminaría las mediciones de I/O; el generador debe ser barato (aritmética, no hash). El hash queda solo para el checksum de integridad.
- Verificado con arnés aparte (`/tmp/t.cpp`): posición-estable (pos abs 100 igual con dos particionados) y archivos distintos → contenido distinto. Binario real recompila OK.
- Nota: el self-test vive de momento en el arnés, no en `main` (que solo parsea/imprime). Decidir más adelante si añadir un `self_test()` como test de CI.

# Martes Jul 21 (cont.) — F1 · CMakeLists del ejemplo cerrado

- `examples/io_uring/CMakeLists.txt` como **mini-proyecto autónomo** (con `project()` propio), no como hoja estilo MPI. Motivo: `examples/` no está enganchado al build raíz de CAPIO, y un ejemplo didáctico gana en ser autoconstruible (`cmake -S examples/io_uring -B build && cmake --build build`).
- liburing localizado con pkg-config: `find_package(PkgConfig REQUIRED)` + `pkg_check_modules(liburing REQUIRED IMPORTED_TARGET liburing)`, enlazado con `target_link_libraries(one_to_one PRIVATE PkgConfig::liburing)`.
- **Lección (tropezón):** el target imported se llama `PkgConfig::<PREFIJO>` donde `<PREFIJO>` es el 1er argumento de `pkg_check_modules`, NO el nombre del módulo. Con prefijo y módulo ambos `liburing`, queda `PkgConfig::liburing` y es legible.
- Estándar fijado a C++17 (`CMAKE_CXX_STANDARD 17` + `REQUIRED ON`), igual que el raíz. Configura/compila/enlaza/corre OK con liburing 2.11. Nota: aún no se usa ningún símbolo de liburing (llega en el motor uring, Hito 3); enlazar ya está bien.

Pendiente inmediato: Hito 2 (FNV-1a de 64 bits + patrón determinista, funciones puras sin I/O).

# Martes Jul 21 — F1 · Hito 1 (parseo CLI) cerrado + decisión C++

1. **CLI de `one_to_one` completa y verificada.** Parseo con `getopt(3)`: `-r role`, `-n n_files`, `-f file_size`, `-c chunk_size`, `-q queue_depth`, `-e engine`, `-d dir`, `-h`. Valores obligatorios validados (`-q` solo si el motor es io_uring); `parse_positive` rechaza no-numéricos y no-positivos; `chunk_size <= file_size`. `main` imprime la config parseada (verificación del hito). Casos probados: sin args, válido, `-h` (sale 0), falta obligatorio, chunk>file, basura numérica.

2. **Decisión: el ejemplo pasa de C a C++** (revierte la nota de "en C" del PLAN §6). Motivo: todo el repo de CAPIO es C++ y los `examples/` existentes son `.cpp`; para un primer PR conviene mimetizarse con el registro del proyecto, más aún con los maintainers sensibles al tema LLM. liburing es API de C pero se usa sin fricción desde C++.
   - CAPIO compila con **C++17** (`CMAKE_CXX_STANDARD 17`) → nada de inicializadores designados (`.campo=`, son C++20/extensión). Se usan **default member initializers** en el `struct config` (estándar C++11), que además dan el default `dir = "."` de forma limpia.
   - `usage()` marcada `[[noreturn]]` (mata el warning de fallthrough en el `case 'h'` y es la anotación correcta).
   - Simplificaciones acordadas para bajar el over-engineering al registro del repo: `parse_positive` sin cota `max` (solo `>0` y `*end=='\0'`); `usage()` siempre a `stderr`.
   - Compila con `g++ -std=c++17 -Wall -Wextra -pedantic` **sin warnings**.

3. **Confirmado:** los `examples/` NO están enganchados al `CMakeLists.txt` raíz (solo `capio/posix`, `capio/server`, `capio/tests`) → el ejemplo es autocontenido y el PR queda mínimo.

Pendiente inmediato: rellenar `examples/io_uring/CMakeLists.txt` (pkg-config liburing) y arrancar Hito 2 (FNV-1a + patrón determinista, funciones puras sin I/O).

# Lunes Jul 20 — arranque de F1

Contexto retomado: F0 completado (suite verde el 23 jun, de ahí salió el PR #243). El PR #243 sigue abierto en upstream: marcoSanti retiró su aprobación el 28 jun por dudas de licenciamiento con código LLM (el trailer `Co-Authored-By: Claude`). Decisión: los commits del fork van sin trailers de LLM; el código de la tesis lo escribo yo, Claude acompaña/revisa.

1. Rama nueva para el Entregable A, desde upstream limpio (no desde `6b14036`: el pin es para el trabajo de intercepción de F3; el ejemplo va como PR contra el master actual de upstream, `07427e3`):

```
git fetch upstream
git switch -c feature/io-uring-example upstream/master
# al publicar: git push -u origin feature/io-uring-example
```

2. Instalar liburing (quedó la 2.11):

```
sudo apt install liburing-dev
pkg-config --modversion liburing   # 2.11
```

3. Esqueleto de `examples/io_uring/` (autocontenido — los ejemplos existentes no están conectados al CMake raíz, así el PR queda mínimo):

```
examples/io_uring/
├── CMakeLists.txt        # ojo: L mayúscula, CMake es case-sensitive
├── README.md
├── capio_config.json     # on_close + no_update, estilo Fig. 5 del paper
└── one_to_one.c          # producer y consumer en el mismo binario
```

Diseño acordado: CLI `one_to_one <producer|consumer> -n -s -b -q -e posix|uring`; motores POSIX/uring detrás de una interfaz común de punteros a función; checksum FNV-1a de 64 bits; datos deterministas (patrón por índice de archivo + offset). Orden: primero CLI + FNV-1a + motor POSIX (baseline y maquinaria de verificación), después el motor uring. Sin fixed buffers ni SQPOLL.

# Domingo Jun 21
1. Actualizar dependencias.

```
sudo apt update
sudo apt install -y \
  cmake ninja-build make build-essential \
  openmpi-bin libopenmpi-dev gfortran \
  pkg-config git jq wget tar
```

2. Compilar CAPIO con los test e instalar.

```
cmake -DCMAKE_BUILD_TYPE=Release \
      -DCAPIO_BUILD_TESTS=ON \
      -G Ninja \
      -B build -S .

cmake --build build -j"$(nproc)"
sudo cmake --install build --prefix /usr/local
export LD_LIBRARY_PATH="/usr/local/lib:${LD_LIBRARY_PATH}"
```

3. Suite de tests

```
jq -n --arg pwd "$(pwd)" \
  '{name:"CAPIO", IO_Graph:[], exclude:[$pwd+"/aNonExistingFile", $pwd, $pwd+"/"]}' \
  > test_config.json
export CONFIG_PATH="$(realpath test_config.json)"
export CAPIO_DIR="$(pwd)"
export CAPIO_LOG_LEVEL=-1

capio_posix_unit_tests   --gtest_break_on_failure --gtest_print_time=1
capio_server_unit_tests  --gtest_break_on_failure --gtest_print_time=1
LD_PRELOAD=libcapio_posix.so \
capio_syscall_unit_tests --gtest_break_on_failure --gtest_print_time=1

rm -rf /dev/shm/CAPIO*
LD_PRELOAD=libcapio_posix.so \
capio_integration_tests  --gtest_break_on_failure --gtest_print_time=1


```