import psutil
import subprocess

# Store the last known alert states to prevent spam
ALERT_STATE = {
    "cpu": False,
    "ram": False,
    "disk": False,
    "gpu": False
}

def get_gpu_usage():
    try:
        # Check if nvidia-smi is available and grab the gpu utilization
        output = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
            stderr=subprocess.STDOUT
        ).decode().strip()
        usages = [int(x.strip()) for x in output.split('\n') if x.strip().isdigit()]
        if usages:
            return max(usages)
    except Exception:
        pass
    
    return None

def check_system_health():
    global ALERT_STATE
    
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent
    gpu = get_gpu_usage()
    
    threshold = 90
    
    current_state = {
        "cpu": cpu > threshold,
        "ram": ram > threshold,
        "disk": disk > threshold,
        "gpu": gpu is not None and gpu > threshold
    }
    
    alerts = []
    
    # Check for new alerts
    if current_state["cpu"] and not ALERT_STATE["cpu"]:
        alerts.append(f"⚠️ High CPU Usage: {cpu}%")
    if current_state["ram"] and not ALERT_STATE["ram"]:
        alerts.append(f"⚠️ High RAM Usage: {ram}%")
    if current_state["disk"] and not ALERT_STATE["disk"]:
        alerts.append(f"⚠️ High Disk Usage: {disk}%")
    if current_state["gpu"] and not ALERT_STATE["gpu"]:
        alerts.append(f"⚠️ High GPU Usage: {gpu}%")
        
    resolved = []
    
    # Check for resolved alerts
    if not current_state["cpu"] and ALERT_STATE["cpu"]:
        resolved.append(f"✅ CPU Usage normalized: {cpu}%")
    if not current_state["ram"] and ALERT_STATE["ram"]:
        resolved.append(f"✅ RAM Usage normalized: {ram}%")
    if not current_state["disk"] and ALERT_STATE["disk"]:
        resolved.append(f"✅ Disk Usage normalized: {disk}%")
    if not current_state["gpu"] and ALERT_STATE["gpu"]:
        resolved.append(f"✅ GPU Usage normalized: {gpu}%")

    # Update state
    ALERT_STATE.update(current_state)
    
    messages = []
    if alerts:
        messages.append("🚨 *SYSTEM WARNING* 🚨\n\n" + "\n".join(alerts))
    if resolved:
        messages.append("✅ *SYSTEM RESOLVED* ✅\n\n" + "\n".join(resolved))
        
    if messages:
        return "\n\n".join(messages)
        
    return None
