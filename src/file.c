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
#include <unistd.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <sys/statvfs.h>

#include "file.h"

// Helper function to copy a file stream.
// Since uses low lever file descriptors it works with sockets too.
// Optional "count" parameter limits how many bytes to copy,
// use <0 to copy the entire stream. Returns 0 on success, -1 on error.
int copy_stream(int source, int destination, ssize_t count)
{
    ssize_t copied = 0;
    ssize_t block = 0;
    char buffer[1024];

    if (count == 0) return 0;
    while (count < 0 || copied < count) {
        block = read(source, buffer, sizeof(buffer));
        if (block < 0 || (block == 0 && count > 0 && copied < count)) {
            return -1;
        }
        if (block == 0) {
            return 0;
        }
        copied = copied + block;
        while (block > 0) {
            ssize_t tmp = write(destination, buffer, block);
            if (tmp <= 0) {
                return -1;
            }
            block = block - tmp;
        }
    }
    return 0;
}

// Helper function to get the free space available in a given mount point.
// Returns -1 on error.
ssize_t get_free_space(const char *pathname)
{
    struct statvfs svfs;
    if (statvfs(pathname, &svfs) < 0) return -1;
    return svfs.f_bfree * svfs.f_bsize;
}
