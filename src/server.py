#
#  Cip
#  C++ Package Manager.
#  Copyright Arjun Sahlot 2021
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

import time
import socket
import pickle
import ctypes
import threading

IP = input("IP: ")
PORT = input("Port: ")


class Server:
    def __init__(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((IP, PORT))

        self.clients = []
        self.active = True

    def start(self):
        print(f"[SERVER] Started on IP {IP} and PORT {PORT}")
        threading.Thread(target=self.cleanup).start()
        self.server.listen()

        while True:
            try:
                conn, addr = self.server.accept()
                client = Client(conn, addr, self)
                self.clients.append(client)
                threading.Thread(target=client.start).start()

            except KeyboardInterrupt:
                self.quit()

    def cleanup(self):
        while self.active:
            time.sleep(0.1)
            for i, c in enumerate(self.clients):
                if not c.active:
                    c.quit()
                    self.clients.pop(i)

    def quit(self):
        self.active = False
        self.server.close()
        for c in self.clients:
            c.quit()
        print("[SERVER] Stopping")
        ctypes.pointer(ctypes.c_char.from_address(5))[0]


class Client:
    header = 64
    padding = " " * header
    packet_size = 8192

    def __init__(self, conn, addr, server):
        self.conn = conn
        self.addr = addr
        self.server = server

        self.active = True
        self.last_move = 0
        self.alert("Connected")

    def alert(self, msg):
        if self.server.active:
            print(f"[{self.addr}] {msg}")

    def start(self):
        while True:
            cmd = self.recv()

            if not self.server.active:
                self.quit()
                return

            if cmd["type"] == "quit":
                self.quit()
                self.alert("Disconnected")
                return

            elif cmd["type"] == "user":
                if cmd["method"] == "get":
                    pass

                elif cmd["method"] == "create":
                    pass

            elif cmd["type"] == "install":
                pass

            elif cmd["type"] == "uninstall":
                pass

            elif cmd["type"] == "upload":
                pass

    def quit(self):
        self.conn.close()
        self.active = False

    def send(self, obj):
        data = pickle.dumps(obj)
        len_msg = (str(len(data)) + self.padding)[:self.header].encode()

        packets = []
        while data:
            curr_len = min(len(data), self.packet_size)
            packets.append(data[:curr_len])
            data = data[curr_len:]

        self.conn.send(len_msg)
        for packet in packets:
            self.conn.send(packet)

    def recv(self):
        len_msg = b""
        while len(len_msg) < self.header:
            len_msg += self.conn.recv(self.header-len(len_msg))

        length = int(len_msg)
        data = b""
        while len(data) < length:
            curr_len = min(self.packet_size, length-len(data))
            data += self.conn.recv(curr_len)

        return pickle.loads(data)
