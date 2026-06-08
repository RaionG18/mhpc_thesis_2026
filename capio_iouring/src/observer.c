#define _GNU_SOURCE
#include <dlfcn.h>
#include <liburing.h>
#include <linux/io_uring.h>
#include <stdio.h>

static int (*real_io_uring_submit)(struct io_uring *ring);

static const char *op_name(unsigned op) {
    switch (op) {
        case IORING_OP_READ:   return "READ";
        case IORING_OP_WRITE:  return "WRITE";
        case IORING_OP_READV:  return "READV";
        case IORING_OP_WRITEV: return "WRITEV";
        case IORING_OP_OPENAT: return "OPENAT";
        case IORING_OP_CLOSE:  return "CLOSE";
        default:               return "OTHER";
    }
}

int io_uring_submit(struct io_uring *ring) {
    if (!real_io_uring_submit) {
        real_io_uring_submit = dlsym(RTLD_NEXT, "io_uring_submit");
        if (!real_io_uring_submit) {
            fprintf(stderr, "observer: cannot find real io_uring_submit\n");
            return -1;
        }
    }

    struct io_uring_sq *sq = &ring->sq;
    unsigned mask = *sq->kring_mask;

    for (unsigned i = sq->sqe_head; i < sq->sqe_tail; i++) {
        struct io_uring_sqe *sqe = &sq->sqes[i & mask];

        fprintf(stderr,
                "observer: op=%s fd=%d len=%u off=%llu user_data=%llu\n",
                op_name(sqe->opcode),
                sqe->fd,
                sqe->len,
                (unsigned long long)sqe->off,
                (unsigned long long)sqe->user_data);
    }

    return real_io_uring_submit(ring);
}
