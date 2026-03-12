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

    if temp < 45:
        speed = 30
    elif temp < 50:
        speed = 40
    elif temp < 55:
        speed = 50
    elif temp < 60:
        speed = 60
    elif temp < 65:
        speed = 70
    else:
        speed = 100

    changed = set_speed(speed)

    return temp, speed, changed