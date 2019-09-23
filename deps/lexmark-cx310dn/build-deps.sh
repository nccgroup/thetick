#!/bin/bash

# This script will build all the dependencies for The Tick for the Lexmark printer.

# Stop on any errors.
set -e

# Make sure we are in the correct directory.
pushd $(dirname $0) >/dev/null

# Download zlib.
if [[ -f zlib/ChangeLog ]]
then
    echo "zlib already downloaded"
else
    wget https://www.zlib.net/zlib-1.2.11.tar.gz
    tar -xvzf zlib-1.2.11.tar.gz
    ln -s zlib-1.2.11 zlib
fi

# Download openssl.
if [[ -f openssl/CHANGES ]]
then
    echo "openssl already downloaded"
else
    wget https://www.openssl.org/source/old/1.0.2/openssl-1.0.2j.tar.gz
    tar -xvzf openssl-1.0.2j.tar.gz
    ln -s openssl-1.0.2j openssl
fi

# Download curl.
if [[ -f curl/CHANGES ]]
then
    echo "curl already downloaded"
else
    wget https://curl.haxx.se/download/curl-7.20.0.tar.bz2
    tar -xvjf curl-7.20.0.tar.bz2
    ln -s curl-7.20.0 curl
fi

# Common variables.
export CROSS_COMPILE_PREFIX="arm-linux-gnueabi"
export AR=${CROSS_COMPILE_PREFIX}-ar
export AS=${CROSS_COMPILE_PREFIX}-as
export LD=${CROSS_COMPILE_PREFIX}-ld
export RANLIB=${CROSS_COMPILE_PREFIX}-ranlib
export CC=${CROSS_COMPILE_PREFIX}-gcc
export NM=${CROSS_COMPILE_PREFIX}-nm

# Let's build zlib, the easiest one.
pushd zlib >/dev/null
if [[ -f libz.a && -f libz.so ]]
then
    echo "zlib already built, skipping"
else
    ./configure --prefix=$(pwd)
    make clean
    make
fi
popd >/dev/null

# Let's build openssl next.
pushd openssl >/dev/null
if [[ -f libcrypto.a && -f libcrypto.so && -f libssl.a && -f libssl.so ]]
then
    echo "openssl already built, skipping"
else
    ./Configure linux-generic32 shared -DL_ENDIAN --prefix=${PWD} --openssldir=${PWD}
    make clean
    make CC=arm-linux-gnueabi-gcc RANLIB=arm-linux-gnueabi-ranlib LD=arm-linux-gnueabi-ld MAKEDEPPROG=arm-linux-gnueabi-gcc PROCESSOR=ARM
fi
popd >/dev/null

# Let's build curl now. Depends on zlib and openssl.
pushd curl >/dev/null
if [[ -f lib/.libs/libcurl.a && -f lib/.libs/libcurl.so ]]
then
    echo "curl already built, skipping"
else
    export CROSS_COMPILE=${CROSS_COMPILE_PREFIX}
    export ROOTDIR="${PWD}"
    export CPPFLAGS="-I${ROOTDIR}/../openssl/include -I${ROOTDIR}/../zlib"
    export LDFLAGS="-L${ROOTDIR}/../openssl -L${ROOTDIR}/../zlib"
    export LIBS="-lssl -lcrypto"
    ./configure --prefix=${ROOTDIR}/build --target=${CROSS_COMPILE} --host=${CROSS_COMPILE} --build=i586-pc-linux-gnu --with-ssl --with-zlib --with-random=/dev/urandom
    make clean
    make
fi
popd >/dev/null

# We're done!
popd >/dev/null
