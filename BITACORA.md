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