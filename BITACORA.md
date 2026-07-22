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