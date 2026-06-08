# io_uring: Minimal observer

## What it does

- `demo.c` creates a ring with `liburing` and writes and reads a file using `io_uring`.
- `observer.c` is loaded with `LD_PRELOAD` and intercepts `io_uring_submit()`.
- Before the SQEs are sent to the kernel, it prints opcode, fd, length, offset, and `user_data`.

## Build and run

```bash
make run
```

Expected output:

```text
observer: op=WRITE fd=3 len=20 off=0 user_data=1
observer: op=READ fd=3 len=63 off=0 user_data=2
app read: hola desde io_uring
```

## Dependencies

```bash
sudo apt install liburing-dev
```