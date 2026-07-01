import subprocess


def get_fan_status():
    try:
        output = subprocess.check_output(["nbfc", "status", "-a"]).decode().strip()
        return f"FAN STATUS\n\n{output}"
    except Exception as e:
        return f"Fan status error: {e}"


def _parse_kv(line):
    """Parse a 'Key : Value' line from nbfc output."""
    if ":" not in line:
        return None, None
    key, _, value = line.partition(":")
    return key.strip().lower(), value.strip()


def get_nbfc_status():
    try:
        output = subprocess.check_output(
            ["nbfc", "status"], stderr=subprocess.STDOUT
        ).decode()
    except FileNotFoundError:
        print("Fan control error: 'nbfc' command not found")
        return {"temps": {}, "speeds": {}}
    except subprocess.CalledProcessError as e:
        print(f"Fan control error: nbfc exited with code {e.returncode}: {e.output}")
        return {"temps": {}, "speeds": {}}
    except Exception as e:
        print(f"Fan control error: {e}")
        return {"temps": {}, "speeds": {}}

    data = {"temps": {}, "speeds": {}}
    fan_index = -1

    for line in output.splitlines():
        key, value = _parse_kv(line)

        if key is None or value == "":
            continue

        # A new fan block starts with "fan display name"
        if "fan" in key and "name" in key:
            fan_index += 1

        elif fan_index >= 0 and key == "temperature":
            try:
                data["temps"][fan_index] = float(value)
            except ValueError:
                print(f"Fan control warning: could not parse temperature '{value}'")

        elif fan_index >= 0 and "current fan speed" in key:
            try:
                data["speeds"][fan_index] = int(float(value))
            except ValueError:
                print(f"Fan control warning: could not parse speed '{value}'")

    return data


def get_current_speeds():
    return get_nbfc_status()["speeds"]


def get_temps():
    return get_nbfc_status()["temps"]


LAST_SPEEDS = get_current_speeds()


def set_speed(speed, fan_index=0):
    global LAST_SPEEDS

    if LAST_SPEEDS.get(fan_index) == speed:
        return False

    subprocess.run(["nbfc", "set", "-f", str(fan_index), "-s", str(speed)])

    LAST_SPEEDS[fan_index] = speed

    return True


SHARED_HISTORY = []

def fan_logic():
    global LAST_SPEEDS, SHARED_HISTORY
    temps = get_temps()
    
    cpu_temp = temps.get(0, 0)
    gpu_temp = temps.get(1, 0)

    # 1. Emergency Thermal Protection
    if cpu_temp >= 90 or gpu_temp >= 85:
        set_speed(100, 0)
        set_speed(100, 1)
        return f"EMERGENCY ({cpu_temp}/{gpu_temp})", "MAX COOLING (100%)", True

    # 2. Shared Thermal Awareness (Nitro 5 shared heatpipes)
    shared_temp = max(cpu_temp, gpu_temp)
    
    # 3. Weighted Smoothing (Last 5 readings, latest has double weight)
    SHARED_HISTORY.append(shared_temp)
    if len(SHARED_HISTORY) > 5:
        SHARED_HISTORY.pop(0)
    
    if len(SHARED_HISTORY) > 1:
        eval_temp = (sum(SHARED_HISTORY[:-1]) + SHARED_HISTORY[-1] * 2) / (len(SHARED_HISTORY) + 1)
    else:
        eval_temp = SHARED_HISTORY[0]

    # 4. Unified Fan Curve for Server-style Operation
    levels = [
        (80, 100), (75, 85), (68, 70), (60, 55), (50, 40), (40, 30), (0, 25)
    ]

    # 5. Hysteresis and Speed Decision (Reduced oscillation)
    HYSTERESIS = 10
    current_speed = LAST_SPEEDS.get(0, 30) # Assuming fans are near-synchronized
    
    target_up = 25
    for threshold, spd in levels:
        if eval_temp >= threshold:
            target_up = spd
            break

    target_down = 25
    for threshold, spd in levels:
        if eval_temp >= (threshold - HYSTERESIS):
            target_down = spd
            break

    if current_speed < target_up:
        speed = target_up
    elif current_speed > target_down:
        speed = target_down
    else:
        speed = current_speed

    # 6. Synchronized Fan Control (Skips writes if speed is unchanged)
    changed_0 = set_speed(speed, 0)
    changed_1 = set_speed(speed, 1)
    any_changed = changed_0 or changed_1

    # Return summary for bot notification
    summary_temp = f"🌡 CPU: {cpu_temp}°C | GPU: {gpu_temp}°C | Smooth: {eval_temp:.1f}°C"
    summary_speed = f"⚙️ Speed: {speed}%"
    
    return summary_temp, summary_speed, any_changed