# MHPC Thesis 2026 — Transparent io_uring Interception in CAPIO

Thesis workspace. Everything that is **not** meant to be upstreamed to
[High-Performance-IO/capio](https://github.com/High-Performance-IO/capio) lives here;
code intended for upstream lives in the [fork](https://github.com/RaionG18/capio),
always branched from `upstream/master`.

## Layout

| Path | Contents |
|---|---|
| [PLAN.md](PLAN.md) | Thesis plan: research questions, design decision (syscall-level emulation), phases F0–F7 |
| [BITACORA.md](BITACORA.md) | Work log (dated entries with the exact commands used) |
| [test.json](test.json) | Supervisor's 1-to-1 writer/reader CAPIO-CL config (`on_close` + `no_update`) — used for the F0 baseline and scaled to GBs for first measurements |
| [capio_iouring/](capio_iouring/) | Motivational prototype: `LD_PRELOAD` observer that interposes `io_uring_submit()` and dumps SQEs (design-chapter material) |
| [Papers/](Papers/) | Reference papers and reading notes |
| [old/](old/) | First experimental step (ML workflow + POSIX I/O tracing observer), kept for the record |
| `spikes/` | *(to be created in F2b)* time-boxed liburing-interposition spike — never merged into the fork |

## Quick pointers

- Upstream CAPIO paper: *CAPIO: a Middleware for Transparent I/O Streaming in
  Data-Intensive Workflows* (HiPC 2023, DOI 10.1109/HiPC58850.2023.00031)
- Fork kept clean for upstream PRs; see PLAN.md §5 for the phase plan and
  PLAN.md §11 for the current next action.
