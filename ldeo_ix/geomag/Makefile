# Generic minimal makefile for linux.

all: magdec

magdec: geomag_calc.o magdec.o Makefile igrf11.h
	$(CC) -o $@ geomag_calc.o magdec.o -lm

install: magdec
	install magdec /usr/local/bin

clean:
	$(RM) *.o  magdec
