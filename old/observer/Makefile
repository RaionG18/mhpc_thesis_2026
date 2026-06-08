CC=gcc
CFLAGS=-Wall -Wextra -O2 -fPIC
LDFLAGS=-shared -ldl

all: libiotrace.so

libiotrace.so: iotrace.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

clean:
	rm -f libiotrace.so
