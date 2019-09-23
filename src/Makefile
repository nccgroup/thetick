#
# The Tick, a Linux embedded backdoor.
# 
# Released as open source by NCC Group Plc - http://www.nccgroup.com/
# Developed by Mario Vilas, mario.vilas@nccgroup.com
# http://www.github.com/nccgroup/thetick
# 
# See the LICENSE file for further details.
#

##############################################################################
# Uncomment all but one of the following to select the target for compilation:

TARGET="generic"
#TARGET="lexmark-cx310dn"

##############################################################################
# Source, object and binary files.

SRC=$(wildcard *.c)
ASM=$(patsubst %.c,%.s,$(SRC))
OBJ=$(patsubst %.c,%.o,$(SRC))
BIN=../bin/ticksvc

##############################################################################
# Platform dependent configuration.

# Cross-compile for the Lexmark CX310DN printer.
ifeq ($(TARGET),"lexmark-cx310dn")
CC=arm-linux-gnueabi-gcc
AS=arm-linux-gnueabi-as -meabi=4
ST=arm-linux-gnueabi-strip
CPPFLAGS=-I../deps/$(TARGET)/curl/include -I./ -I../deps/$(TARGET)/openssl/include -I../deps/$(TARGET)/zlib
LDDFLAGS=-L../deps/$(TARGET)/openssl -L../deps/$(TARGET)/zlib -L../deps/$(TARGET)/curl/lib/.libs -Wl,-rpath-link,../deps/$(TARGET)/openssl -Wl,-rpath-link,../deps/$(TARGET)/zlib -Wl,-rpath-link,../deps/$(TARGET)/curl/lib/.libs -lssl -lz -lcurl
PRECMD=@bash -c "pushd ../deps/$(TARGET) >/dev/null ; ./build-deps.sh; popd >/dev/null"
BINCMD=sed -i 's/libcurl.so.4/libcurl.so.5/g'
POSTCMD=@true
endif

# Compile for the local platform.
ifeq ($(TARGET),"generic")
CC=gcc
AS=as
ST=@true
CPPFLAGS=-g
LDDFLAGS=$$(pkg-config --libs --cflags libcurl)
PRECMD=@true
BINCMD=@true
POSTCMD=@true
endif

##############################################################################
# Make targets.

.PHONY: all clean pre-build main-build post-build

all: post-build
	@echo Finished building for platform: $(TARGET)

pre-build:
	@echo Building for platform: $(TARGET)
	$(PRECMD)

main-build: pre-build
	@$(MAKE) --no-print-directory $(BIN)

post-build: main-build
	$(POSTCMD)

%.s: %.c
	$(CC) -S $< $(CPPFLAGS) -o $@

%.o: %.s
	$(AS) $< -o $@

$(BIN): $(OBJ)
	mkdir -p -- $$(dirname $@)
	$(CC) $(OBJ) $(LDDFLAGS) -o $@
	$(ST) $@
	$(BINCMD) $@

clean:
	rm -f -- $(ASM) $(OBJ) $(BIN)
