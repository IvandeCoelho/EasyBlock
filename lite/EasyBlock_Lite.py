"""
EasyBlock Lite - bloqueio de sites, aplicativos e termos usando listas online (GitHub ou outras).

Execute como Administrador (necessario para editar o arquivo hosts).
Parametro: --minimized (abre minimizado na barra de tarefas)
"""
import ctypes
import hashlib
import hmac
import json
import os
import queue
import re
import shutil
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import urllib.request
import webbrowser
from tkinter import font as tkfont
from tkinter import messagebox, ttk
from urllib.parse import urlparse
from xml.sax.saxutils import escape

import psutil

APP_NAME = "EasyBlock Lite"
APP_VERSION = "1.0.0"
APP_TAGLINE = "Bloqueio online, por listas do GitHub ou de outras fontes, para Windows"
AUTHOR = "Ivande Coelho"
REPO_URL = "https://github.com/IvandeCoelho/EasyBlock"
# ---- Aba "Apoie o projeto" (apoio voluntario, opcional). Edite aqui textos, chave PIX e link.
SUPPORT_PIX_KEY = "ivandealveslp@gmail.com"
SUPPORT_GITHUB_URL = REPO_URL  # troque pela URL oficial do repositorio, se necessario
SUPPORT = {
    "titulo": "💛 Curtiu o projeto? Apoie!",
    "subtitulo": "Feito com dedicação para facilitar a vida de quem trabalha com tecnologia e educação.",
    "destaque": "🤝 Menos dores de cabeça, mais tempo para o que importa!",
    "mensagem": ("Caso essa solução tenha ajudado você e economizado algumas dores de cabeça, que tal dar "
                 "uma força para manter o projeto vivo? 😅\n\n"
                 "O aplicativo é desenvolvido de forma independente e voluntária. Sua contribuição é "
                 "opcional e ajuda a incentivar melhorias, correções e novas funcionalidades."),
    "sem_contribuir": ("Não pode contribuir financeiramente? Sem problemas! ⭐ Deixar uma estrela no GitHub, "
                       "compartilhar o projeto ou enviar sugestões também ajuda muito!"),
    "pix_rotulo": "☕ Quer pagar um cafezinho ao desenvolvedor?",
    "copiado": "Chave PIX copiada! Obrigado pelo apoio 💛",
    "erro_copia": "Não foi possível copiar. Selecione a chave e copie manualmente (Ctrl+C).",
    "sem_url": "O link do repositório ainda não foi configurado.",
    "rodape": ["🔓 Código aberto", "💛 Apoio voluntário", "🚫 Sem obrigação de contribuir"],
    "final": "Obrigado por usar o projeto e fazer parte dessa ideia! 💙",
}
DEFAULT_NAME = "Lista oficial (padrão)"
LIST_URL = ("https://raw.githubusercontent.com/IvandeCoelho/EasyBlock/"
            "refs/heads/main/lists/default-list.txt")
UPDATE_URL = ("https://raw.githubusercontent.com/IvandeCoelho/EasyBlock/"
              "refs/heads/main/version_lite.json")

IS_WIN = os.name == "nt"
HOSTS_PATH = r"C:\Windows\System32\drivers\etc\hosts"
MARK_BEGIN, MARK_END = "# BLOQUEADOR-INICIO", "# BLOQUEADOR-FIM"
_APPDATA = os.environ.get("APPDATA") or os.path.expanduser("~")
CONFIG_DIR = os.path.join(_APPDATA, "EasyBlockLite")
_OLD_CONFIG_DIR = os.path.join(_APPDATA, "BloqueadorLite")  # pasta usada ate a versao 1.0.0


def _migrate_old_dir():
    """Copia as configuracoes da pasta antiga (BloqueadorLite) na primeira abertura. A pasta antiga e mantida."""
    try:
        if os.path.isdir(_OLD_CONFIG_DIR) and not os.path.exists(CONFIG_DIR):
            shutil.copytree(_OLD_CONFIG_DIR, CONFIG_DIR)
    except OSError:
        pass


_migrate_old_dir()
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
LOG_PATH = os.path.join(CONFIG_DIR, "easyblock_lite.log")
CHECK_INTERVAL = 1.5
MAX_BYTES = 1_000_000
WM_CLOSE = 0x0010
CREATE_NO_WINDOW = 0x08000000
MUTEX_NAME = "Local\\BloqueadorLiteSingleInstance"
TASK_LOGON = "BloqueadorLite-Inicio"
WRAP = 860

KEYS = ("sites", "apps", "terms")
LABELS = {"sites": "Site", "apps": "Aplicativo", "terms": "Termo"}
NORMALIZERS = {}
INTERVALS = [("5 minutos", 5), ("15 minutos", 15), ("30 minutos", 30),
             ("1 hora", 60), ("6 horas", 360), ("24 horas", 1440)]
UNLOCK_CHOICES = ["1", "5", "15", "30", "60"]
SECTION_ALIASES = {
    "sites": "sites", "site": "sites",
    "apps": "apps", "app": "apps", "aplicativos": "apps", "jogos": "apps",
    "terms": "terms", "termos": "terms", "term": "terms",
}
# Processos essenciais do Windows: nunca encerrados (protege contra uma lista errada)
PROTECTED = {"explorer.exe", "svchost.exe", "winlogon.exe", "csrss.exe", "lsass.exe",
             "services.exe", "system", "dwm.exe", "wininit.exe", "smss.exe", "taskmgr.exe",
             "cmd.exe", "powershell.exe", "python.exe", "pythonw.exe", "easyblock_lite.exe",
             "conhost.exe", "fontdrvhost.exe", "sihost.exe", "registry", "system idle process",
             "memcompression"}
EXTRA = "\x00extra"  # sinal do dialogo: "Esqueci a senha"

# Paleta clara (mesmas cores da versao completa)
PAL = {"bg": "#f0f0f0", "fg": "#1a1a1a", "muted": "#555555", "field": "#ffffff",
       "ok": "#2a6f2a", "err": "#b03030", "link": "#0a58ca", "warn": "#b35c00",
       "sel": "#0078d4", "btn": "#e1e1e1", "border": "#c8c8c8"}


# ------------------------------------------------------------------ tema
def apply_style(root):
    for fname in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont",
                  "TkCaptionFont", "TkTooltipFont"):
        try:
            tkfont.nametofont(fname).configure(size=10)
        except tk.TclError:
            pass
    s = ttk.Style(root)
    try:
        s.theme_use("clam")
    except tk.TclError:
        pass
    p = PAL
    s.configure(".", background=p["bg"], foreground=p["fg"], fieldbackground=p["field"],
                bordercolor=p["border"], lightcolor=p["bg"], darkcolor=p["bg"],
                troughcolor=p["field"], selectbackground=p["sel"], selectforeground="#ffffff",
                insertcolor=p["fg"], focuscolor=p["sel"])
    s.configure("TButton", padding=(14, 7), background=p["btn"], foreground=p["fg"],
                bordercolor=p["border"])
    s.map("TButton", background=[("pressed", p["sel"]), ("active", p["border"]), ("disabled", p["bg"])],
          foreground=[("disabled", p["muted"])])
    s.configure("TCheckbutton", background=p["bg"], foreground=p["fg"], indicatorbackground=p["field"],
                indicatorforeground=p["fg"], padding=4)
    s.map("TCheckbutton", background=[("active", p["bg"])])
    s.configure("TLabel", background=p["bg"], foreground=p["fg"])
    s.configure("TLabelframe", background=p["bg"], bordercolor=p["border"])
    s.configure("TLabelframe.Label", background=p["bg"], foreground=p["fg"])
    s.configure("TEntry", fieldbackground=p["field"], foreground=p["fg"], insertcolor=p["fg"], padding=6)
    s.configure("TCombobox", fieldbackground=p["field"], background=p["btn"], foreground=p["fg"],
                arrowcolor=p["fg"], padding=6)
    s.map("TCombobox", fieldbackground=[("readonly", p["field"])], foreground=[("readonly", p["fg"])])
    s.configure("Treeview", background=p["field"], fieldbackground=p["field"], foreground=p["fg"],
                rowheight=24, bordercolor=p["border"])
    s.map("Treeview", background=[("selected", p["sel"])], foreground=[("selected", "#ffffff")])
    s.configure("Treeview.Heading", background=p["btn"], foreground=p["fg"], padding=5, relief="flat",
                font=("Segoe UI", 10, "bold"))
    s.map("Treeview.Heading", background=[("active", p["border"])])
    s.configure("TNotebook", background=p["bg"], bordercolor=p["border"])
    s.configure("TNotebook.Tab", background=p["btn"], foreground=p["fg"], padding=(14, 6),
                font=("Segoe UI", 10))
    s.map("TNotebook.Tab", background=[("selected", p["bg"])], foreground=[("selected", p["fg"])])
    s.configure("TScrollbar", background=p["btn"], troughcolor=p["bg"], bordercolor=p["border"],
                arrowcolor=p["fg"])
    root.configure(background=p["bg"])
    for opt, val in (("background", p["field"]), ("foreground", p["fg"]),
                     ("selectBackground", p["sel"]), ("selectForeground", "#ffffff")):
        root.option_add(f"*TCombobox*Listbox.{opt}", val)


def note(parent, text, color="muted", wrap=WRAP, **kw):
    return ttk.Label(parent, text=text, wraplength=wrap, justify="left", foreground=PAL[color], **kw)


# ------------------------------------------------------------------ utilidades
def log_error(msg: str):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(time.strftime("%d/%m/%Y %H:%M:%S ") + msg + "\n")
    except OSError:
        pass


def is_admin() -> bool:
    if not IS_WIN:
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def app_argv(extra=None) -> list:
    extra = list(extra or [])
    if getattr(sys, "frozen", False):
        return [sys.executable] + extra
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if IS_WIN and os.path.exists(pyw):
        exe = pyw
    return [exe, os.path.abspath(sys.argv[0])] + extra


def relaunch_as_admin(argv):
    args = app_argv(argv)
    ctypes.windll.shell32.ShellExecuteW(None, "runas", args[0], subprocess.list2cmdline(args[1:]), None, 1)


def normalize_site(text: str) -> str:
    t = text.strip().lower()
    if not t:
        return ""
    if "//" not in t:
        t = "//" + t
    try:
        host = urlparse(t).hostname or ""
    except ValueError:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host if "." in host and " " not in host else ""


def normalize_app(text: str) -> str:
    t = text.strip().strip('"')
    if "\\" in t or "/" in t:
        t = re.split(r"[\\/]", t)[-1]
    return t


def normalize_term(text: str) -> str:
    return text.strip().strip('"')


NORMALIZERS.update({"sites": normalize_site, "apps": normalize_app, "terms": normalize_term})


def parse_entries(text: str) -> list:
    return [p.strip() for p in re.split(r"[\n\r,;]+", text) if p.strip()]


def clean(d: dict) -> dict:
    """Normaliza, remove duplicados e descarta entradas invalidas."""
    res = {}
    for key in KEYS:
        seen, out = set(), []
        for raw in d.get(key, []):
            v = NORMALIZERS[key](str(raw))
            if not v or v.lower() in seen:
                continue
            if key == "terms" and len(v) < 3:
                continue
            if key == "apps" and not v.lower().endswith(".exe") and len(v) < 3:
                continue
            seen.add(v.lower())
            out.append(v)
        res[key] = out
    return res


def parse_list(text: str) -> dict:
    """Aceita JSON {"sites":[],"apps":[],"terms":[]} ou texto com secoes [sites] [apps] [termos]."""
    text = text.lstrip("\ufeff")
    raw = {k: [] for k in KEYS}
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    if isinstance(data, dict):
        for k in KEYS:
            if isinstance(data.get(k), list):
                raw[k] = [str(x) for x in data[k]]
        return clean(raw)
    section = "sites"
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = SECTION_ALIASES.get(line[1:-1].strip().lower())
            continue
        if section:
            raw[section].extend(parse_entries(line))
    return clean(raw)


def fetch_list(url: str) -> dict:
    if not url.lower().startswith("https://"):
        raise ValueError("endereço precisa começar com https://")
    req = urllib.request.Request(url, headers={"User-Agent": f"EasyBlockLite/{APP_VERSION}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("arquivo grande demais (máx. 1 MB)")
    return parse_list(data.decode("utf-8-sig", errors="replace"))


def fetch_update() -> dict:
    req = urllib.request.Request(UPDATE_URL, headers={"User-Agent": f"EasyBlockLite/{APP_VERSION}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        info = json.loads(resp.read(100_000).decode("utf-8-sig", errors="replace"))
    download = str(info.get("download") or REPO_URL + "/releases")
    if not download.lower().startswith("https://"):
        download = REPO_URL + "/releases"
    return {"version": str(info["version"]), "download": download, "notes": str(info.get("notes", ""))}


def version_tuple(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v)) or (0,)


# --------------------------------------------------------------- configuracao
def empty_lists() -> dict:
    return {k: [] for k in KEYS}


def make_source(name: str, url: str, enabled: bool = True) -> dict:
    return {"name": name, "url": url, "enabled": enabled, "last_sync": "", "cache": empty_lists()}


def default_config() -> dict:
    return {
        "active": True, "interval": 30, "unlock_minutes": 5, "autostart": False,
        "check_updates": True, "ignored": empty_lists(),
        "sources": [make_source(DEFAULT_NAME, LIST_URL)],
        "security": {"salt": "", "hash": "", "rsalt": "", "rhash": ""},
    }


def _lists(d) -> dict:
    d = d if isinstance(d, dict) else {}
    return {k: [str(x) for x in d[k]] if isinstance(d.get(k), list) else [] for k in KEYS}


def load_config() -> dict:
    cfg = default_config()
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return cfg
    if not isinstance(data, dict):
        return cfg
    cfg["active"] = bool(data.get("active", True))
    cfg["autostart"] = bool(data.get("autostart", False))
    cfg["check_updates"] = bool(data.get("check_updates", True))
    try:
        cfg["interval"] = int(data.get("interval", 30))
    except (TypeError, ValueError):
        pass
    try:
        cfg["unlock_minutes"] = max(1, min(120, int(data.get("unlock_minutes", 5))))
    except (TypeError, ValueError):
        pass
    cfg["ignored"] = _lists(data.get("ignored"))
    sec = data.get("security") if isinstance(data.get("security"), dict) else {}
    for k in cfg["security"]:
        cfg["security"][k] = str(sec.get(k, ""))

    raw = data.get("sources")
    if not isinstance(raw, list):  # migracao da versao anterior (lista unica)
        raw = [{"name": DEFAULT_NAME, "url": LIST_URL, "enabled": True,
                "cache": data.get("cache"), "last_sync": data.get("last_sync", "")}]
    srcs = []
    for s in raw:
        if not isinstance(s, dict):
            continue
        url = str(s.get("url", "")).strip()
        if not url.lower().startswith("https://") or any(x["url"] == url for x in srcs):
            continue
        srcs.append({"name": str(s.get("name") or "Lista online")[:60], "url": url,
                     "enabled": bool(s.get("enabled", True)), "last_sync": str(s.get("last_sync", "")),
                     "cache": _lists(s.get("cache"))})
    for x in srcs:
        if x["url"] == LIST_URL:
            x["name"] = DEFAULT_NAME
    if not srcs:  # o usuario removeu todas as listas: a padrao volta a ser carregada
        srcs.insert(0, make_source(DEFAULT_NAME, LIST_URL))
    cfg["sources"] = srcs
    return cfg


def save_config(cfg: dict):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    os.replace(tmp, CONFIG_PATH)


def effective(cfg: dict) -> dict:
    """Uniao das listas ativas, menos os itens ignorados neste computador."""
    out = {}
    for k in KEYS:
        skip = {x.lower() for x in cfg["ignored"][k]}
        seen, items = set(), []
        for s in cfg["sources"]:
            if not s["enabled"]:
                continue
            for x in s["cache"][k]:
                lx = x.lower()
                if lx in skip or lx in seen:
                    continue
                seen.add(lx)
                items.append(x)
        out[k] = items
    return out


# ------------------------------------------------------------------ senha
def _pbkdf2(pw: str, salt_hex: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), bytes.fromhex(salt_hex), 200_000).hex()


def has_password(cfg: dict) -> bool:
    return bool(cfg["security"]["hash"])


def set_password(cfg: dict, pw: str) -> str:
    sec = cfg["security"]
    sec["salt"] = secrets.token_hex(16)
    sec["hash"] = _pbkdf2(pw, sec["salt"])
    code = "-".join(secrets.token_hex(2).upper() for _ in range(3))
    sec["rsalt"] = secrets.token_hex(16)
    sec["rhash"] = _pbkdf2(code, sec["rsalt"])
    return code


def check_password(cfg: dict, pw: str) -> bool:
    sec = cfg["security"]
    return bool(sec["hash"]) and hmac.compare_digest(_pbkdf2(pw, sec["salt"]), sec["hash"])


def check_recovery(cfg: dict, code: str) -> bool:
    sec = cfg["security"]
    return bool(sec["rhash"]) and hmac.compare_digest(
        _pbkdf2(code.strip().upper(), sec["rsalt"]), sec["rhash"])


def clear_password(cfg: dict):
    for k in cfg["security"]:
        cfg["security"][k] = ""


# ------------------------------------------------------------------ hosts
def apply_hosts(sites: list, active: bool):
    with open(HOSTS_PATH, "r", encoding="utf-8", errors="replace") as f:
        old = f.read().splitlines()
    lines, inside = [], False
    for line in old:
        if line.strip() == MARK_BEGIN:
            inside = True
            continue
        if line.strip() == MARK_END:
            inside = False
            continue
        if not inside:
            lines.append(line)
    while lines and not lines[-1].strip():
        lines.pop()
    if active and sites:
        lines += ["", MARK_BEGIN]
        for s in sites:
            lines += [f"127.0.0.1 {s}", f"127.0.0.1 www.{s}", f"::1 {s}", f"::1 www.{s}"]
        lines.append(MARK_END)
    if "\n".join(lines).rstrip() == "\n".join(old).rstrip():
        return
    with open(HOSTS_PATH, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\n".join(lines) + "\n")
    subprocess.run(["ipconfig", "/flushdns"], capture_output=True,
                   creationflags=CREATE_NO_WINDOW if IS_WIN else 0)


# ----------------------------------------------------------- janelas / processos
if IS_WIN:
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
else:
    user32 = kernel32 = None


def visible_windows() -> list:
    """Lista de (hwnd, titulo, pid) das janelas visiveis."""
    if not IS_WIN:
        return []
    result = []

    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                result.append((hwnd, buf.value, pid.value))
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return result


def app_matches(entry: str, proc_lower: str) -> bool:
    entry = entry.lower()
    return proc_lower == entry if entry.endswith(".exe") else entry in proc_lower


class Monitor(threading.Thread):
    """Encerra processos e fecha janelas conforme as listas efetivas."""

    def __init__(self, get_lists):
        super().__init__(daemon=True)
        self.get_lists = get_lists
        self.my_pid = os.getpid()
        self.blocked = 0
        self.last_error = ""

    def run(self):
        while True:
            try:
                apps, terms = self.get_lists()
                self.sweep(apps, terms)
                self.last_error = ""
            except Exception as e:
                msg = f"{type(e).__name__}: {e}"
                if msg != self.last_error:
                    log_error("monitor: " + msg)
                self.last_error = msg
            time.sleep(CHECK_INTERVAL)

    def sweep(self, apps: list, terms: list):
        if not apps and not terms:
            return
        apps = [a.lower() for a in apps]
        terms = [t.lower() for t in terms]
        for p in psutil.process_iter(["name", "pid"]):
            name = p.info["name"] or ""
            low = name.lower()
            if p.info["pid"] == self.my_pid or low in PROTECTED:
                continue
            if any(app_matches(a, low) for a in apps) or any(t in low for t in terms):
                try:
                    p.kill()
                    self.blocked += 1
                except Exception:
                    pass
        if terms and IS_WIN:
            for hwnd, title, pid in visible_windows():
                if pid != self.my_pid and any(t in title.lower() for t in terms):
                    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                    self.blocked += 1


def acquire_instance() -> bool:
    """Reserva a instancia unica. False se o app ja esta aberto."""
    if not IS_WIN:
        return True
    kernel32.CreateMutexW(None, False, MUTEX_NAME)
    return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS


# ------------------------------------------------------- inicio com o Windows
def _schtasks(args: list) -> tuple:
    r = subprocess.run(["schtasks"] + args, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def set_autostart(enable: bool) -> tuple:
    if not IS_WIN:
        return False, "Disponível apenas no Windows."
    if not enable:
        _schtasks(["/Delete", "/TN", TASK_LOGON, "/F"])
        return True, ""
    argv = app_argv(["--minimized"])
    user = os.environ.get("USERNAME", "")
    domain = os.environ.get("USERDOMAIN", "")
    uid = f"<UserId>{escape(domain + chr(92) + user if domain else user)}</UserId>" if user else ""
    xml = (
        '<?xml version="1.0" encoding="UTF-16"?>\n'
        '<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">'
        "<RegistrationInfo><Description>Inicia o EasyBlock Lite ao entrar no Windows</Description></RegistrationInfo>"
        f"<Triggers><LogonTrigger><Enabled>true</Enabled>{uid}</LogonTrigger></Triggers>"
        f'<Principals><Principal id="Author">{uid}<LogonType>InteractiveToken</LogonType>'
        "<RunLevel>HighestAvailable</RunLevel></Principal></Principals>"
        "<Settings><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>"
        "<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><StartWhenAvailable>true</StartWhenAvailable>"
        "<ExecutionTimeLimit>PT0S</ExecutionTimeLimit><Enabled>true</Enabled></Settings>"
        f'<Actions Context="Author"><Exec><Command>{escape(argv[0])}</Command>'
        f"<Arguments>{escape(subprocess.list2cmdline(argv[1:]))}</Arguments></Exec></Actions></Task>"
    )
    path = os.path.join(tempfile.mkdtemp(prefix="bloqL_"), "task.xml")
    with open(path, "w", encoding="utf-16") as f:
        f.write(xml)
    try:
        return _schtasks(["/Create", "/TN", TASK_LOGON, "/XML", path, "/F"])
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


# ------------------------------------------------------------------ dialogos
def _modal(dlg, parent):
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    dlg.wait_window()


def ask_text(parent, title: str, prompt: str, show: str = "", extra_label: str = None):
    """Pede um texto. Retorna a string, None (cancelar) ou EXTRA (botao extra)."""
    dlg = tk.Toplevel(parent.winfo_toplevel())
    dlg.title(title)
    dlg.resizable(False, False)
    frm = ttk.Frame(dlg, padding=18)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=prompt, wraplength=460, justify="left").pack(anchor="w")
    var = tk.StringVar()
    ent = ttk.Entry(frm, textvariable=var, show=show, width=40)
    ent.pack(fill="x", pady=14)
    result = {"v": None}

    def ok(_=None):
        result["v"] = var.get()
        dlg.destroy()

    def extra():
        result["v"] = EXTRA
        dlg.destroy()

    row = ttk.Frame(frm)
    row.pack(fill="x")
    if extra_label:
        ttk.Button(row, text=extra_label, command=extra).pack(side="left")
    ttk.Button(row, text="Cancelar", command=dlg.destroy).pack(side="right")
    ttk.Button(row, text="OK", command=ok).pack(side="right", padx=6)
    dlg.bind("<Return>", ok)
    dlg.bind("<Escape>", lambda e: dlg.destroy())
    ent.focus_set()
    _modal(dlg, parent)
    return result["v"]


def show_recovery_code(parent, code: str):
    dlg = tk.Toplevel(parent.winfo_toplevel())
    dlg.title("Código de recuperação")
    dlg.resizable(False, False)
    frm = ttk.Frame(dlg, padding=18)
    frm.pack()
    ttk.Label(frm, text="Senha definida!", font=("Segoe UI", 14, "bold")).pack(anchor="w")
    note(frm, "Anote este código de recuperação e guarde em lugar seguro. Ele é mostrado UMA ÚNICA VEZ "
              "e é a única forma de remover a senha se você a esquecer.", wrap=520).pack(anchor="w", pady=(6, 12))
    ttk.Label(frm, text=code, font=("Consolas", 18, "bold"), foreground=PAL["warn"]).pack(pady=8)
    ttk.Button(frm, text="Anotei, fechar", command=dlg.destroy).pack(anchor="e", pady=(12, 0))
    _modal(dlg, parent)


def source_dialog(parent, sources, name="", url="", editing_url=None):
    """Adicionar/editar uma lista online. Retorna dict {name,url} ou None."""
    dlg = tk.Toplevel(parent.winfo_toplevel())
    dlg.title("Lista online")
    dlg.resizable(False, False)
    frm = ttk.Frame(dlg, padding=18)
    frm.pack(fill="both", expand=True)
    n, u = tk.StringVar(value=name), tk.StringVar(value=url)
    ttk.Label(frm, text="Nome da lista:").grid(row=0, column=0, sticky="w", pady=6)
    ttk.Entry(frm, textvariable=n, width=56).grid(row=0, column=1, pady=6, padx=(12, 0))
    ttk.Label(frm, text="Endereço (https://):").grid(row=1, column=0, sticky="w", pady=6)
    ttk.Entry(frm, textvariable=u, width=56).grid(row=1, column=1, pady=6, padx=(12, 0))
    note(frm, "Use o link 'raw' do arquivo de texto, por exemplo: "
              "https://raw.githubusercontent.com/usuario/repositorio/main/lista.txt",
         wrap=640).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))
    err = ttk.Label(frm, text="", foreground=PAL["err"])
    err.grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))
    result = {}

    def ok(_=None):
        uu, nn = u.get().strip(), n.get().strip()
        if not uu.lower().startswith("https://") or len(uu) < 12:
            err.config(text="O endereço precisa começar com https://")
            return
        if any(x["url"] == uu and x["url"] != editing_url for x in sources):
            err.config(text="Essa lista já foi adicionada.")
            return
        nn = nn or urlparse(uu).hostname or "Lista online"
        base, i = nn, 2
        while any(x["name"].lower() == nn.lower() and x["url"] != editing_url for x in sources):
            nn, i = f"{base} ({i})", i + 1
        result.update(name=nn[:60], url=uu)
        dlg.destroy()

    row = ttk.Frame(frm)
    row.grid(row=4, column=0, columnspan=2, sticky="e", pady=(14, 0))
    ttk.Button(row, text="Cancelar", command=dlg.destroy).pack(side="right")
    ttk.Button(row, text="Salvar", command=ok).pack(side="right", padx=6)
    dlg.bind("<Return>", ok)
    dlg.bind("<Escape>", lambda e: dlg.destroy())
    _modal(dlg, parent)
    return result or None


# ---------------------------------------------------------------- abas
class OnlineTab(ttk.Frame):
    HEADINGS = {"origem": "Lista", "tipo": "Tipo", "item": "Item", "estado": "Estado"}

    def __init__(self, parent, app):
        super().__init__(parent, padding=12)
        self.app = app
        self.sort_col, self.sort_rev = "estado", False
        note(self, "Listas mantidas online, pela lista padrão ou por outras fontes que você cadastrar. "
                   "Todas as listas ativas se somam. Se a internet cair, vale a última versão baixada.").pack(anchor="w")

        lf = ttk.Frame(self)
        lf.pack(fill="x", pady=(10, 4))
        self.src = ttk.Treeview(lf, columns=("on", "nome", "itens", "sync", "estado"), show="headings",
                                height=4, selectmode="browse")
        for col, text, w in (("on", "Ativa", 70), ("nome", "Lista", 260), ("itens", "Itens", 70),
                             ("sync", "Última sincronização", 180), ("estado", "Estado", 260)):
            self.src.heading(col, text=text, anchor="w")
            self.src.column(col, width=w, stretch=(col == "estado"))
        self.src.pack(fill="x")
        self.src.bind("<Double-1>", lambda e: self.edit_source())
        self.src.bind("<<TreeviewSelect>>", lambda e: self.refresh_items())

        row = ttk.Frame(self)
        row.pack(fill="x", pady=6)
        for text, cmd in (("➕ Adicionar lista…", self.add_source), ("✏ Editar…", self.edit_source),
                          ("🗑 Remover", self.remove_source), ("⏯ Ativar/Desativar", self.toggle_source),
                          ("🔄 Sincronizar agora", self.sync_now)):
            ttk.Button(row, text=text, command=cmd).pack(side="left", padx=(0, 8))
        row2 = ttk.Frame(self)
        row2.pack(fill="x", pady=(2, 0))
        ttk.Label(row2, text="Atualizar a cada:").pack(side="left")
        cur = next((l for l, m in INTERVALS if m == app.cfg["interval"]), "30 minutos")
        self.interval = tk.StringVar(value=cur)
        cb = ttk.Combobox(row2, textvariable=self.interval, values=[l for l, _ in INTERVALS],
                          state="readonly", width=14)
        cb.pack(side="left", padx=8)
        cb.bind("<<ComboboxSelected>>", lambda e: self.save_interval())
        self.msg = ttk.Label(self, text="")
        self.msg.pack(anchor="w", pady=(8, 4))

        lf2 = ttk.Frame(self)
        lf2.pack(fill="both", expand=True, pady=(4, 0))
        self.tree = ttk.Treeview(lf2, columns=tuple(self.HEADINGS), show="headings", height=8,
                                 selectmode="extended")
        for col, w in (("origem", 230), ("tipo", 120), ("item", 380), ("estado", 110)):
            self.tree.column(col, width=w, stretch=(col == "item"))
        for col, title in self.HEADINGS.items():
            self.tree.heading(col, text=title, anchor="w", command=lambda c=col: self.sort_by(c))
        self.tree.tag_configure("ignored", foreground=PAL["muted"])
        sb = ttk.Scrollbar(lf2, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<Delete>", lambda e: self.ignore_selected())

        bot = ttk.Frame(self)
        bot.pack(fill="x", pady=(10, 0))
        ttk.Button(bot, text="🚫 Ignorar selecionados", command=self.ignore_selected).pack(side="left")
        ttk.Button(bot, text="↩ Restaurar selecionados", command=self.restore_selected).pack(side="left", padx=8)
        ttk.Button(bot, text="Restaurar todos", command=self.restore_all).pack(side="left")
        note(self, "Ignorar vale só neste computador: o item continua na lista online, mas não é bloqueado aqui. "
                   "Para apagar de vez, remova a linha no arquivo online.").pack(anchor="w", pady=(8, 0))
        self.refresh()

    # ---- estado
    @property
    def sources(self):
        return self.app.cfg["sources"]

    def selected_source(self):
        sel = self.src.selection()
        return next((s for s in self.sources if s["url"] == sel[0]), None) if sel else None

    def source_state(self, s) -> tuple:
        if not s["enabled"]:
            return "desativada", PAL["muted"]
        st = self.app.sync_status.get(s["url"])
        if st is None:
            return ("ok" if s["last_sync"] else "aguardando sincronização"), PAL["muted"]
        kind, msg = st
        if kind == "run":
            return "sincronizando…", PAL["muted"]
        if kind == "ok":
            return "ok", PAL["ok"]
        return f"erro: {msg} (usando a última cópia)", PAL["err"]

    def refresh(self):
        sel = self.src.selection()
        self.src.delete(*self.src.get_children())
        for s in self.sources:
            n = sum(len(v) for v in s["cache"].values())
            state, _ = self.source_state(s)
            self.src.insert("", "end", iid=s["url"], values=(
                "✔" if s["enabled"] else "—", s["name"], n, s["last_sync"] or "—", state))
        if sel and self.src.exists(sel[0]):
            self.src.selection_set(sel[0])
        elif self.sources:
            self.src.selection_set(self.sources[0]["url"])
        self.refresh_items()

    def is_ignored(self, key, item) -> bool:
        return item.lower() in {x.lower() for x in self.app.cfg["ignored"][key]}

    def sort_by(self, col):
        self.sort_rev = (not self.sort_rev) if col == self.sort_col else False
        self.sort_col = col
        self.refresh_items()

    def refresh_items(self, message=None, ok=True):
        self.tree.delete(*self.tree.get_children())
        rows = []
        for s in self.sources:
            if not s["enabled"]:
                continue
            for key in KEYS:
                for item in s["cache"][key]:
                    rows.append((s["name"], LABELS[key], item, self.is_ignored(key, item)))
        keyfn = {"estado": lambda t: (t[3], t[1], t[2].lower()),
                 "tipo": lambda t: (t[1], t[3], t[2].lower()),
                 "item": lambda t: (t[2].lower(), t[1]),
                 "origem": lambda t: (t[0].lower(), t[3], t[2].lower())}[self.sort_col]
        for origem, label, item, ig in sorted(rows, key=keyfn, reverse=self.sort_rev):
            self.tree.insert("", "end", values=(origem, label, item, "ignorado" if ig else "ativo"),
                             tags=("ignored",) if ig else ())
        for col, title in self.HEADINGS.items():
            arrow = (" ▼" if self.sort_rev else " ▲") if col == self.sort_col else ""
            self.tree.heading(col, text=title + arrow)
        if message is None:
            total = sum(len(v) for v in effective(self.app.cfg).values())
            message = f"{total} itens ativos vindos das listas online."
        self.msg.config(text=message, foreground=PAL["ok"] if ok else PAL["err"])
        self.app.refresh_status()

    def save_interval(self):
        if not self.app.auth("Alterar a frequência de atualização"):
            cur = next((l for l, m in INTERVALS if m == self.app.cfg["interval"]), "30 minutos")
            self.interval.set(cur)
            return
        self.app.cfg["interval"] = dict(INTERVALS).get(self.interval.get(), 30)
        self.app.save()

    # ---- listas
    def add_source(self):
        r = source_dialog(self, self.sources)
        if not r:
            return
        self.sources.append(make_source(r["name"], r["url"], True))
        self.app.save()
        self.refresh()
        self.src.selection_set(r["url"])
        self.app.start_sync(force=True)

    def edit_source(self):
        s = self.selected_source()
        if not s or not self.app.auth("Editar listas online"):
            return
        r = source_dialog(self, self.sources, s["name"], s["url"], editing_url=s["url"])
        if not r:
            return
        if r["url"] != s["url"]:
            s["cache"], s["last_sync"] = empty_lists(), ""
            self.app.sync_status.pop(s["url"], None)
        if s["url"] == LIST_URL:
            r["name"] = DEFAULT_NAME
        s.update(name=r["name"], url=r["url"])
        self.app.save()
        self.app.sync_hosts()
        self.refresh()
        self.app.start_sync(force=True)

    def remove_source(self):
        s = self.selected_source()
        if not s:
            return
        if not self.app.auth("Remover listas online"):
            return
        if not messagebox.askyesno(APP_NAME, f"Remover a lista \"{s['name']}\"?"):
            return
        self.app.cfg["sources"] = [x for x in self.sources if x["url"] != s["url"]]
        self.app.sync_status.pop(s["url"], None)
        self.app.save()
        self.app.sync_hosts()
        self.refresh()

    def toggle_source(self):
        s = self.selected_source()
        if not s:
            return
        if s["enabled"] and not self.app.auth("Desativar uma lista online"):
            return
        s["enabled"] = not s["enabled"]
        self.app.save()
        self.app.sync_hosts()
        self.refresh()
        if s["enabled"]:
            self.app.start_sync(force=True)

    def sync_now(self):
        self.app.start_sync(force=True)
        self.refresh_items("Sincronizando…")

    # ---- ignorar
    def selected_entries(self):
        out = []
        inv = {v: k for k, v in LABELS.items()}
        for iid in self.tree.selection():
            _o, label, item, _e = self.tree.item(iid, "values")
            out.append((inv[str(label)], str(item)))
        return out

    def ignore_selected(self):
        sel = self.selected_entries()
        if not sel:
            return self.refresh_items("Selecione itens na lista (Ctrl/Shift para vários).", ok=False)
        if not self.app.auth("Ignorar itens da lista online"):
            return
        ign = self.app.cfg["ignored"]
        for key, item in sel:
            if not self.is_ignored(key, item):
                ign[key].append(item)
        self.apply_change(f"{len(sel)} item(ns) ignorado(s).")

    def restore_selected(self):
        sel = self.selected_entries()
        if not sel:
            return self.refresh_items("Selecione itens na lista.", ok=False)
        if not self.app.auth("Restaurar itens do bloqueio"):
            return
        ign = self.app.cfg["ignored"]
        for key, item in sel:
            ign[key] = [x for x in ign[key] if x.lower() != item.lower()]
        self.apply_change(f"{len(sel)} item(ns) restaurado(s).")

    def restore_all(self):
        if not self.app.auth("Restaurar todos os itens"):
            return
        ign = self.app.cfg["ignored"]
        n = sum(len(v) for v in ign.values())
        for key in ign:
            ign[key] = []
        self.apply_change(f"{n} item(ns) restaurado(s).")

    def apply_change(self, message):
        self.app.save()
        self.app.sync_hosts()
        self.refresh_items(message)


class SettingsTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=12)
        self.app = app
        cfg = app.cfg

        sec = ttk.LabelFrame(self, text=" Segurança ", padding=12)
        sec.pack(fill="x", pady=(0, 12))
        self.pw_state = ttk.Label(sec, text="")
        self.pw_state.pack(anchor="w")
        note(sec, "Com senha, pausar o bloqueio, sair, ignorar itens e alterar configurações exigem a senha. "
                  "Use o código de recuperação se esquecer a senha.").pack(anchor="w", pady=(4, 8))
        row = ttk.Frame(sec)
        row.pack(anchor="w")
        self.pw_btn = ttk.Button(row, text="Definir senha", command=self.set_password)
        self.pw_btn.pack(side="left")
        self.pw_rm = ttk.Button(row, text="Remover senha", command=self.remove_password)
        self.pw_rm.pack(side="left", padx=8)
        ttk.Button(row, text="🔒 Bloquear agora", command=app.lock_now).pack(side="left")
        row2 = ttk.Frame(sec)
        row2.pack(anchor="w", pady=(10, 0))
        ttk.Label(row2, text="Lembrar a senha por").pack(side="left")
        self.unlock = tk.StringVar(value=str(cfg["unlock_minutes"]))
        cb = ttk.Combobox(row2, textvariable=self.unlock, values=UNLOCK_CHOICES, state="readonly", width=5)
        cb.pack(side="left", padx=8)
        cb.bind("<<ComboboxSelected>>", lambda e: self.save_unlock())
        ttk.Label(row2, text="minutos").pack(side="left")

        sysf = ttk.LabelFrame(self, text=" Sistema ", padding=12)
        sysf.pack(fill="x", pady=(0, 12))
        self.autostart = tk.BooleanVar(value=cfg["autostart"])
        ttk.Checkbutton(sysf, text="Iniciar com o Windows (abre minimizado, já como administrador)",
                        variable=self.autostart, command=self.toggle_autostart).pack(anchor="w")
        self.check_updates = tk.BooleanVar(value=cfg["check_updates"])
        ttk.Checkbutton(sysf, text="Verificar atualizações ao abrir o app", variable=self.check_updates,
                        command=self.save_check_updates).pack(anchor="w", pady=(8, 0))

        ttk.Button(self, text="📁 Abrir pasta de configurações", command=self.open_folder).pack(anchor="w")
        self.refresh_pw()

    def refresh_pw(self):
        has = has_password(self.app.cfg)
        self.pw_state.config(text="🔒 Proteção por senha: ligada" if has else "🔓 Proteção por senha: desligada",
                             foreground=PAL["ok"] if has else PAL["muted"])
        self.pw_btn.config(text="Alterar senha" if has else "Definir senha")
        self.pw_rm.config(state="normal" if has else "disabled")

    def set_password(self):
        if has_password(self.app.cfg) and not self.app.auth("Alterar a senha", fresh=True):
            return
        p1 = ask_text(self, "Nova senha", "Digite a nova senha (mínimo 4 caracteres):", show="•")
        if p1 in (None, EXTRA):
            return
        if len(p1) < 4:
            return messagebox.showwarning(APP_NAME, "Use pelo menos 4 caracteres.")
        p2 = ask_text(self, "Nova senha", "Digite a senha novamente:", show="•")
        if p2 != p1:
            return messagebox.showwarning(APP_NAME, "As senhas não são iguais.")
        code = set_password(self.app.cfg, p1)
        self.app.save()
        self.app.lock_now()
        self.refresh_pw()
        show_recovery_code(self, code)

    def remove_password(self):
        if not self.app.auth("Remover a senha", fresh=True):
            return
        clear_password(self.app.cfg)
        self.app.save()
        self.refresh_pw()

    def save_unlock(self):
        if not self.app.auth("Alterar configurações"):
            self.unlock.set(str(self.app.cfg["unlock_minutes"]))
            return
        self.app.cfg["unlock_minutes"] = int(self.unlock.get())
        self.app.save()

    def toggle_autostart(self):
        new = self.autostart.get()
        if not self.app.auth("Alterar o início com o Windows"):
            self.autostart.set(not new)
            return
        ok, out = set_autostart(new)
        if not ok:
            self.autostart.set(not new)
            return messagebox.showerror(APP_NAME, f"Não foi possível alterar o início automático:\n{out}")
        self.app.cfg["autostart"] = new
        self.app.save()

    def save_check_updates(self):
        self.app.cfg["check_updates"] = self.check_updates.get()
        self.app.save()

    def open_folder(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        try:
            os.startfile(CONFIG_DIR)
        except AttributeError:
            webbrowser.open(CONFIG_DIR)


class AboutTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=18)
        self.app = app
        self.update_info = None
        ttk.Label(self, text=APP_NAME, font=("Segoe UI", 18, "bold")).pack(anchor="w")
        note(self, APP_TAGLINE, color="muted").pack(anchor="w", pady=(0, 14))
        info = ttk.Frame(self)
        info.pack(fill="x")
        rows = [("Versão", APP_VERSION), ("Autor", AUTHOR), ("Sistema", "Windows 10 / 11"),
                ("Repositório", REPO_URL), ("Configurações", CONFIG_DIR)]
        for i, (k, v) in enumerate(rows):
            ttk.Label(info, text=f"{k}:", font=("Segoe UI", 10, "bold")).grid(row=i, column=0, sticky="nw", pady=3, padx=(0, 12))
            lbl = ttk.Label(info, text=v, wraplength=600)
            lbl.grid(row=i, column=1, sticky="w", pady=3)
            if k == "Repositório":
                lbl.configure(foreground=PAL["link"], cursor="hand2")
                lbl.bind("<Button-1>", lambda e: webbrowser.open(REPO_URL))

        box = ttk.LabelFrame(self, text=" Atualizações ", padding=12)
        box.pack(fill="x", pady=16)
        self.status = ttk.Label(box, text="Clique em \"Verificar atualizações\".", wraplength=760)
        self.status.pack(anchor="w")
        self.notes = ttk.Label(box, text="", wraplength=760, foreground=PAL["muted"])
        self.notes.pack(anchor="w", pady=(4, 0))
        row = ttk.Frame(box)
        row.pack(fill="x", pady=(10, 0))
        ttk.Button(row, text="🔄 Verificar atualizações", command=lambda: app.check_update(True)).pack(side="left")
        self.dl_btn = ttk.Button(row, text="⬇ Baixar nova versão", state="disabled", command=self.download)
        self.dl_btn.pack(side="left", padx=8)

        note(self, "Como funciona: sites são bloqueados pelo arquivo hosts do Windows; aplicativos e termos são "
                   "encerrados enquanto o app estiver aberto. As listas vêm da internet; o app não se atualiza sozinho.").pack(anchor="w")

    def download(self):
        if self.update_info:
            webbrowser.open(self.update_info["download"])

    def set_checking(self):
        self.status.config(text="Verificando…", foreground="")
        self.notes.config(text="")

    def show_result(self, kind, payload, manual):
        if kind == "ok":
            if version_tuple(payload["version"]) > version_tuple(APP_VERSION):
                self.update_info = payload
                self.status.config(text=f"🔔 Nova versão disponível: {payload['version']} "
                                        f"(você tem {APP_VERSION})", foreground=PAL["warn"])
                self.notes.config(text=payload["notes"])
                self.dl_btn.config(state="normal")
            else:
                self.update_info = None
                self.status.config(text=f"✔ Você está na versão mais recente ({APP_VERSION}). "
                                        f"Verificado em {time.strftime('%d/%m/%Y %H:%M')}.", foreground=PAL["ok"])
                self.notes.config(text="")
                self.dl_btn.config(state="disabled")
        elif manual:
            self.status.config(text=f"Não foi possível verificar agora: {payload}", foreground=PAL["err"])
            self.notes.config(text="")


class SupportTab(ttk.Frame):
    """Apoio voluntario e opcional: mostra a chave PIX e um link para o GitHub. Nao cobra nada."""

    def __init__(self, parent, app):
        super().__init__(parent, padding=18)
        self.app = app
        s = SUPPORT
        st = ttk.Style(self)
        st.configure("Accent.TButton", background="#f5b400", foreground="#1a1a1a",
                     bordercolor="#c98f00", padding=(14, 8))
        st.map("Accent.TButton", background=[("active", "#ffc933"), ("pressed", "#d99f00")])

        ttk.Label(self, text=s["titulo"], font=("Segoe UI", 18, "bold")).pack(anchor="w")
        note(self, s["subtitulo"], color="muted").pack(anchor="w", pady=(2, 12))
        ttk.Label(self, text=s["destaque"], font=("Segoe UI", 10, "bold")).pack(anchor="w")
        note(self, s["mensagem"]).pack(anchor="w", pady=(6, 0))
        note(self, s["sem_contribuir"], color="muted").pack(anchor="w", pady=(10, 0))

        card = ttk.LabelFrame(self, text=f" {s['pix_rotulo']} ", padding=16)
        card.pack(fill="x", pady=(18, 0))
        ttk.Label(card, text="Chave PIX (e-mail):", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.pix_var = tk.StringVar(value=SUPPORT_PIX_KEY)  # guardado no objeto para nao ser coletado
        ttk.Entry(card, textvariable=self.pix_var, state="readonly",
                  font=("Consolas", 12)).pack(fill="x", pady=(6, 12), ipady=4)
        row = ttk.Frame(card)
        row.pack(anchor="w")
        ttk.Button(row, text="📋 Copiar chave PIX", style="Accent.TButton", command=self.copy_pix).pack(side="left")
        ttk.Button(row, text="⭐ Apoiar no GitHub", command=self.open_github).pack(side="left", padx=8)
        self.feedback = ttk.Label(card, text="", foreground=PAL["ok"])
        self.feedback.pack(anchor="w", pady=(10, 0))

        tags = ttk.Frame(self)
        tags.pack(fill="x", pady=(18, 0))
        for text in s["rodape"]:
            ttk.Label(tags, text=text, foreground=PAL["muted"]).pack(side="left", padx=(0, 18))
        ttk.Label(self, text=s["final"], font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 0))

        bot = ttk.Frame(self)
        bot.pack(fill="x", pady=(16, 0))
        ttk.Button(bot, text="Fechar", command=lambda: self.app.nb.select(0)).pack(side="right")

    def copy_pix(self):
        key = SUPPORT_PIX_KEY
        try:
            top = self.winfo_toplevel()
            top.clipboard_clear()
            top.clipboard_append(key)
            top.update()
            if top.clipboard_get() != key:
                raise tk.TclError("conteudo diferente")
            self.feedback.config(text=SUPPORT["copiado"], foreground=PAL["ok"])
        except tk.TclError:
            self.feedback.config(text=SUPPORT["erro_copia"], foreground=PAL["err"])
        self.after(5000, lambda: self.feedback.config(text=""))

    def open_github(self):
        url = (SUPPORT_GITHUB_URL or "").strip()
        if not url.lower().startswith("https://"):
            return messagebox.showinfo(APP_NAME, SUPPORT["sem_url"])
        try:
            webbrowser.open(url)
        except Exception:
            messagebox.showwarning(APP_NAME, f"Não foi possível abrir o navegador. Acesse:\n{url}")


# ------------------------------------------------------------------ janela principal
class App(tk.Tk):
    def __init__(self, minimized: bool = False, need_login: bool = False):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1000x760")
        self.minsize(900, 660)
        apply_style(self)
        self.cfg = load_config()
        self.unlocked_until = 0.0
        self.fail_count, self.locked_until = 0, 0.0
        self.sync_q, self.upd_q = queue.Queue(), queue.Queue()
        self.syncing, self.sync_status = set(), {}
        self.last_sync_try = 0.0
        self.hosts_key, self._hosts_warned = None, False
        self.dead = False
        self.monitor = Monitor(lambda: (effective(self.cfg)["apps"], effective(self.cfg)["terms"]))
        self.protocol("WM_DELETE_WINDOW", self.request_quit)

        if need_login:
            self.withdraw()
        self.build()
        if need_login:
            if not self.auth("Abrir o EasyBlock Lite", fresh=True):
                self.dead = True
                self.destroy()
                return
            self.unlocked_until = time.time() + self.cfg["unlock_minutes"] * 60
        self.deiconify()
        if minimized:
            self.iconify()

        self.monitor.start()
        self.sync_hosts()
        self.start_sync(force=True)
        self.tick()
        if self.cfg["check_updates"]:
            self.check_update(False)

    def build(self):
        top = ttk.Frame(self, padding=(14, 12, 14, 0))
        top.pack(fill="x")
        self.active_var = tk.BooleanVar(value=self.cfg["active"])
        ttk.Checkbutton(top, text="Bloqueio ativo", variable=self.active_var,
                        command=self.toggle_active).pack(side="left")
        self.status = ttk.Label(top, text="")
        self.status.pack(side="right")

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=10)
        self.online = OnlineTab(self.nb, self)
        self.settings = SettingsTab(self.nb, self)
        self.about = AboutTab(self.nb, self)
        self.nb.add(self.online, text="☁ Bloqueio online")
        self.nb.add(self.settings, text="⚙ Configurações")
        self.nb.add(self.about, text="ℹ Sobre")
        self.support = SupportTab(self.nb, self)
        self.nb.add(self.support, text="💛 Apoie")

        bar = tk.Menu(self)
        arq = tk.Menu(bar, tearoff=False)
        arq.add_command(label="Sair", command=self.request_quit)
        bar.add_cascade(label="Arquivo", menu=arq)
        ajuda = tk.Menu(bar, tearoff=False)
        ajuda.add_command(label="Verificar atualizações", command=lambda: self.check_update(True))
        ajuda.add_command(label="💛 Apoie o projeto", command=lambda: self.nb.select(self.support))
        ajuda.add_command(label="Repositório no GitHub", command=lambda: webbrowser.open(REPO_URL))
        bar.add_cascade(label="Ajuda", menu=ajuda)
        self.config(menu=bar)

    # ---- senha
    def auth(self, reason: str, fresh: bool = False) -> bool:
        if not has_password(self.cfg):
            return True
        if not fresh and time.time() < self.unlocked_until:
            return True
        if time.time() < self.locked_until:
            messagebox.showwarning(APP_NAME, f"Muitas tentativas erradas. Aguarde "
                                             f"{int(self.locked_until - time.time()) + 1} s.")
            return False
        pw = ask_text(self, "Senha necessária", f"{reason} exige a senha.", show="•",
                      extra_label="Esqueci a senha")
        if pw is None:
            return False
        if pw == EXTRA:
            return self.recover()
        if check_password(self.cfg, pw):
            self.fail_count = 0
            self.unlocked_until = time.time() + self.cfg["unlock_minutes"] * 60
            return True
        self.fail_count += 1
        if self.fail_count >= 3:
            self.locked_until, self.fail_count = time.time() + 30, 0
        messagebox.showerror(APP_NAME, "Senha incorreta.")
        return False

    def recover(self) -> bool:
        code = ask_text(self, "Recuperar senha", "Digite o código de recuperação que você anotou:")
        if code in (None, EXTRA):
            return False
        if not check_recovery(self.cfg, code):
            messagebox.showerror(APP_NAME, "Código de recuperação incorreto.")
            return False
        clear_password(self.cfg)
        self.save()
        self.settings.refresh_pw()
        messagebox.showinfo(APP_NAME, "Senha removida. Defina uma nova em Configurações, se quiser.")
        self.unlocked_until = time.time() + self.cfg["unlock_minutes"] * 60
        return True

    def lock_now(self):
        self.unlocked_until = 0.0

    # ---- bloqueio
    def toggle_active(self):
        new = self.active_var.get()
        if not new and not self.auth("Pausar o bloqueio"):
            self.active_var.set(True)
            return
        self.cfg["active"] = new
        self.save()
        self.sync_hosts()
        self.refresh_status()

    def sync_hosts(self):
        try:
            eff = effective(self.cfg)
            apply_hosts(eff["sites"], self.cfg["active"])
            self.hosts_key = (tuple(eff["sites"]), self.cfg["active"])
        except PermissionError:
            self.hosts_key = None
            if not self._hosts_warned:
                self._hosts_warned = True
                messagebox.showerror(APP_NAME, "Sem permissão para editar o arquivo hosts. "
                                               "Execute como Administrador.")
        except Exception as e:
            log_error(f"hosts: {e}")

    def refresh_status(self):
        st = "● ATIVO" if self.cfg["active"] else "⏸ pausado"
        err = self.monitor.last_error
        self.status.config(text=f"{st} • bloqueios aplicados: {self.monitor.blocked}"
                                + (f" • ⚠ erro: {err}" if err else ""))

    def save(self):
        try:
            save_config(self.cfg)
        except OSError as e:
            log_error(f"salvar config: {e}")

    # ---- listas online
    def start_sync(self, force: bool = False):
        now = time.time()
        if not force and now - self.last_sync_try < self.cfg["interval"] * 60:
            return
        self.last_sync_try = now
        for s in self.cfg["sources"]:
            if s["enabled"] and s["url"] not in self.syncing:
                self.syncing.add(s["url"])
                self.sync_status[s["url"]] = ("run", "")
                threading.Thread(target=self._fetch_worker, args=(s["url"],), daemon=True).start()
        if hasattr(self, "online"):
            self.online.refresh()

    def _fetch_worker(self, url: str):
        try:
            self.sync_q.put((url, "ok", fetch_list(url)))
        except Exception as e:
            self.sync_q.put((url, "err", str(e)[:120] or type(e).__name__))

    def _drain_sync(self):
        changed = False
        while True:
            try:
                url, kind, payload = self.sync_q.get_nowait()
            except queue.Empty:
                break
            self.syncing.discard(url)
            s = next((x for x in self.cfg["sources"] if x["url"] == url), None)
            if s is None:
                continue  # lista removida ou trocada durante a sincronizacao
            changed = True
            if kind == "ok":
                s["cache"] = payload
                s["last_sync"] = time.strftime("%d/%m/%Y %H:%M")
                self.sync_status[url] = ("ok", "")
            else:
                log_error(f"lista {s['name']}: {payload}")
                self.sync_status[url] = ("err", payload)
        if changed:
            self.save()
            self.sync_hosts()
            self.online.refresh()

    # ---- atualizacoes
    def check_update(self, manual: bool = False):
        if manual:
            self.about.set_checking()

        def work():
            try:
                self.upd_q.put(("ok", fetch_update(), manual))
            except Exception as e:
                self.upd_q.put(("err", str(e), manual))

        threading.Thread(target=work, daemon=True).start()

    # ---- laco
    def tick(self):
        try:
            while True:
                try:
                    kind, payload, manual = self.upd_q.get_nowait()
                except queue.Empty:
                    break
                self.about.show_result(kind, payload, manual)
            self._drain_sync()
            key = (tuple(effective(self.cfg)["sites"]), self.cfg["active"])
            if key != self.hosts_key:
                self.sync_hosts()
            self.start_sync()
            self.refresh_status()
        except Exception as e:
            log_error(f"tick: {type(e).__name__}: {e}")
        self.after(1000, self.tick)

    # ---- saida
    def request_quit(self):
        if not self.auth("Sair do app"):
            return
        if self.cfg["active"] and not messagebox.askyesno(
                APP_NAME, "Ao fechar, aplicativos e termos deixam de ser bloqueados. Os sites continuam "
                          "no arquivo hosts até o app abrir de novo.\n\nFechar mesmo assim?"):
            return
        self.save()
        self.destroy()


def main(argv) -> int:
    if not IS_WIN:
        print("Este app funciona apenas no Windows.")
        return 1
    if not is_admin():
        relaunch_as_admin(argv)
        return 0
    if not acquire_instance():
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(APP_NAME, "O EasyBlock Lite já está aberto.")
        root.destroy()
        return 0
    cfg = load_config()
    app = App(minimized="--minimized" in argv, need_login=has_password(cfg))
    if app.dead:
        return 0
    app.mainloop()
    return 0


def run_safely(argv) -> int:
    try:
        return main(argv)
    except SystemExit:
        raise
    except BaseException:
        import traceback
        log_error("ERRO FATAL:\n" + traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(run_safely(sys.argv[1:]))
