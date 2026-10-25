#!/usr/bin/env python3
"""Exercise real TCP gameplay with fresh synthetic accounts; never deletes saves."""

import argparse
import re
import secrets
import socket
import string
import subprocess
import time
from pathlib import Path


ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


class Session:
    def __init__(self, host="127.0.0.1", port=4000):
        self.socket = socket.create_connection((host, port), timeout=10)
        self.socket.settimeout(0.2)
        self.buffer = ""
        self.telnet_state = "data"
        self.negotiation = 0
        self.password = ""
        self.command_number = 0
        self.prompt_prefix = "SMOKE" + secrets.token_hex(3)

    def decode(self, data):
        text = bytearray()
        for byte in data:
            if self.telnet_state == "data":
                if byte == 255:
                    self.telnet_state = "iac"
                else:
                    text.append(byte)
            elif self.telnet_state == "iac":
                if byte == 255:
                    text.append(byte)
                    self.telnet_state = "data"
                elif byte in (251, 252, 253, 254):
                    self.negotiation = byte
                    self.telnet_state = "option"
                elif byte == 250:
                    self.telnet_state = "sub"
                else:
                    self.telnet_state = "data"
            elif self.telnet_state == "option":
                if self.negotiation == 251:
                    # Accept remote password echo control; refuse other options.
                    self.socket.sendall(bytes((255, 253 if byte == 1 else 254, byte)))
                elif self.negotiation == 253:
                    self.socket.sendall(bytes((255, 252, byte)))
                self.telnet_state = "data"
            elif self.telnet_state == "sub":
                if byte == 255:
                    self.telnet_state = "sub_iac"
            elif self.telnet_state == "sub_iac":
                self.telnet_state = "data" if byte == 240 else "sub"
        return text.decode("cp1251")

    def expect(self, needle, timeout=15):
        deadline = time.monotonic() + timeout
        while needle not in ANSI.sub("", self.buffer):
            if time.monotonic() > deadline:
                tail = self.buffer[-1500:]
                if self.password:
                    tail = tail.replace(self.password, "[redacted]")
                raise AssertionError(f"Expected {needle!r}; received {tail!r}")
            try:
                data = self.socket.recv(65536)
            except socket.timeout:
                continue
            if not data:
                raise AssertionError(f"Server disconnected while waiting for {needle!r}")
            self.buffer += self.decode(data)
        result = self.buffer
        self.buffer = ""
        return result

    def send(self, text):
        self.socket.sendall(text.encode("cp1251").replace(b"\xff", b"\xff\xff") + b"\r\n")

    def step(self, text, needle):
        self.send(text)
        return self.expect(needle)

    def create(self, name, password):
        self.password = password
        self.expect("Select your codepage:")
        # An option split across packets must not become part of the next line.
        self.socket.sendall(b"\xff\xfb")
        time.sleep(0.3)
        self.socket.sendall(b"\x1f")
        self.step("2", "странник:")
        self.step(name, "(Y/N)?")
        self.step("y", "пароль")
        self.step(password, "еще раз:")
        self.step(password, "расы")
        self.step("human", "пола")
        self.step("m", "класс")
        self.step("warrior", "(G/N/E)?")
        self.step("n", "Вручную (Y/N)?")
        self.step("n", "Твой выбор?")
        self.step("sword", "[Нажми ENTER для продолжения]")
        self.step("", "Добро пожаловать в Forgotten Dungeon")
        self.prepare()

    def login(self, name, password):
        self.password = password
        self.expect("Select your codepage:")
        self.step("2", "странник:")
        self.step(name, "Пароль:")
        self.step(password, "[Нажми ENTER для продолжения]")
        self.step("", "Добро пожаловать в Forgotten Dungeon")
        self.prepare()

    def prepare(self):
        self.command("scroll 0")

    def command(self, command):
        # A unique prompt confirms this command, not an asynchronous chat, completed.
        self.command_number += 1
        prompt = f"{self.prompt_prefix}{self.command_number}>"
        self.send(command)
        self.send("prompt " + prompt)
        return self.expect(prompt)

    def quit(self):
        self.step("quit", "Все хорошее рано или поздно заканчивается")
        self.socket.close()


def fresh_name():
    return "Smoke" + "".join(secrets.choice(string.ascii_lowercase) for _ in range(6))


def smoke(restart=False):
    password = secrets.token_hex(12)
    names = [fresh_name(), fresh_name()]
    sessions = [Session(), Session()]
    try:
        for session, name in zip(sessions, names):
            session.create(name, password)
            print("Created synthetic character: " + name, flush=True)
        first, second = sessions
        assert "Вход в Школу" in ANSI.sub("", first.command("look"))
        assert names[0] in second.command("who") and names[1] in first.command("who")
        assert "Вход в Школу" not in ANSI.sub("", first.command("north"))
        assert "Вход в Школу" in ANSI.sub("", first.command("south"))
        if "\x1b[" not in first.command("look"):
            first.command("colour")
        assert "\x1b[" in first.command("look"), "ANSI colors absent"
        phrase = "Привет, друзья! я здесь"
        first.command("say " + phrase)
        assert phrase in ANSI.sub("", second.expect(phrase)), "Cyrillic did not round-trip"
        second.command("say Ответ получен")
        first.expect("Ответ получен")
        areas = ANSI.sub("", first.command("areas"))
        assert "KPI" in areas, "KPI not loaded into runtime area list"
        assert "Shadows" in areas, "Shadows not loaded into runtime area list"
        for direction in ["down"] + ["south"] * 8 + ["east", "south", "up", "east", "north", "north"]:
            first.command(direction)
        assert "Первый корпус КПИ" in ANSI.sub("", first.command("look")), "Cannot walk to KPI"
        marker = "LocalPersistence" + secrets.token_hex(3)
        first.command("title " + marker)
        assert "Хранители Знаний" in first.command("save")
        first.quit()
        second.quit()
        if restart:
            subprocess.run(["docker", "compose", "restart", "game"], cwd=Path(__file__).resolve().parents[1], check=True)
            deadline = time.monotonic() + 60
            while True:
                try:
                    first = Session()
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(0.5)
        else:
            first = Session()
        sessions.append(first)
        first.login(names[0], password)
        score = first.command("score")
        assert marker in score, "Saved character title did not survive reload: " + ANSI.sub("", score)
        first.quit()
        print("PASS: fresh characters, login, movement, concurrent chat, Cyrillic, ANSI, KPI/Shadows loaded, save/reload" + (", container restart" if restart else ""))
        print("Synthetic characters retained: " + ", ".join(names))
    finally:
        for session in sessions:
            session.socket.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restart", action="store_true", help="also restart the game container to verify persistence (disconnects players)")
    smoke(parser.parse_args().restart)
