CC=gcc
CFLAGS=-Wall -O2

all: hello

hello: hello.c
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f hello

.PHONY: all clean
