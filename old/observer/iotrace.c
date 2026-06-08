#define _GNU_SOURCE

#include <dlfcn.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

#define MAX_FDS  4096
#define MAX_PATH 512

static int log_fd = -1;
static char fd_paths[MAX_FDS][MAX_PATH];

static ssize_t (*real_read)(int, void *, size_t)            = NULL;
static ssize_t (*real_write)(int, const void *, size_t)     = NULL;
static int     (*real_open)(const char *, int, ...)         = NULL;
static int     (*real_openat)(int, const char *, int, ...)  = NULL;
static int     (*real_close)(int)                           = NULL;

static long long now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ((long long)ts.tv_sec * 1000000000LL) + ts.tv_nsec;
}

static void record_fd(int fd, const char *path) {
    if (fd >= 0 && fd < MAX_FDS && path != NULL) {
        strncpy(fd_paths[fd], path, MAX_PATH - 1);
        fd_paths[fd][MAX_PATH - 1] = '\0';
    }
}

static void forget_fd(int fd) {
    if (fd >= 0 && fd < MAX_FDS) {
        fd_paths[fd][0] = '\0';
    }
}

static void resolve_proc_fd(int fd) {
    if (fd < 0 || fd >= MAX_FDS || fd_paths[fd][0] != '\0') {
        return;
    }
    char proc_path[64];
    snprintf(proc_path, sizeof(proc_path), "/proc/self/fd/%d", fd);
    ssize_t len = readlink(proc_path, fd_paths[fd], MAX_PATH - 1);
    if (len > 0) {
        fd_paths[fd][len] = '\0';
    }
}

/* Read /proc/self/cmdline using raw syscalls so we don't recurse into our
   own read() hook. Args are NUL-separated; convert to spaces and strip any
   CSV-breaking characters since the result goes in the last (path) field. */
static void read_cmdline(char *buf, size_t bufsize) {
    buf[0] = '\0';

    int fd = (int)syscall(SYS_openat, AT_FDCWD, "/proc/self/cmdline", O_RDONLY, 0);
    if (fd < 0) {
        return;
    }

    ssize_t n = syscall(SYS_read, fd, buf, bufsize - 1);
    syscall(SYS_close, fd);

    if (n <= 0) {
        buf[0] = '\0';
        return;
    }

    for (ssize_t i = 0; i < n; i++) {
        char c = buf[i];
        if (c == '\0' || c == ',' || c == '\n' || c == '\r') {
            buf[i] = ' ';
        }
    }
    buf[n] = '\0';

    while (n > 0 && buf[n - 1] == ' ') {
        buf[--n] = '\0';
    }
}

static void log_line(const char *op, int fd, size_t count, ssize_t result,
                     const char *path) {
    if (log_fd < 0) {
        return;
    }

    char line[MAX_PATH + 128];
    int len = snprintf(
        line,
        sizeof(line),
        "%lld,%d,%s,%d,%zu,%zd,%s\n",
        now_ns(),
        (int)getpid(),
        op,
        fd,
        count,
        result,
        path ? path : ""
    );

    if (len > 0) {
        syscall(SYS_write, log_fd, line, (size_t)len);
    }
}

static void log_event(const char *op, int fd, size_t count, ssize_t result) {
    if (log_fd < 0 || fd == log_fd) {
        return;
    }

    const char *path = (fd >= 0 && fd < MAX_FDS) ? fd_paths[fd] : "";
    log_line(op, fd, count, result, path);
}

__attribute__((constructor))
static void init_iotrace(void) {
    real_read   = dlsym(RTLD_NEXT, "read");
    real_write  = dlsym(RTLD_NEXT, "write");
    real_open   = dlsym(RTLD_NEXT, "open");
    real_openat = dlsym(RTLD_NEXT, "openat");
    real_close  = dlsym(RTLD_NEXT, "close");

    memset(fd_paths, 0, sizeof(fd_paths));

    const char *path = getenv("IOTRACE_LOG");
    if (path == NULL) {
        path = "iotrace.log";
    }

    log_fd = (int)syscall(
        SYS_openat,
        AT_FDCWD,
        path,
        O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC,
        0644
    );

    /* Resolve stdin/stdout/stderr paths via /proc in case the shell
       opened them before LD_PRELOAD loaded us. */
    resolve_proc_fd(0);
    resolve_proc_fd(1);
    resolve_proc_fd(2);

    /* Emit a process-start marker carrying the command line, so the timeline
       analysis can map each PID to its pipeline stage and bound its lifespan. */
    char cmdline[MAX_PATH];
    read_cmdline(cmdline, sizeof(cmdline));
    log_line("start", -1, 0, 0, cmdline);
}

__attribute__((destructor))
static void fini_iotrace(void) {
    log_line("exit", -1, 0, 0, "");

    if (log_fd >= 0) {
        syscall(SYS_close, log_fd);
        log_fd = -1;
    }
}

/* ------------------------------------------------------------------ */

int open(const char *pathname, int flags, ...) {
    if (real_open == NULL) {
        real_open = dlsym(RTLD_NEXT, "open");
    }

    mode_t mode = 0;
    if (flags & O_CREAT) {
        va_list ap;
        va_start(ap, flags);
        mode = va_arg(ap, mode_t);
        va_end(ap);
    }

    int fd = real_open(pathname, flags, mode);
    if (fd >= 0) {
        record_fd(fd, pathname);
        log_event("open", fd, 0, fd);
    }
    return fd;
}

int openat(int dirfd, const char *pathname, int flags, ...) {
    if (real_openat == NULL) {
        real_openat = dlsym(RTLD_NEXT, "openat");
    }

    mode_t mode = 0;
    if (flags & O_CREAT) {
        va_list ap;
        va_start(ap, flags);
        mode = va_arg(ap, mode_t);
        va_end(ap);
    }

    int fd = real_openat(dirfd, pathname, flags, mode);
    if (fd >= 0) {
        record_fd(fd, pathname);
        log_event("open", fd, 0, fd);
    }
    return fd;
}

int close(int fd) {
    if (real_close == NULL) {
        real_close = dlsym(RTLD_NEXT, "close");
    }

    log_event("close", fd, 0, 0);
    forget_fd(fd);
    return real_close(fd);
}

ssize_t read(int fd, void *buf, size_t count) {
    if (real_read == NULL) {
        real_read = dlsym(RTLD_NEXT, "read");
    }

    resolve_proc_fd(fd);
    ssize_t result = real_read(fd, buf, count);
    log_event("read", fd, count, result);
    return result;
}

ssize_t write(int fd, const void *buf, size_t count) {
    if (real_write == NULL) {
        real_write = dlsym(RTLD_NEXT, "write");
    }

    resolve_proc_fd(fd);
    ssize_t result = real_write(fd, buf, count);
    log_event("write", fd, count, result);
    return result;
}
