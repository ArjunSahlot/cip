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


class Version:
    def __init__(self, owner, version, content):
        self.owner = owner
        self.version = version
        self.content = content

    def __eq__(self, version):
        return self.version == version

    def __ne__(self, version):
        return self.version != version

    def get_bytes(self):
        return self.content


class Package:
    def __init__(self, name):
        self.name = name
        self.versions = []

    def add_version(self, version, content):
        self.versions.append(Version(self, version, content))

    def get_version(self, version):
        if version == "RECENT":
            return max(self.versions, lambda x: int(x.name.replace(".", "")))
        else:
            for v in self.versions:
                if v == version:
                    return v

    def __eq__(self, pack):
        return self.name == pack

    def __str__(self):
        return f"{self.name} ({len(self.versions)} versions)"


class User:
    def __init__(self, username, password, email, website, github, description):
        self.username = username
        self.password = password
        self.email = email
        self.website = website
        self.github = github
        self.description = description
        self.packages = []

    def add_package(self, package, version, content):
        p = Package(package)
        p.add_version(version, content)
        self.packages.append(p)

    def get_version(self, package, version):
        for pack in self.packages:
            if pack == package:
                if ver := pack.get_version(version):
                    return ver
                else:
                    return f"Package {package} has no version {version}"

    def auth(self, pwd):
        return pwd == self.password

    def __str__(self):
        string  = f"User: {self.username}\n"
        string += f"Email: {self.email}\n"
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

    def add_package(self, user, package, version, content):
        self.get_user(user).add_package(package, version, content)

    def auth(self, username, password):
        return self.get_user(username).auth(password)

    def get_version(self, package, version):
        for user in self.users:
            if pack := user.get_version(package, version):
                return pack

    def check_user(self, username):
        return isinstance(self.get_user(username), str)

    def get_user(self, username):
        for user in self.users:
            if user.username == username:
                return user
        return f"No user named {username}"

    def add_user(self, username, password, email, website, github, description):
        self.users.append(User(username, password, email, website, github, description))

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
                    self.server.add_user(cmd["username"], cmd["password"], cmd["email"], cmd["website"], cmd["github"], cmd["description"])
                    self.send({"type": "reply", "reply": "success"})

                elif cmd["method"] == "verify":
                    if self.server.check_user(cmd["username"]):
                        self.send({"type": "reply", "reply": "success"})
                    else:
                        self.send({"type": "reply", "reply": "exists"})

            elif cmd["type"] == "install":
                version = self.server.get_version(cmd["package"], cmd["version"])
                if isinstance(version, Version):
                    self.send({"type": "reply", "reply": version.content})
                else:
                    self.send({"type": "reply", "reply": version})

            elif cmd["type"] == "upload":
                self.server.add_package(cmd["user"], cmd["package"], cmd["version"], cmd["content"])

            elif cmd["type"] == "auth":
                self.server.auth(cmd["username"], cmd["password"])

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
