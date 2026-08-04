"""Wall-E controller: touch wheel toggle, idle head wiggle, and LED eye blink.

Ports: A=color eye, B=ultrasonic eye, C=head, D=left wheel,
E=shoulder touch, F=right wheel.
"""

from pybricks.hubs import PrimeHub
from pybricks.parameters import Port
from pybricks.pupdevices import ColorSensor, ForceSensor, Motor, UltrasonicSensor
from pybricks.tools import StopWatch, wait
from usys import stdin
from uselect import POLLIN, poll
from urandom import getrandbits

LEFT_SIGN = 1
RIGHT_SIGN = -1
MAX_DRIVE = 55
HEAD_LIMIT = 60
HEAD_MOTOR_TEETH = 20
HEAD_HEAD_TEETH = 56
HEAD_SIGN = -1
OBSTACLE_MM = 180
COMMAND_TIMEOUT_MS = 2000
TELEMETRY_INTERVAL_MS = 500

# Idle personality settings. The head sweep is relative to its last commanded
# centre position, so a manual head command still becomes its natural resting pose.
IDLE_START_MS = 5000
IDLE_LEFT_OFFSET = -20
IDLE_RIGHT_OFFSET = 20
IDLE_LEFT_TIME_MS = 3000
IDLE_RIGHT_TIME_MS = 5000
IDLE_RETURN_TIME_MS = 3000
IDLE_BLINK_INTERVAL_MS = 3000
IDLE_BLINK_MS = 140

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
last_motion_ms = 0
last_blink_ms = 0
blink_until_ms = 0
line = ""
wheels_enabled = True
wheels_moving = False
shoulder_was_pressed = False
head_home_angle = 0
eyes_are_on = False
eye_mood = "awake"
idle_active = False
idle_phase = 0
idle_phase_started_ms = 0
idle_phase_duration_ms = 0


def send(text):
    try:
        print(text)
    except OSError:
        pass


def clamp(value, low, high):
    return max(low, min(high, value))


def set_eyes(on, mood="awake"):
    """Use the Ultrasonic Sensor's 4 LEDs for happy/sad eye patterns."""
    global eyes_are_on, eye_mood
    if on == eyes_are_on and (not on or mood == eye_mood):
        return
    try:
        if on:
            color_eye.lights.on(30)
            if mood == "happy":
                # Outer lights on: an upbeat, wide-eyed expression.
                distance_eye.lights.on((100, 0, 0, 100))
            elif mood == "sad":
                # Inner lights on: a softer, worried expression.
                distance_eye.lights.on((0, 100, 100, 0))
            else:
                distance_eye.lights.on(30)
        else:
            color_eye.lights.off()
            distance_eye.lights.off()
        eyes_are_on = on
        if on:
            eye_mood = mood
    except OSError:
        pass


def set_head_target(logical_angle):
    motor_angle = HEAD_SIGN * logical_angle * HEAD_HEAD_TEETH // HEAD_MOTOR_TEETH
    head.track_target(motor_angle)


def run_head_target(logical_angle, duration_ms, logical_distance):
    """Move the geared head slowly enough to cover a known sweep duration."""
    motor_angle = HEAD_SIGN * logical_angle * HEAD_HEAD_TEETH // HEAD_MOTOR_TEETH
    motor_speed = max(10, logical_distance * HEAD_HEAD_TEETH * 1000 // (HEAD_MOTOR_TEETH * duration_ms))
    head.run_target(motor_speed, motor_angle, wait=False)


def stop_drive(reason=None):
    global wheels_moving, last_motion_ms
    left.stop()
    right.stop()
    if wheels_moving:
        wheels_moving = False
        last_motion_ms = clock.time()
    if reason:
        send("SAFE " + reason)


def drive(left_percent, right_percent):
    global wheels_moving, last_motion_ms
    if not wheels_enabled:
        send("SAFE wheels-disabled")
        return
    if distance_eye.distance() < OBSTACLE_MM and (left_percent > 0 or right_percent > 0):
        stop_drive("obstacle")
        return
    left.dc(LEFT_SIGN * clamp(left_percent, -MAX_DRIVE, MAX_DRIVE))
    right.dc(RIGHT_SIGN * clamp(right_percent, -MAX_DRIVE, MAX_DRIVE))
    wheels_moving = left_percent != 0 or right_percent != 0
    if wheels_moving:
        last_motion_ms = clock.time()


def handle_command(command):
    global last_command_ms, head_home_angle
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
            head_home_angle = clamp(int(parts[1]), -HEAD_LIMIT, HEAD_LIMIT)
            set_head_target(head_home_angle)
            send("ACK HEAD " + str(head_home_angle))
        except ValueError:
            send("ERR invalid-head")
        return
    send("ERR " + command)


def animate_idle(now):
    """After five idle seconds, slowly sweep the head and blink random moods."""
    global blink_until_ms, last_blink_ms, idle_active
    global idle_phase, idle_phase_started_ms, idle_phase_duration_ms
    if wheels_moving:
        idle_active = False
        idle_phase = 0
        set_eyes(True, "awake")
        return
    if now - last_motion_ms < IDLE_START_MS:
        idle_active = False
        idle_phase = 0
        set_eyes(True, "awake")
        return

    if not idle_active:
        idle_active = True
        idle_phase = 0
        idle_phase_started_ms = now
        idle_phase_duration_ms = IDLE_LEFT_TIME_MS
        run_head_target(
            clamp(head_home_angle + IDLE_LEFT_OFFSET, -HEAD_LIMIT, HEAD_LIMIT),
            IDLE_LEFT_TIME_MS,
            abs(IDLE_LEFT_OFFSET),
        )
    elif now - idle_phase_started_ms >= idle_phase_duration_ms:
        idle_phase = (idle_phase + 1) % 3
        idle_phase_started_ms = now
        if idle_phase == 1:
            idle_phase_duration_ms = IDLE_RIGHT_TIME_MS
            run_head_target(
                clamp(head_home_angle + IDLE_RIGHT_OFFSET, -HEAD_LIMIT, HEAD_LIMIT),
                IDLE_RIGHT_TIME_MS,
                abs(IDLE_RIGHT_OFFSET - IDLE_LEFT_OFFSET),
            )
        elif idle_phase == 2:
            idle_phase_duration_ms = IDLE_RETURN_TIME_MS
            run_head_target(head_home_angle, IDLE_RETURN_TIME_MS, abs(IDLE_RIGHT_OFFSET))
        else:
            idle_phase_duration_ms = IDLE_LEFT_TIME_MS
            run_head_target(
                clamp(head_home_angle + IDLE_LEFT_OFFSET, -HEAD_LIMIT, HEAD_LIMIT),
                IDLE_LEFT_TIME_MS,
                abs(IDLE_LEFT_OFFSET),
            )

    if blink_until_ms:
        if now >= blink_until_ms:
            set_eyes(True, "happy" if getrandbits(1) else "sad")
            blink_until_ms = 0
    elif now - last_blink_ms >= IDLE_BLINK_INTERVAL_MS:
        set_eyes(False)
        blink_until_ms = now + IDLE_BLINK_MS
        last_blink_ms = now

set_eyes(True, "awake")
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

    shoulder_pressed = shoulder.touched()
    if shoulder_pressed and not shoulder_was_pressed:
        wheels_enabled = not wheels_enabled
        stop_drive()
        send("WHEELS " + ("ON" if wheels_enabled else "OFF"))
    shoulder_was_pressed = shoulder_pressed

    if now - last_command_ms > COMMAND_TIMEOUT_MS:
        stop_drive()

    animate_idle(now)

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
