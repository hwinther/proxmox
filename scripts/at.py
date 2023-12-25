import os
import socket
import sys


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


class Modem(object):
    connection: socket.socket = None

    def __init__(self, connection: socket):
        self.connection = connection
        self.buffer = Buffer(end_chars=b'\r')
        # Modem states
        self.dial_target = ''
        self.relay = False  # relay data mode to dial_target
        self.echo = False
        self.verbose = False

    def recv(self, buf_size: int):
        data = self.connection.recv(buf_size)
        print('<- Received data:', repr(data))
        if self.echo:
            self.connection.sendall(data)

        if data == b'+++':
            # modem break, will not be followed by \r so it should skip the packet buffer
            # TODO: break proxy connection here?
            self.send_ok()
            self.relay = False
            return

        if self.relay:
            print('In relay mode')
            return

        self.buffer.parse(data)
        while True:
            packet = self.buffer.pop()
            if packet is None:
                break

            cmd = packet.decode()
            print('Handling:', repr(cmd))

            if cmd == 'AT':
                self.send_ok()
            elif cmd == 'ATH':
                print(f'Hang up from: {self.dial_target}')
                self.send_ok()
            elif cmd == 'ATZ':
                print(f'Modem reset (noop)')
                self.send_ok()
            elif cmd.startswith('ATDT'):
                self.dial_target = cmd[4:]
                print(f'Dialing: {self.dial_target}')
                self.connection.sendall('RING\r'.encode())
                self.relay = True
            elif cmd.startswith('AT'):
                # command set parse loop, expect letters to possibly be followed by a single digit
                i = 2
                for c in cmd[2:].upper():
                    if c.isalpha():
                        d = 0 if len(cmd) < i or not cmd[i + 1].isdigit() else int(cmd[i + 1])
                        print('AT c=%s d=%d' % (c, d))
                        # TODO: move ATDT handler here?
                        # if c == 'D'
                        if c == 'E':
                            # 1 = echo / 0 = no echo
                            self.echo = d == 1
                            print('echo', 'on' if self.echo else 'off')
                        elif c == 'V':
                            # verbose, 0 = numeric result codes, 1 = english result codes
                            self.verbose = d == 1
                            print('verbose', 'on' if self.verbose else 'off')
                        else:
                            print('!! Unhandled AT command c=%s d=%d' % (c, d))
                    i += 1
                self.send_ok()
            else:
                print('!! Unknown command:', repr(cmd))

    def send_ok(self):
        print('-> Sending OK')
        self.connection.sendall('OK\r'.encode())


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
