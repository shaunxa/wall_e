"""Wall-E-style SPIKE Prime companion controller.

Port map: A=color eye, B=distance eye, C=head, D=left wheel,
E=shoulder touch, F=right wheel.
"""

from pybricks.hubs import PrimeHub
from pybricks.parameters import Port
from pybricks.pupdevices import ColorSensor, ForceSensor, Motor, UltrasonicSensor
from pybricks.tools import StopWatch, wait
from usys import stdin
from uselect import POLLIN, poll

# Set either value to -1 only if that wheel turns in the wrong direction.
LEFT_SIGN = 1
# The two wheel motors are mirrored on the chassis. Invert Port F so logical
# left/right wheel commands produce real differential steering.
RIGHT_SIGN = -1

MAX_DRIVE = 55
HEAD_LIMIT = 60
OBSTACLE_MM = 180
COMMAND_TIMEOUT_MS = 2000
TELEMETRY_INTERVAL_MS = 500

hub = PrimeHub()
left = Motor(Port.D)
right = Motor(Port.F)
head = Motor(Port.C)
color_eye = ColorSensor(Port.A)
distance_eye = UltrasonicSensor(Port.B)
shoulder = ForceSensor(Port.E)

# Start with the head looking forward.
head.reset_angle(0)

keyboard = poll()
# The default includes POLLOUT, which is always ready and prevents us from
# seeing real Bluetooth stdin bytes. Register only readable input events.
keyboard.register(stdin, POLLIN)
clock = StopWatch()
last_command_ms = 0
last_telemetry_ms = -TELEMETRY_INTERVAL_MS
line = ""


def send(text):
    # print() reaches the Pybricks BLE stdout channel and adds a newline.
    # str.encode() is not implemented on this MicroPython build.
    # BLE stdout is non-blocking. If its tiny buffer is full, dropping a
    # telemetry/ACK line is safer than stopping the physical robot program.
    try:
        print(text)
    except OSError:
        pass


def clamp(value, low, high):
    return max(low, min(high, value))


def stop_drive(reason=None):
    left.stop()
    right.stop()
    if reason:
        send("SAFE " + reason)


def drive(left_percent, right_percent):
    distance = distance_eye.distance()
    if distance < OBSTACLE_MM and (left_percent > 0 or right_percent > 0):
        stop_drive("obstacle")
        return
    left.dc(LEFT_SIGN * clamp(left_percent, -MAX_DRIVE, MAX_DRIVE))
    right.dc(RIGHT_SIGN * clamp(right_percent, -MAX_DRIVE, MAX_DRIVE))


def handle_command(command):
    global last_command_ms
    last_command_ms = clock.time()
    parts = command.split()
    if not parts:
        return

    if parts[0] == "STOP":
        stop_drive()
        send("ACK STOP")
        return

    if parts[0] == "PING":
        send("ACK PING")
        return

    if parts[0] == "DRV" and len(parts) == 3:
        try:
            drive(int(parts[1]), int(parts[2]))
            send("ACK " + command)
        except ValueError:
            send("ERR invalid-drive")
        return

    if parts[0] == "HEAD" and len(parts) == 2:
        try:
            target = clamp(int(parts[1]), -HEAD_LIMIT, HEAD_LIMIT)
            head.track_target(target)
            send("ACK HEAD " + str(target))
        except ValueError:
            send("ERR invalid-head")
        return

    send("ERR " + command)


send("READY")

while True:
    now = clock.time()

    # Reading text one character at a time handles a command split across BLE
    # packets. stdin.read() already returns a string on Pybricks.
    while keyboard.poll(0):
        try:
            character = stdin.read(1)
        except OSError:
            # poll() can report ready just as the BLE buffer becomes empty.
            break
        if not character:
            break
        if character == "\n":
            handle_command(line.strip())
            line = ""
        elif len(line) < 32:
            line += character
        else:
            line = ""
            send("ERR line-too-long")

    if shoulder.touched():
        stop_drive("shoulder")

    if now - last_command_ms > COMMAND_TIMEOUT_MS:
        stop_drive()

    if now - last_telemetry_ms >= TELEMETRY_INTERVAL_MS:
        last_telemetry_ms = now
        send("TEL d={} r={} touch={} h={}".format(
            distance_eye.distance(),
            color_eye.reflection(),
            int(shoulder.touched()),
            head.angle(),
        ))

    wait(10)
