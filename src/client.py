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

import os
import re
import sys
import zlib
import socket
import pickle
import ctypes
import shutil
from getpass import getuser
from pathlib import Path
from hashlib import sha256
from getpass import getpass


IP = input("IP: ")
PORT = int(input("Port: "))


def encrypt(string):
    return sha256(string.encode()).hexdigest()


class Client:
    header = 64
    padding = " " * header
    packet_size = 8192

    def __init__(self, ip, port):
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.conn.connect((ip, port))

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

        data = pickle.loads(zlib.decompress(data))
        if data["type"] == "force_quit":
            print("The server has sent a command to force quit.")
            print("This could be because the server is shutting down.")
            ctypes.pointer(ctypes.c_char.from_address(5))[0]

        return data


def print_help():
    print("cip - The C++ Package Installer")
    print("usage: cip [cmd] [cmd options] [-h --help] [-ls --list]\n")
    print("cip install <package name>                          Install the latest version of a package")
    print("cip install <package name>=<version>                Install the specified version of a package")
    print("cip uninstall <package name>                        Uninstall a package")
    print("cip upload <package name> <package path>            Upload your package for everyone to use")
    print("cip user <username> <-c --create> <-d --delete>     Get info about a user. Provide -c or --create flag for creating user\n")
    print("Additions:")
    print("    -h --help")
    print("         Print this menu")
    print("    -ls --list")
    print("         List all possible commands")


def install(conn, args):
    if args:
        if "=" in args[0]:
            package, version = filter(lambda x: x, args[0].split("="))
        else:
            package, version = args[0], "RECENT"

        conn.send({"type": "install", "package": package, "version": version})
        content = conn.recv()["reply"]
        if isinstance(content, str):
            print(content)
        else:
            print("Creating path...")
            if sys.platform == "windows":
                raise NotImplementedError("Currently windows is not supported for installation.")
                path = ""
            elif sys.platform == "darwin":
                raise NotImplementedError("Currently macos is not supported for installation.")
                path = ""
            else:
                if getuser() != "root":
                    raise PermissionError("You need to be root to install packages")
                path = "/usr/include/c++/9"

            print("Writing package...")

            with open(os.path.join(path, package), "wb") as f:
                f.write(content)

            print("Changing permissions...")

            if sys.platform == "windows":
                raise NotImplementedError("Currently windows is not supported for installation.")
            elif sys.platform == "darwin":
                raise NotImplementedError("Currently macos is not supported for installation.")
            else:
                os.system(f"chmod +x {os.path.join(path, package)}")

            print(f"Successfully installed {package}")


def uninstall(conn, args):
    if args:
        if "y" not in input(f"Are you sure you want to uninstall {args[0]}"):
            return
        print("Getting path...")
        if sys.platform == "windows":
            print(f"Package {args[0]} does not exist")
        elif sys.platform == "darwin":
            print(f"Package {args[0]} does not exist")
        else:
            print("Removing package...")
            if os.path.isfile(path := os.path.join("/usr/include/c++/9", args[0])):
                os.remove(path)
            elif os.path.isdir(path):
                shutil.rmtree(path)
            else:
                print(f"Package {args[0]} does not exist")
            print(f"Successfully removed {args[0]}")


def upload(conn, args):
    if args:
        pack_name = args[0]
        while re.search(re.compile(r"[a-zA-Z0-9-]+"), pack_name) is None:
            print(f"Invalid package name {pack_name}")
            pack_name = input("Package name: ")

        username = input("Username: ")
        conn.send({"type": "user", "method": "verify", "username": username})
        while conn.recv()["reply"] == "success":
            print(f"User {username} does not exist")
            username = input("Username: ")
            conn.send({"type": "user", "method": "verify", "username": username})

        conn.send({"type": "package", "package": pack_name, "user": username})
        while conn.recv()["reply"]:
            print(f"Package {pack_name} already exists")
            pack_name = input("Package Name: ")
            conn.send({"type": "package", "package": pack_name, "user": username})

        for i in range(3):
            password = encrypt(getpass(f"(Attempt {i+1}/3) Password: "))
            conn.send({"type": "auth", "username": username, "password": password})
            if conn.recv()["reply"]:
                break
            print("Incorrect password")
        else:
            print("3 attempts failed. Try again next time.")
            return

        version = input("Version: ")
        conn.send({"type": "version", "package": pack_name, "version": version})
        while conn.recv()["reply"]:
            print(f"Version {version} already exists")
            version = input("Version: ")
            conn.send({"type": "version", "package": pack_name, "version": version})


        print("Password authentication successful")
        print("Compressing data...")
        if os.path.isdir(args[1]):
            tmp = Path.home() / "Downloads/cip-tmp.zip"
            shutil.make_archive(os.path.splitext(tmp)[0], "zip", args[1])
            with open(tmp, "rb") as f:
                content = f.read()
            os.remove(tmp)
        elif os.path.isfile(args[1]):
            with open(args[1], "r") as f:
                content = f.read().encode()
        else:
            print("Not a valid path.")
            return
        print("Uploading package...")
        conn.send({"type": "upload", "user": username, "package": pack_name, "version": version, "content": content})
        if conn.recv()["reply"] == "success":
            print("Successfully uploaded")
        else:
            print("Upload failed... Try again next time")


def user(conn, args):
    if args:
        username = args[0]
        while not args[0].isalnum():
            print("Username is not alphanumeric")
            username = input("Username: ")
        if "-c" in args or "--create" in args:
            conn.send({"type": "user", "method": "verify", "username": username})
            while conn.recv()["reply"] != "success":
                print("User already exists. Try a different username.")
                username = input("Username: ")
                conn.send({"type": "user", "method": "verify", "username": username})
            pwd = encrypt(getpass("Password: "))
            if encrypt(getpass("Confirm password: ")) != pwd:
                print("Passwords didn't match")
                return
            print("Passwords match")
            print("Note: The rest of the fields are not required. Leave them blank at choice.")
            email = input("Email: ")
            website = input("Website: ")
            github = input("Github: ")
            description = input("Description: ")
            conn.send({"type": "user", "method": "create", "username": username, "password": pwd, "email": email, "website": website, "github": github, "description": description})
            if conn.recv()["reply"] == "success":
                print(f"Successfully created user {username}")
            else:
                print("Unfortunately the user could not be created.")

        elif "-d" in args or "--delete" in args:
            conn.send({"type": "user", "method": "verify", "username": username})
            while conn.recv()["reply"] == "success":
                print(f"User {username} does not exist")
                username = input("Username: ")
                conn.send({"type": "user", "method": "verify", "username": username})

            for i in range(3):
                password = encrypt(getpass(f"(Attempt {i+1}/3) Password: "))
                conn.send({"type": "auth", "username": username, "password": password})
                if conn.recv()["reply"]:
                    break
                print("Incorrect password")
            else:
                print("3 attempts failed. Try again next time.")
                return
            if "y" in input(f"Are you sure you want to delete {username}? [y/n] ").lower():
                print("Deleting user from server...")
                conn.send({"type": "user", "user": username, "method": "delete"})
                if conn.recv()["reply"] == "success":
                    print(f"{username} got deleted")
                else:
                    print(f"Deletion failed for {username}")

        else:
            conn.send({"type": "user", "method": "get", "user": username})
            print(conn.recv()["reply"])


def main():
    conn = Client(IP, PORT)
    funcs = {
        "install": install,
        "uninstall": uninstall,
        "upload": upload,
        "user": user,
    }

    if len(sys.argv) == 1:
        print_help()
    else:
        if "-h" in sys.argv or "--help" in sys.argv:
            print_help()
        elif "-ls" in sys.argv or "--list" in sys.argv:
            print("Possible commands:")
            for f in funcs.keys():
                print(f)
        else:
            if sys.argv[1] in funcs:
                funcs[sys.argv[1]](conn, sys.argv[2:])
            else:
                print(f"Unrecognized command {sys.argv[1]}.")

    conn.send({"type": "quit"})


main()
