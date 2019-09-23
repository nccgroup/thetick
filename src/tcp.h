/*
 * The Tick, a Linux embedded backdoor.
 * 
 * Released as open source by NCC Group Plc - http://www.nccgroup.com/
 * Developed by Mario Vilas, mario.vilas@nccgroup.com
 * http://www.github.com/nccgroup/thetick
 * 
 * See the LICENSE file for further details.
*/

#ifndef TCP_H
#define TCP_H

#include <sys/types.h>
#include <sys/socket.h>

int create_socket(int family);
int connect_socket(int fd, const struct sockaddr *sa, size_t count);
int connect_to_host(const char *hostname, int port);
int listen_on_port(const char *bind_addr, int *port);
int send_block(int fd, const char *buf, size_t count);
int recv_block(int sock, char *buf, size_t count);
ssize_t consume_extra_data(int fd, size_t count);
void disconnect_tcp(int fd);

#endif /* TCP_H */
