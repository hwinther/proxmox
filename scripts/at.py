from __future__ import annotations

import os
import socket
import sys
import threading


class Buffer(object):
    """
    Copied from RadioNetwork.Handlers.PacketParser
    :type Packets: list(bytes)
    :type packetBuffer: bytes
    :type end_chars: bytes
    """

    def __init__(self, end_chars, verbose=False):
        """
        :rtype: Buffer
        """
        self.Packets = list()
        self.packetBuffer = b''
        if type(end_chars) is str:
            end_chars = end_chars.encode('ascii')
        self.end_chars = end_chars
        self.verbose = verbose

    def parse(self, packet_data: bytes) -> None:
        if type(packet_data) is str:
            packet_data = packet_data.encode('ascii')

        if packet_data == b'':
            return

        self.packetBuffer += packet_data
        if self.verbose:
            print('packetBuffer is now:', repr(self.packetBuffer))
        if self.packetBuffer.find(self.end_chars) == -1:
            return

        rest = b''
        if self.packetBuffer.endswith(self.end_chars):
            for segment in self.packetBuffer.split(self.end_chars):
                if segment == b'':
                    continue
                self.Packets.append(segment)
                if self.verbose:
                    print('appending segment', repr(segment))
        else:
            segments = self.packetBuffer.split(self.end_chars)
            for segment in segments[-1]:
                if segment == b'':
                    continue
                self.Packets.append(segment)
                if self.verbose:
                    print('appending segment', repr(segment))
            rest = segments[-1]
            if self.verbose:
                print('setting rest', repr(segments[-1]))

        self.packetBuffer = rest

    def pop(self) -> bytes | None:
        if len(self.Packets) != 0:
            return self.Packets.pop(0)
        return None


class SocketReceiveProxy(threading.Thread):
    def __init__(self, receive_socket: socket.socket, send_socket: socket.socket):
        super().__init__()
        self.receive_socket = receive_socket
        self.send_socket = send_socket

    def run(self):
        while True:
            data = self.receive_socket.recv(1024)
            if data == b'':
                # disconnected
                break
            print('Forwarding data:', repr(data))
            self.send_socket.sendall(data)


class Modem(object):
    connection: socket.socket = None
    buffer: Buffer = None
    relay: bool = None
    dial_target: str = None
    dial_socket: socket.socket | None = None
    dial_proxy: SocketReceiveProxy | None = None
    echo: bool = None
    verbose: bool = None
    quiet: bool = None
    phonebook: dict[str, str] = {}

    def __init__(self, connection: socket):
        self.connection = connection
        self.buffer = Buffer(end_chars=b'\r')

        # Modem states
        self.relay = False  # relay data mode to dial_target
        self.echo = False
        self.verbose = False
        self.quiet = False
        self.phonebook['5551000'] = 'bbs.fozztexx.com:23'
        self.phonebook['5551001'] = 'particlesbbs.dyndns.org:6400'
        self.phonebook['5559000'] = '10.20.1.210:2323'

    def recv(self, buf_size: int):
        data = self.connection.recv(buf_size)
        if data == b'':
            print('empty')
            self.end_dial()
            return
            
        print('<- Received data:', repr(data))
        if self.echo:
            self.connection.sendall(data)

        if data == b'+++':
            # modem command mode, should not break connection
            # it will not be followed by \r so it should skip the packet buffer
            self.send_ok()
            self.relay = False
            return

        if self.relay:
            print('In relay mode with %s (%s)' % (self.dial_target, self.dial_socket))
            if self.dial_socket is not None:
                try:
                    self.dial_socket.sendall(data)
                except socket.error:
                    print('Remote socket probably closed')
                    self.end_dial()
                    self.relay = False
            return

        self.buffer.parse(data)
        while True:
            packet = self.buffer.pop()
            if packet is None:
                break

            try:
                cmd = packet.decode()
            except UnicodeDecodeError:
                print('UnicodeDecodeError, discarding packet input')
                continue

            print('Handling:', repr(cmd))

            if cmd == 'AT':
                self.send_ok()
            elif cmd == 'ATH':
                print(f'Hang up from: {self.dial_target}')
                self.end_dial()
                self.send('NO CARRIER')
            elif cmd == 'ATZ':
                print(f'Modem reset (noop)')
                self.send_ok()
            elif cmd.startswith('ATDT'):
                self.dial_target = cmd[4:].strip()
                print(f'Dialing: {self.dial_target}')
                self.send('RING')
                if self.dial_target in self.phonebook:
                    self.end_dial()  # in case there are lingering objects, try to clean them up first
                    print('Connecting to', self.phonebook[self.dial_target])
                    self.dial_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    host, port = self.phonebook[self.dial_target].split(':')
                    port = int(port)
                    self.dial_socket.connect((host, port))
                    self.dial_proxy = SocketReceiveProxy(self.dial_socket, self.connection)
                    self.send_ok()
                    print('Starting dial_proxy')
                    self.dial_proxy.start()
                    self.relay = True
                elif self.dial_target == '12345678':
                    print('No phone book entry, test/empty relay')
                    self.send_ok()
                    self.relay = True
                else:
                    self.send('BUSY')
            elif cmd.startswith('AT'):
                # command set parse loop, expect letters to possibly be followed by a single digit
                self.command_parse(cmd[2:])
                self.send_ok()
            else:
                print('!! Unknown command:', repr(cmd))

    def command_parse(self, cmd):
        i = 0
        for c in cmd.upper():
            if c == ' ':
                pass
            elif c.isalpha():
                d = 0 if len(cmd) > i or not cmd[i + 1].isdigit() else int(cmd[i + 1])
                print('AT c=%s d=%d' % (c, d))
                # TODO: move ATDT handler here?
                # if c == 'D'
                if c == 'E':
                    # 1 = echo / 0 = no echo
                    self.echo = d == 1
                    print('echo', 'on' if self.echo else 'off')
                elif c == 'I':
                    # inquiry, information or interrogation 0-9
                    if d == 0:
                        self.send('PROXMOX-AT-PY')
                    else:
                        self.send('ERROR')
                elif c == 'Q':
                    # 1 = quiet mode / 0 = quiet mode off
                    self.quiet = d == 1
                    print('quiet mode', 'on' if self.quiet else 'off')
                elif c == 'V':
                    # verbose, 0 = numeric result codes, 1 = english result codes
                    self.verbose = d == 1
                    print('verbose', 'on' if self.verbose else 'off')
                else:
                    print('!! Unhandled AT command c=%s d=%d' % (c, d))
            i += 1

    def send_ok(self):
        self.send('OK')

    def send(self, data):
        print(f'-> Sending: {data}')
        self.connection.sendall(f'{data}\r'.encode())

    def end_dial(self):
        if self.dial_proxy is not None:
            self.dial_proxy.join(0.1)
            self.dial_proxy = None
        if self.dial_proxy is not None:
            self.dial_socket.close()
            self.dial_socket = None


def main():
    socket_path = '/tmp/at-py'

    try:
        os.unlink(socket_path)
    except OSError:
        if os.path.exists(socket_path):
            raise

    try:
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(socket_path)
        server.listen(1)

        print('Server is listening for incoming connections...')

        while True:
            connection, client_address = server.accept()
            print('Connection from', str(connection).split(", ")[0][-4:])
            modem_client = Modem(connection)

            try:
                while True:
                    modem_client.recv(1024)
            except KeyboardInterrupt:
                print('Exiting')
                modem_client.end_dial()
                break
            except OSError:
                print('Caught OSError', sys.exc_info()[0])
            finally:
                print('Closing connection')
                connection.close()
    finally:
        print('Closing socket')
        os.unlink(socket_path)


if __name__ == '__main__':
    main()
