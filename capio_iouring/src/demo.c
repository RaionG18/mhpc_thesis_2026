#include <liburing.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static int wait_cqe(struct io_uring *ring) {
    struct io_uring_cqe *cqe;
    int ret = io_uring_wait_cqe(ring, &cqe);
    if (ret < 0) return ret;

    ret = cqe->res;
    io_uring_cqe_seen(ring, cqe);
    return ret;
}

int main(void) {
    struct io_uring ring;
    const char *path = "demo.txt";
    const char *msg = "hola desde io_uring\n";
    char buf[64] = {0};

    int ret = io_uring_queue_init(8, &ring, 0);
    if (ret < 0) {
        fprintf(stderr, "io_uring_queue_init: %s\n", strerror(-ret));
        return 1;
    }

    int fd = open(path, O_CREAT | O_TRUNC | O_RDWR, 0644);
    if (fd < 0) {
        perror("open");
        io_uring_queue_exit(&ring);
        return 1;
    }

    struct io_uring_sqe *sqe = io_uring_get_sqe(&ring);
    io_uring_prep_write(sqe, fd, msg, strlen(msg), 0);
    sqe->user_data = 1;

    ret = io_uring_submit(&ring);
    if (ret < 0 || wait_cqe(&ring) < 0) {
        fprintf(stderr, "write failed\n");
        close(fd);
        io_uring_queue_exit(&ring);
        return 1;
    }

    sqe = io_uring_get_sqe(&ring);
    io_uring_prep_read(sqe, fd, buf, sizeof(buf) - 1, 0);
    sqe->user_data = 2;

    ret = io_uring_submit(&ring);
    if (ret < 0 || wait_cqe(&ring) < 0) {
        fprintf(stderr, "read failed\n");
        close(fd);
        io_uring_queue_exit(&ring);
        return 1;
    }

    printf("app read: %s", buf);

    close(fd);
    io_uring_queue_exit(&ring);
    return 0;
}
