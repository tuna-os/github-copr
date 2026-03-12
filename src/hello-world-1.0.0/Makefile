CC=gcc
CFLAGS=-Wall -O2
DESTDIR?=

all: hello

hello: hello.c
	$(CC) $(CFLAGS) -o $@ $<

install: hello
	install -D -m 0755 hello $(DESTDIR)/usr/bin/hello-world

clean:
	rm -f hello

.PHONY: all clean install
