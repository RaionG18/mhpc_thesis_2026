#include <liburing.h>
#include <fcntl.h>
#include <unistd.h>
#include <cstdio>
#include <cstring>

int main()
{
    // Stand in for CAPIO's open(): the exact fd its handler hands back.
    int fd = open("/dev/null", O_RDONLY);
    if (fd < 0) {
        perror("open /dev/null");
        return 1;
    }
    printf("fd %d  <- real kernel fd on /dev/null, O_RDONLY\n\n", fd);

    io_uring ring;
    if (int r = io_uring_queue_init(8, &ring, 0); r < 0) {
        fprintf(stderr, "io_uring_queue_init: %s\n", strerror(-r));
        return 1;
    }

    char buf[4096] = {0};
    io_uring_sqe *sqe = io_uring_get_sqe(&ring);
    io_uring_prep_write(sqe, fd, buf, sizeof buf, 0);
    io_uring_submit_and_wait(&ring, 1);

    io_uring_cqe *cqe;
    io_uring_wait_cqe(&ring, &cqe);
    const int res = cqe->res;
    io_uring_cqe_seen(&ring, cqe);
    io_uring_queue_exit(&ring);
    close(fd);

    printf("io_uring write -> res = %d (%s)\n", res, strerror(-res));
}
