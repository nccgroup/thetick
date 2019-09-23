/*
 * The Tick, a Linux embedded backdoor.
 * 
 * Released as open source by NCC Group Plc - http://www.nccgroup.com/
 * Developed by Mario Vilas, mario.vilas@nccgroup.com
 * http://www.github.com/nccgroup/thetick
 * 
 * See the LICENSE file for further details.
*/

#ifndef COMMAND_H
#define COMMAND_H

#include <sys/types.h>
#include <stdint.h>

#include "parser.h"

// Main function.
int command_loop(Parser *p);

// Command implementations.
void do_file_read(Parser *p);
void do_file_write(Parser *p);
void do_file_delete(Parser *p);
void do_file_chmod(Parser *p);
void do_file_exec(Parser *p);
void do_http_download(Parser *p);
void do_dns_resolve(Parser *p);
void do_tcp_pivot(Parser *p);
void do_system_fork(Parser *p);
void do_system_shell(Parser *p);

#endif /* COMMAND_H */
