import subprocess


def get_fan_status():
    try:
        output = subprocess.check_output(["nbfc", "status", "-a"]).decode().strip()
        return f"FAN STATUS\n\n{output}"
    except Exception as e:
        return f"Fan status error: {e}"


def get_current_speed():
    try:
        output = subprocess.check_output(["nbfc", "status"]).decode()

        for line in output.split("\n"):
            if "Requested Fan Speed" in line:
                return int(float(line.split(":")[1].strip()))

    except:
        pass

    return None


LAST_SPEED = get_current_speed()


def get_temp():
    output = subprocess.check_output(["nbfc", "status"]).decode()

    for line in output.split("\n"):
        if "Temperature" in line:
            return float(line.split(":")[1].strip())

    return 0


def set_speed(speed):
    global LAST_SPEED

    if LAST_SPEED == speed:
        return False

    subprocess.run(["nbfc", "set", "-s", str(speed)])

    LAST_SPEED = speed

    return True


def fan_logic():
    temp = get_temp()

    global LAST_SPEED
    current_speed = LAST_SPEED if LAST_SPEED is not None else 30

    levels = [
        (65, 100),
        (60, 70),
        (55, 60),
        (50, 50),
        (45, 40),
        (0, 30)
    ]

    # Find the target speed based purely on temperature
    target_up = 30
    for threshold, spd in levels:
        if temp >= threshold:
            target_up = spd
            break

    # Find the minimum speed allowed to drop to (incorporating a 5-degree hysteresis)
    HYSTERESIS = 5
    target_down = 30
    for threshold, spd in levels:
        if temp >= (threshold - HYSTERESIS):
            target_down = spd
            break

    # Decide speed based on current state and thresholds
    if current_speed < target_up:
        speed = target_up
    elif current_speed > target_down:
        speed = target_down
    else:
        speed = current_speed

    changed = set_speed(speed)

    return temp, speed, changed