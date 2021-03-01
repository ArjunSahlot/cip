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
import zlib
import socket
import pickle
import ctypes
import threading

IP = "192.168.1.10"
PORT = 5555


class Package:
    def __init__(self, name, version, content):
        self.name = name
        self.version = version
        self.content = content

    def get_detailed(self):
        return f"{self.name}={self.version}"

    def __str__(self):
        return self.name


class User:
    def __init__(self, username, password, website, github, description):
        self.username = username
        self.password = password
        self.website = website
        self.github = github
        self.description = description
        self.packages = []

    def auth(self, pwd):
        return pwd == self.password

    def __str__(self):
        string  = f"User: {self.username}\n"
        string += f"Website: {self.website}\n"
        string += f"Github: {self.github}\n"
        string += f"Description: {self.description}\n"
        if self.packages:
            packs = set(map(str, self.packages))
            string += "Packages:\n"
            for pack in packs[:-1]:
                string += str(pack) + "\n"
            string += str(self.packages[-1])
        else:
            string += "This user hasn't created any packages yet"
        return string


class Server:
    def __init__(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((IP, PORT))

        self.clients = []
        self.users = []
        self.active = True

    def get_user(self, username):
        for user in self.users:
            if user.username == username:
                return user
        return f"No user named {username}"

    def add_user(self, username, password, website, github, description):
        if isinstance(self.get_user(username), str):
            self.users.append(User(username, password, website, github, description))
            return True
        else:
            return False

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
                    self.send({"type": "reply", "reply": str(self.server.get_user(cmd["user"]))})

                elif cmd["method"] == "create":
                    if self.server.add_user(cmd["username"], cmd["password"], cmd["website"], cmd["github"], cmd["description"]):
                        self.send({"type": "reply", "reply": "success"})
                    else:
                        self.send({"type": "reply", "reply": "retry"})

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
        data = zlib.compress(pickle.dumps(obj))
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

        return pickle.loads(zlib.decompress(data))


def main():
    server = Server()
    server.start()


main()
