#define _GNU_SOURCE

#include <dlfcn.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

static int log_fd = -1;
static ssize_t (*real_read)(int, void *, size_t) = NULL;
static ssize_t (*real_write)(int, const void *, size_t) = NULL;

static long long now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ((long long)ts.tv_sec * 1000000000LL) + ts.tv_nsec;
}

static void log_event(const char *op, int fd, size_t count, ssize_t result) {
    if (log_fd < 0 || fd == log_fd) {
        return;
    }

    char line[256];
    int len = snprintf(
        line,
        sizeof(line),
        "%lld,%d,%s,%d,%zu,%zd\n",
        now_ns(),
        getpid(),
        op,
        fd,
        count,
        result
    );

    if (len > 0) {
        syscall(SYS_write, log_fd, line, (size_t)len);
    }
}

__attribute__((constructor))
static void init_iotrace(void) {
    real_read = dlsym(RTLD_NEXT, "read");
    real_write = dlsym(RTLD_NEXT, "write");

    const char *path = getenv("IOTRACE_LOG");
    if (path == NULL) {
        path = "iotrace.log";
    }

    log_fd = syscall(
        SYS_openat,
        AT_FDCWD,
        path,
        O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC,
        0644
    );
}

__attribute__((destructor))
static void fini_iotrace(void) {
    if (log_fd >= 0) {
        syscall(SYS_close, log_fd);
        log_fd = -1;
    }
}

ssize_t read(int fd, void *buf, size_t count) {
    if (real_read == NULL) {
        real_read = dlsym(RTLD_NEXT, "read");
    }

    ssize_t result = real_read(fd, buf, count);
    log_event("read", fd, count, result);
    return result;
}

ssize_t write(int fd, const void *buf, size_t count) {
    if (real_write == NULL) {
        real_write = dlsym(RTLD_NEXT, "write");
    }

    ssize_t result = real_write(fd, buf, count);
    log_event("write", fd, count, result);
    return result;
}
