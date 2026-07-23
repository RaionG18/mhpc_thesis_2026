/* Minimal CAPIO smoke test: writes a short string to test.txt.
 * Pairs with the "writer" node of test.json. */

#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv)
{
    const char *path = argc > 1 ? argv[1] : "test.txt";
    const char *msg  = "hello capio\n";
    const size_t len = strlen(msg);

    int fd = open(path, O_CREAT | O_WRONLY | O_TRUNC, 0644);

    if (fd < 0) {
        perror("writer: open");
        return 1;
    }

    if (write(fd, msg, len) != (ssize_t) len) {
        perror("writer: write");
        close(fd);
        return 1;
    }

    close(fd);
    printf("writer: wrote %zu bytes to %s\n", len, path);

    return 0;
}
