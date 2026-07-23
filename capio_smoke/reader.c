/* Minimal CAPIO smoke test: reads test.txt and prints what it got.
 * Pairs with the "reader" node of test.json. */

#include <fcntl.h>
#include <stdio.h>
#include <unistd.h>

int main(int argc, char **argv)
{
    const char *path = argc > 1 ? argv[1] : "test.txt";
    char buf[256];

    int fd = open(path, O_RDONLY);

    if (fd < 0) {
        perror("reader: open");
        return 1;
    }

    ssize_t n = read(fd, buf, sizeof(buf) - 1);

    if (n < 0) {
        perror("reader: read");
        close(fd);
        return 1;
    }

    close(fd);

    buf[n] = '\0';
    printf("reader: read %zd bytes from %s: %s", n, path, buf);

    return n > 0 ? 0 : 1;
}
