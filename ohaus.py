#!/usr/bin/env python3


import questionary
import serial
import time
import glob
import json
import signal

from os import path, remove
from sys import platform
from datetime import datetime

class UI():
    """
    UI is a class representing the user interface
    """
    def __init__(self, interface):
        self.interface = interface
        if not path.exists("settings.json"):
            self.wizard()
        else:
            if questionary.confirm("Would you like to load previous settings?").ask():
                self.load_settings()
                if not questionary.confirm("Are these settings correct?").ask():
                    self.wizard()
            else:
                self.wizard()
        self.check_logfile()

    def save_settings(self):
        settings = {
                "port": self.interface.port,
                "interval": self.interface.human_interval,
                "filename": self.interface.filename,
        }
        with open("settings.json", "w") as f:
            f.write(json.dumps(settings))

    def check_logfile(self):
        if path.exists(self.interface.filename):
            if questionary.confirm(f"{self.interface.filename} exists, remove?").ask():
                remove(self.interface.filename)
            else:
                print("Aborting")
                exit()

    def load_settings(self):
        with open("settings.json", "r") as f:
            settings = json.loads(f.read())
            self.interface.port = settings["port"]
            self.interface.set_interval(settings["interval"])
            self.interface.filename = settings["filename"]
        print("Settings loaded")
        print(f"Port: {self.interface.port}")
        print(f"Interval: {self.interface.human_interval}")
        print(f"filename: {self.interface.filename}")

    def wizard(self):
        ports = self.interface.scan_serial()
        if len(ports) < 1:
            raise RuntimeError("No available ports found, make sure everyting is connected and you have permissions to use the port")
        port = questionary.select("Please select your serial port", choices=ports).ask()
        interval = questionary.text("Please enter the required interval. ex: 30m to schedule every 30 minutes or 4s to schedule every 4 seconds (h / m / s)").ask()
        filename = questionary.text("Please enter the filename to save the log").ask()

        self.interface.port = port
        self.interface.interval = interval
        self.interface.set_interval(interval)
        self.interface.filename = filename
        self.save_settings()


class Interface():
    """
    Interface is a class representing the interface to communicate to the ohaus scale
    """
    def __init__(self):
        self.detect_os()
        self.filename = None
        self.interval = None
        self.human_interval = None
        self.port = None

    def detect_os(self):
        self.platform = platform
        self.scan_serial()

    def scan_serial(self):
        if self.platform.startswith('win'):
            ports = ['COM%s' % (i + 1) for i in range(256)]
        elif self.platform.startswith('linux') or self.platform.startswith('cygwin'):
            # this excludes your current terminal "/dev/tty"
            ports = glob.glob('/dev/tty[A-Za-z]*')
        elif self.platform.startswith('darwin'):
            ports = glob.glob('/dev/tty.*')
        else:
            raise EnvironmentError('Unsupported platform')

        self.available_ports = []
        for port in ports:
            try:
                s = serial.Serial(port)
                s.close()
                self.available_ports.append(port)
            except (OSError, serial.SerialException):
                pass
        return self.available_ports

    def set_interval(self, interval):
        self.human_interval = interval
        unit = interval[-1].lower()
        interval = int(interval[:-1])
        if unit == "m":
            interval = interval * 60
        elif unit == "h":
            interval = interval * 60 * 60
        self.interval = interval

    def setup_port(self):
        self.scale = serial.Serial(
            baudrate = 9600,
            parity   = serial.PARITY_NONE,
            bytesize = 8,
            stopbits = 1,
            timeout  = 1,
            xonxoff  = False,
            port     = self.port,
        )
        try:
            self.scale.open()
        except serial.SerialException:
            pass
        print("Initialising Scale")
        self.scale.reset_input_buffer()
        self.scale.write(b'POH\r\n')
        time.sleep(.2)
        print("Initialised Scale")

    def get_weight(self):
        self.scale.write(b'P\r\n')
        self.scale.reset_input_buffer()
        while True:
            if self.scale.in_waiting > 3:
                weight = self.scale.readline()
                return f"{self.now()} - {self.decode_bytes(weight)}"
                break
            else:
                time.sleep(.1)

    def decode_bytes(self, s):
        return s.decode("utf-8").strip()

    def now(self):
        return datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    def write(self, line):
        with open(self.filename, "a") as f:
            f.write(f"{line}\r\n")

    def execute(self):
        self.setup_port()
        print(f"Weighing every {self.human_interval}")
        while True:
            weight = self.get_weight()
            print(weight)
            self.write(weight)
            time.sleep(self.interval)

def main():
    interface = Interface()
    ui = UI(interface)
    interface.execute()


if __name__ == '__main__':
    main()
