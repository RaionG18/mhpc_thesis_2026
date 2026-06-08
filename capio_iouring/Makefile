CC ?= cc
CFLAGS ?= -Wall -Wextra -O2

all: demo observer.so

demo: src/demo.c
	$(CC) $(CFLAGS) -o $@ $< -luring

observer.so: src/observer.c
	$(CC) $(CFLAGS) -shared -fPIC -o $@ $< -ldl

run: all
	LD_PRELOAD=./observer.so ./demo

clean:
	rm -f demo observer.so demo.txt
