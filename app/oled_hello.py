import os, socket, subprocess, shlex, shutil, time, glob, traceback
from PIL import ImageFont
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import sh1106

# ==== Display / runtime config ====
ADDR = 0x3C
WIDTH, HEIGHT = 128, 64
UPDATE_SECS = float(os.getenv("UPDATE_SECS", "2"))
MOUNT = os.getenv("MOUNT", "/")
IFACE = os.getenv("IFACE")
HOST_IP = os.getenv("HOST_IP")
FONT_PATH = os.getenv("FONT_PATH")

# ==== Helpers ====
def get_ip():
    try:
        if HOST_IP:
            return HOST_IP.strip()
        if IFACE:
            out = subprocess.check_output(
                f"ip -o -4 addr show dev {shlex.quote(IFACE)} scope global",
                shell=True, text=True
            ).strip()
            for line in out.splitlines():
                for p in line.split():
                    if "/" in p and p.count(".") == 3:
                        return p.split("/")[0]
        out = subprocess.check_output("ip route get 1.1.1.1", shell=True, text=True)
        toks = out.split()
        for i, t in enumerate(toks):
            if t == "src" and i + 1 < len(toks):
                return toks[i + 1]
        # fallback: socket trick
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "0.0.0.0"

def cpu_usage_percent():
    def read_stat():
        with open("/proc/stat") as f:
            for line in f:
                if line.startswith("cpu "):
                    parts = [int(x) for x in line.split()[1:]]
                    idle = parts[3] + parts[4]  # idle + iowait
                    total = sum(parts)
                    return idle, total
        return 0, 0
    idle1, total1 = read_stat()
    time.sleep(0.25)
    idle2, total2 = read_stat()
    d_idle, d_total = idle2 - idle1, total2 - total1
    return round(100.0 * (1.0 - (d_idle / d_total)), 1) if d_total > 0 else 0.0

def read_temp_c():
    paths = [
        "/sys/class/thermal/thermal_zone0/temp",
        "/sys/class/hwmon/hwmon0/temp1_input",
        "/sys/class/hwmon/hwmon1/temp1_input",
    ] + glob.glob("/sys/class/hwmon/hwmon*/temp*_input")
    for p in paths:
        try:
            v = float(open(p).read().strip())
            return round(v/1000.0 if v > 1000 else v, 1)
        except Exception:
            pass
    try:
        out = subprocess.check_output("vcgencmd measure_temp", shell=True, text=True)
        return round(float(out.strip().replace("temp=","").replace("'C","")), 1)
    except Exception:
        return None

def mem_usage_percent():
    mem = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, v = line.split(":")
            mem[k.strip()] = int(v.strip().split()[0])  # kB
    total = mem.get("MemTotal", 0); avail = mem.get("MemAvailable", 0)
    return round(100.0 * (total - avail) / total, 1) if total else 0.0

def disk_usage_percent(path):
    try:
        du = shutil.disk_usage(path)
        return round((du.used / du.total) * 100.0, 1) if du.total else 0.0
    except Exception:
        return 0.0

def fit(draw, text, max_w, font):
    """Trim text by pixel width with ellipsis if needed."""
    if draw.textlength(text, font=font) <= max_w:
        return text
    alt = text
    while alt and draw.textlength(alt + "…", font=font) > max_w:
        alt = alt[:-1]
    return (alt + "…") if alt else text[:1]

def open_display():
    while True:
        try:
            serial = i2c(port=1, address=ADDR)
            dev = sh1106(serial, width=WIDTH, height=HEIGHT, persist=True)
            dev.contrast(255)
            return dev
        except Exception as e:
            print("I2C/OLED init failed, retrying in 5s:", e)
            time.sleep(5)

# ==== Init ====
font = ImageFont.load_default() if not FONT_PATH else ImageFont.truetype(FONT_PATH, 12)
device = open_display()

# ==== Main loop ====
while True:
    try:
        ip   = get_ip()
        cpu  = cpu_usage_percent()
        temp = read_temp_c()
        ram  = mem_usage_percent()
        disk = disk_usage_percent(MOUNT)

        line1 = f"IP: {ip}"
        base2 = f"CPU:{cpu:.1f}%"
        if temp is not None:
            line2_precise = f"{base2}  T:{temp:.1f}°C"
            line2_ints    = f"CPU:{int(round(cpu))}%  T:{int(round(temp))}°C"
            line2 = line2_precise
        else:
            line2_precise = base2
            line2_ints    = base2
            line2 = base2

        line3 = f"RAM:{ram:.1f}%"
        line4 = f"DISK({MOUNT}):{disk:.1f}%"

        with canvas(device) as draw:
            max_w = WIDTH
            draw.text((0, 0),  fit(draw, line1, max_w, font), font=font, fill=255)

            # CPU/T line: try precise; if too wide, fall back to ints
            l2 = line2_precise
            if draw.textlength(l2, font=font) > max_w:
                l2 = line2_ints
            draw.text((0, 14), fit(draw, l2, max_w, font), font=font, fill=255)

            draw.text((0, 28), fit(draw, line3, max_w, font), font=font, fill=255)
            draw.text((0, 42), fit(draw, line4, max_w, font), font=font, fill=255)

        time.sleep(UPDATE_SECS)

    except Exception as e:
        print("Loop error (continuing):", e)
        traceback.print_exc()
        time.sleep(2)
