"""Wall-E SPIKE Prime controller with shoulder-touch wheel enable toggle.

Ports: A=color sensor, B=ultrasonic sensor, C=head, D=left wheel,
E=shoulder touch, F=right wheel.
"""

from pybricks.hubs import PrimeHub
from pybricks.parameters import Port
from pybricks.pupdevices import ColorSensor, ForceSensor, Motor, UltrasonicSensor
from pybricks.tools import StopWatch, wait
from usys import stdin
from uselect import POLLIN, poll

# The drive motors are mirrored on the assembled chassis.
LEFT_SIGN = 1
RIGHT_SIGN = -1

MAX_DRIVE = 55
HEAD_LIMIT = 60
# Motor 20T gear drives the 56T head gear: the head turns 20/56 as far as
# the motor, and one external gear mesh reverses the direction.
HEAD_MOTOR_TEETH = 20
HEAD_HEAD_TEETH = 56
HEAD_SIGN = -1
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

head.reset_angle(0)

keyboard = poll()
keyboard.register(stdin, POLLIN)
clock = StopWatch()
last_command_ms = 0
last_telemetry_ms = -TELEMETRY_INTERVAL_MS
line = ""
wheels_enabled = True
shoulder_was_pressed = False


def send(text):
    # BLE stdout is non-blocking. Do not crash if its buffer is temporarily full.
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
    if not wheels_enabled:
        send("SAFE wheels-disabled")
        return

    if distance_eye.distance() < OBSTACLE_MM and (left_percent > 0 or right_percent > 0):
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
            motor_target = HEAD_SIGN * target * HEAD_HEAD_TEETH // HEAD_MOTOR_TEETH
            head.track_target(motor_target)
            send("ACK HEAD " + str(target))
        except ValueError:
            send("ERR invalid-head")
        return

    send("ERR " + command)


send("READY")

while True:
    now = clock.time()

    while keyboard.poll(0):
        try:
            character = stdin.read(1)
        except OSError:
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

    # Rising-edge detection: a held press changes state only once.
    shoulder_pressed = shoulder.touched()
    if shoulder_pressed and not shoulder_was_pressed:
        wheels_enabled = not wheels_enabled
        stop_drive()
        send("WHEELS " + ("ON" if wheels_enabled else "OFF"))
    shoulder_was_pressed = shoulder_pressed

    if now - last_command_ms > COMMAND_TIMEOUT_MS:
        stop_drive()

    if now - last_telemetry_ms >= TELEMETRY_INTERVAL_MS:
        last_telemetry_ms = now
        send("TEL d={} r={} touch={} h={} wheels={}".format(
            distance_eye.distance(),
            color_eye.reflection(),
            int(shoulder_pressed),
            HEAD_SIGN * head.angle() * HEAD_MOTOR_TEETH // HEAD_HEAD_TEETH,
            int(wheels_enabled),
        ))

    wait(10)
