# CAPIO + io_uring: observador mínimo

Esta es la versión más simple del prototipo.

## Qué hace

- `demo.c` crea un ring con `liburing`.
- Escribe y lee un archivo usando `io_uring`.
- `observer.c` se carga con `LD_PRELOAD`.
- El observador intercepta `io_uring_submit()`.
- Antes de enviar los SQEs al kernel, imprime opcode, fd, longitud, offset y `user_data`.

## Compilar y ejecutar

```bash
make run
```

Salida esperada:

```text
observer: op=WRITE fd=3 len=20 off=0 user_data=1
observer: op=READ fd=3 len=63 off=0 user_data=2
app read: hola desde io_uring
```

## Dependencias

```bash
sudo apt install liburing-dev
```

Necesita un kernel con soporte para `io_uring`.

## Por qué esta versión es más simple

Esta versión intercepta a nivel de `liburing`, no a nivel de syscall cruda.

Eso reduce muchísimo el código porque no hace falta:

- interceptar `io_uring_setup`;
- interceptar `mmap`;
- reconstruir manualmente los rings;
- mapear ring fd → SQ/CQ;
- parsear estructuras creadas directamente por el kernel.

## Limitación importante

Esto sirve como observador didáctico y funcional.

No basta para una integración completa con CAPIO porque solo funciona si la aplicación usa `liburing` dinámicamente. Una aplicación podría usar syscalls crudas, enlazar `liburing` estáticamente o usar otro wrapper.

Para CAPIO real, el camino robusto sigue siendo interceptar `io_uring_setup`, `io_uring_enter`, `io_uring_register` y los `mmap` asociados.
