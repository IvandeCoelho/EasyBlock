"""
Logica do Bloqueador (sem interface): configuracao, listas, monitoramento,
agenda, limites, historico, senha e integracao com o Windows.
"""
from __future__ import annotations

import collections
import ctypes
import hashlib
import hmac
import json
import os
import re
import shutil
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from urllib.parse import urlparse
from xml.sax.saxutils import escape

import psutil

IS_WIN = os.name == "nt"

APP_NAME = "EasyBlock"
APP_VERSION = "2.0.0"
APP_TAGLINE = "Bloqueio de sites, aplicativos e jogos para Windows"
AUTHOR = "Ivande Coelho"
REPO_URL = "https://github.com/IvandeCoelho/EasyBlock"
UPDATE_URL = ("https://raw.githubusercontent.com/IvandeCoelho/EasyBlock/"
              "refs/heads/main/version.json")
DEFAULT_REMOTE_URL = ("https://raw.githubusercontent.com/IvandeCoelho/EasyBlock/"
                      "refs/heads/main/lists/default-list.txt")
DEFAULT_SOURCE_NAME = "Lista padrão (GitHub)"

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

HOSTS_PATH = r"C:\Windows\System32\drivers\etc\hosts"
MARK_BEGIN = "# BLOQUEADOR-INICIO"
MARK_END = "# BLOQUEADOR-FIM"
_APPDATA = os.environ.get("APPDATA") or os.path.expanduser("~")
CONFIG_DIR = os.path.join(_APPDATA, "EasyBlock")
_OLD_CONFIG_DIR = os.path.join(_APPDATA, "Bloqueador")  # pasta usada ate a versao 2.0.0


def _migrate_old_dir():
    """Copia as configuracoes da pasta antiga (Bloqueador) na primeira abertura. A pasta antiga e mantida."""
    try:
        if os.path.isdir(_OLD_CONFIG_DIR) and not os.path.exists(CONFIG_DIR):
            shutil.copytree(_OLD_CONFIG_DIR, CONFIG_DIR)
    except OSError:
        pass


_migrate_old_dir()
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
CHECK_INTERVAL = 1.5  # segundos
REMOTE_MAX_BYTES = 1_000_000
WM_CLOSE = 0x0010
CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008
MUTEX_NAME = "Local\\BloqueadorSingleInstance"
TASK_LOGON = "Bloqueador-Inicio"
TASK_WATCHDOG = "Bloqueador-Guardiao"

# Processos essenciais que nunca sao encerrados (protege contra listas erradas)
PROTECTED = {"explorer.exe", "svchost.exe", "winlogon.exe", "csrss.exe", "lsass.exe",
             "services.exe", "system", "dwm.exe", "wininit.exe", "smss.exe",
             "taskmgr.exe", "cmd.exe", "powershell.exe", "python.exe", "pythonw.exe",
             "easyblock.exe", "conhost.exe", "fontdrvhost.exe", "sihost.exe",
             "registry", "system idle process", "memcompression"}

INTERVALS = [("5 minutos", 5), ("15 minutos", 15), ("30 minutos", 30),
             ("1 hora", 60), ("6 horas", 360), ("24 horas", 1440)]
DAY_NAMES = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

# Reentrante: protege config/usage compartilhados entre a interface e o monitor
CFG_LOCK = threading.RLock()

# --------------------------------------------------------------- listas prontas
PRESETS = {
    "sites": {
        "Redes sociais": [
            "facebook.com", "instagram.com", "twitter.com", "x.com", "tiktok.com",
            "kwai.com", "snapchat.com", "reddit.com", "pinterest.com", "threads.net",
        ],
        "Vídeo e streaming": [
            "youtube.com", "netflix.com", "twitch.tv", "primevideo.com",
            "disneyplus.com", "max.com", "globoplay.globo.com", "crunchyroll.com",
        ],
        "Mensagens": [
            "web.whatsapp.com", "web.telegram.org", "discord.com", "messenger.com",
        ],
        "Jogos online": [
            "roblox.com", "poki.com", "crazygames.com", "miniclip.com", "friv.com",
            "y8.com", "store.steampowered.com", "epicgames.com", "miniplay.com",
        ],
        "Apostas": [
            "bet365.com", "betano.com", "blaze.com", "stake.com", "betfair.com",
            "sportingbet.com", "pixbet.com", "esportesdasorte.com",
        ],
    },
    "apps": {
        "Plataformas de jogos": [
            "steam.exe", "steamwebhelper.exe", "EpicGamesLauncher.exe",
            "RiotClientServices.exe", "Battle.net.exe", "GOGGalaxy.exe",
            "Origin.exe", "EADesktop.exe", "UbisoftConnect.exe",
        ],
        "Jogos populares": [
            "RobloxPlayerBeta.exe", "Minecraft.Windows.exe", "javaw.exe",
            "FortniteClient-Win64-Shipping.exe", "VALORANT-Win64-Shipping.exe",
            "LeagueClient.exe", "League of Legends.exe", "cs2.exe", "GTA5.exe",
            "FreeFire.exe", "HD-Player.exe",
        ],
        "Mensagens": [
            "Discord.exe", "WhatsApp.exe", "Telegram.exe", "Skype.exe",
        ],
    },
    "terms": {
        "Jogos": ["minecraft", "fortnite", "roblox", "free fire", "valorant", "league of legends"],
        "Redes sociais": ["facebook", "instagram", "tiktok", "twitter"],
        "Apostas": ["bet365", "cassino", "tigrinho", "aposta"],
    },
}

# Categorias do assistente de primeira abertura -> listas prontas de cada tipo
WIZARD = {
    "Redes sociais": {"sites": ["Redes sociais"], "terms": ["Redes sociais"]},
    "Vídeo e streaming": {"sites": ["Vídeo e streaming"]},
    "Mensagens": {"sites": ["Mensagens"], "apps": ["Mensagens"]},
    "Jogos": {"sites": ["Jogos online"], "apps": ["Plataformas de jogos", "Jogos populares"],
              "terms": ["Jogos"]},
    "Apostas": {"sites": ["Apostas"], "terms": ["Apostas"]},
}


# ----------------------------------------------------------------- utilidades
def is_admin() -> bool:
    if not IS_WIN:
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def app_argv(extra: list | None = None) -> list:
    """Comando para reabrir este programa (exe empacotado ou script Python)."""
    extra = list(extra or [])
    if getattr(sys, "frozen", False):
        return [sys.executable] + extra
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if IS_WIN and os.path.exists(pyw):
        exe = pyw
    return [exe, os.path.abspath(sys.argv[0])] + extra


def relaunch_as_admin(extra: list | None = None):
    argv = app_argv(extra)
    ctypes.windll.shell32.ShellExecuteW(None, "runas", argv[0],
                                        subprocess.list2cmdline(argv[1:]), None, 1)


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
    if "." not in host or " " in host:
        return ""
    return host


def normalize_app(text: str) -> str:
    t = text.strip().strip('"')
    if "\\" in t or "/" in t:  # caminho completo -> so o nome do arquivo
        t = re.split(r"[\\/]", t)[-1]
    return t


def normalize_term(text: str) -> str:
    return text.strip().strip('"')


def parse_entries(text: str) -> list:
    """Separa por linha, virgula ou ponto e virgula."""
    return [p.strip() for p in re.split(r"[\n\r,;]+", text) if p.strip()]


NORMALIZERS = {"sites": normalize_site, "apps": normalize_app, "terms": normalize_term}
KEYS = ("sites", "apps", "terms")


# --------------------------------------------------------------- configuracao
def empty_lists() -> dict:
    return {k: [] for k in KEYS}


def _clean_lists(d) -> dict:
    d = d if isinstance(d, dict) else {}
    return {k: [str(x) for x in d.get(k, [])] if isinstance(d.get(k, []), list) else [] for k in KEYS}


def default_config() -> dict:
    return {
        "active": True,
        "check_updates": True,
        "first_run_done": False,
        "sites": [], "apps": [], "terms": [],
        "remote": {"interval": 30, "sources": [], "ignored": empty_lists()},
        "schedule": {"enabled": False, "rules": []},
        "limits": [],
        "usage": {"date": "", "seconds": {}},
        "security": {"salt": "", "hash": "", "recovery_hash": "", "recovery_salt": "",
                     "unlock_minutes": 5},
        "system": {"autostart": False, "watchdog": False, "block_doh": False,
                   "title_match_sites": False},
        "ui": {"theme": "claro", "font_size": 10, "close_to_tray": True, "notify": True},
    }


def _source(name, url, enabled=True, secret="", cache=None, last_sync=""):
    return {"name": name, "url": url, "enabled": bool(enabled), "secret": secret,
            "cache": _clean_lists(cache), "last_sync": last_sync}


def load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    cfg = default_config()
    cfg["active"] = bool(data.get("active", True))
    cfg["check_updates"] = bool(data.get("check_updates", True))
    cfg["first_run_done"] = bool(data.get("first_run_done", False))
    for k in KEYS:
        v = data.get(k, [])
        cfg[k] = [str(x) for x in v] if isinstance(v, list) else []

    # ---- listas online (migra o formato antigo de uma unica lista)
    r = data.get("remote") if isinstance(data.get("remote"), dict) else {}
    try:
        cfg["remote"]["interval"] = int(r.get("interval", 30))
    except (TypeError, ValueError):
        pass
    cfg["remote"]["ignored"] = _clean_lists(r.get("ignored"))
    legacy_enabled = bool(r.get("enabled", True))
    legacy_url = str(r.get("url") or DEFAULT_REMOTE_URL)
    sources = []
    for s in r.get("sources", []) if isinstance(r.get("sources"), list) else []:
        if not isinstance(s, dict) or not str(s.get("url", "")).lower().startswith("https://"):
            continue
        enabled = s["enabled"] if "enabled" in s else (legacy_enabled if s["url"] == legacy_url else False)
        sources.append(_source(str(s.get("name") or s["url"]), str(s["url"]), enabled,
                               str(s.get("secret", "")), s.get("cache"), str(s.get("last_sync", ""))))
    has_saved = isinstance(r.get("sources"), list)
    if not has_saved:  # configuracao nova ou formato antigo: cadastra a lista padrao
        if not any(s["url"] == DEFAULT_REMOTE_URL for s in sources):
            sources.insert(0, _source(DEFAULT_SOURCE_NAME, DEFAULT_REMOTE_URL,
                                      legacy_enabled if legacy_url == DEFAULT_REMOTE_URL else True))
        if not any(s["url"] == legacy_url for s in sources):
            sources.append(_source("Personalizada", legacy_url, legacy_enabled))
    elif not sources:  # o usuario removeu todas as listas: a padrao volta a ser carregada
        sources.append(_source(DEFAULT_SOURCE_NAME, DEFAULT_REMOTE_URL, True))
    legacy_cache = _clean_lists(r.get("cache"))
    for s in sources:  # cache do formato antigo vai para a lista que estava ativa
        if s["url"] == legacy_url and not any(s["cache"].values()) and any(legacy_cache.values()):
            s["cache"] = legacy_cache
            s["last_sync"] = str(r.get("last_sync", ""))
    cfg["remote"]["sources"] = sources

    # ---- agenda
    sch = data.get("schedule") if isinstance(data.get("schedule"), dict) else {}
    cfg["schedule"]["enabled"] = bool(sch.get("enabled", False))
    for rule in sch.get("rules", []) if isinstance(sch.get("rules"), list) else []:
        if isinstance(rule, dict) and parse_hhmm(rule.get("start")) is not None \
                and parse_hhmm(rule.get("end")) is not None:
            days = sorted({int(d) for d in rule.get("days", []) if str(d).isdigit() and 0 <= int(d) <= 6})
            if days:
                cfg["schedule"]["rules"].append(
                    {"days": days, "start": str(rule["start"]).strip(), "end": str(rule["end"]).strip()})

    # ---- limites de uso
    for lim in data.get("limits", []) if isinstance(data.get("limits"), list) else []:
        try:
            kind, value, minutes = str(lim["type"]), str(lim["value"]).strip(), int(lim["minutes"])
        except (KeyError, TypeError, ValueError):
            continue
        if kind in ("app", "term") and value and minutes > 0:
            cfg["limits"].append({"type": kind, "value": value, "minutes": minutes})
    u = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    secs = u.get("seconds", {}) if isinstance(u.get("seconds"), dict) else {}
    cfg["usage"] = {"date": str(u.get("date", "")),
                    "seconds": {str(k): float(v) for k, v in secs.items() if isinstance(v, (int, float))}}

    # ---- seguranca / sistema / interface
    for section in ("security", "system", "ui"):
        src = data.get(section) if isinstance(data.get(section), dict) else {}
        for k, default in cfg[section].items():
            v = src.get(k, default)
            if isinstance(default, bool):
                cfg[section][k] = bool(v) if isinstance(v, (bool, int)) else default
            elif isinstance(default, int):
                try:
                    cfg[section][k] = int(v)
                except (TypeError, ValueError):
                    cfg[section][k] = default
            else:
                cfg[section][k] = v if isinstance(v, str) else default
    cfg["security"]["unlock_minutes"] = max(1, min(120, int(cfg["security"]["unlock_minutes"] or 5)))
    cfg["ui"]["font_size"] = max(8, min(16, int(cfg["ui"]["font_size"] or 10)))
    if cfg["ui"]["theme"] not in ("claro", "escuro"):
        cfg["ui"]["theme"] = "claro"
    return cfg


def save_config(cfg: dict):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    tmp = CONFIG_PATH + ".tmp"
    with CFG_LOCK:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    os.replace(tmp, CONFIG_PATH)


def log_error(msg: str):
    """Grava erros em %APPDATA%\\EasyBlock\\easyblock.log para facilitar o diagnostico."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(os.path.join(CONFIG_DIR, "easyblock.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%d/%m/%Y %H:%M:%S ") + msg + "\n")
    except Exception:
        pass


# ------------------------------------------------------------- listas online
SECTION_ALIASES = {
    "sites": "sites", "site": "sites",
    "apps": "apps", "app": "apps", "aplicativos": "apps", "jogos": "apps",
    "terms": "terms", "termos": "terms", "term": "terms",
}
HMAC_RE = re.compile(r"^#\s*hmac:\s*([0-9a-fA-F]{64})\s*$")


def clean_remote(d: dict) -> dict:
    """Normaliza, remove duplicados e descarta itens perigosos (curtos demais)."""
    res = {}
    for key in KEYS:
        fn, seen, out = NORMALIZERS[key], set(), []
        for raw in d.get(key, []):
            v = fn(str(raw))
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


def parse_remote(text: str) -> dict:
    """Aceita JSON {"sites":[],"apps":[],"terms":[]} ou texto com secoes [sites] [apps] [termos]."""
    text = text.lstrip("\ufeff")
    raw = empty_lists()
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    if isinstance(data, dict):
        for key in raw:
            v = data.get(key, [])
            if isinstance(v, list):
                raw[key] = [str(x) for x in v]
        return clean_remote(raw)
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
    return clean_remote(raw)


def canonical_body(text: str) -> str:
    lines = [l.rstrip() for l in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(lines).rstrip("\n")


def split_signature(text: str):
    """Separa o texto da linha final '# hmac: <64 hex>'. Retorna (corpo, assinatura|None)."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    if lines:
        m = HMAC_RE.match(lines[-1].strip())
        if m:
            return "\n".join(lines[:-1]), m.group(1).lower()
    return text, None


def sign_text(body: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), canonical_body(body).encode("utf-8"),
                    hashlib.sha256).hexdigest()


def verify_signed(text: str, secret: str) -> str:
    body, sig = split_signature(text)
    if sig is None:
        raise ValueError("a lista não tem assinatura (# hmac:), mas esta lista exige uma")
    if not hmac.compare_digest(sig, sign_text(body, secret)):
        raise ValueError("assinatura inválida: a lista foi alterada ou a chave está errada")
    return body


def fetch_remote(url: str, secret: str = "") -> dict:
    if not url.lower().startswith("https://"):
        raise ValueError("O endereço precisa começar com https://")
    req = urllib.request.Request(url, headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read(REMOTE_MAX_BYTES + 1)
    if len(data) > REMOTE_MAX_BYTES:
        raise ValueError("Arquivo grande demais (máx. 1 MB)")
    text = data.decode("utf-8-sig", errors="replace")
    if secret:
        text = verify_signed(text, secret)
    return parse_remote(text)


def effective(cfg: dict, now=None) -> dict:
    """Lista local + listas online ativas (menos os itens ignorados).
    'active' fica False se o bloqueio estiver pausado ou fora do horario da agenda."""
    out = dict(cfg)
    out["scheduled"] = in_schedule(cfg, now)
    out["active"] = bool(cfg["active"]) and out["scheduled"]
    ignored = cfg["remote"].get("ignored", {})
    for key in KEYS:
        merged = list(cfg[key])
        seen = {x.lower() for x in merged}
        skip = {x.lower() for x in ignored.get(key, [])}
        for src in cfg["remote"]["sources"]:
            if not src.get("enabled"):
                continue
            for x in src["cache"].get(key, []):
                if x.lower() not in seen and x.lower() not in skip:
                    merged.append(x)
                    seen.add(x.lower())
        out[key] = merged
    return out


# --------------------------------------------------------------------- agenda
def parse_hhmm(s):
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", str(s or ""))
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    return h * 60 + mi if h < 24 and mi < 60 else None


def in_schedule(cfg: dict, now=None) -> bool:
    """True se o bloqueio deve valer agora (sem agenda ativa => sempre)."""
    sch = cfg.get("schedule", {})
    if not sch.get("enabled") or not sch.get("rules"):
        return True
    now = now or time.localtime()
    wd, t = now.tm_wday, now.tm_hour * 60 + now.tm_min
    for r in sch["rules"]:
        s, e, days = parse_hhmm(r.get("start")), parse_hhmm(r.get("end")), set(r.get("days", []))
        if s is None or e is None:
            continue
        if s == e:
            if wd in days:
                return True
        elif s < e:
            if wd in days and s <= t < e:
                return True
        elif (wd in days and t >= s) or (((wd - 1) % 7) in days and t < e):
            return True
    return False


def rule_text(rule: dict) -> str:
    days = rule.get("days", [])
    if days == [0, 1, 2, 3, 4]:
        d = "Seg–Sex"
    elif days == [5, 6]:
        d = "Sáb–Dom"
    elif len(days) == 7:
        d = "Todos os dias"
    else:
        d = ", ".join(DAY_NAMES[i] for i in days)
    return f"{d}  {rule['start']}–{rule['end']}"


# ------------------------------------------------------------------- historico
class History:
    """Registro de bloqueios (arquivo JSON por linha + fila para a interface)."""
    MAX_FILE = 1_000_000

    def __init__(self):
        self.lock = threading.Lock()
        self.pending = collections.deque(maxlen=500)

    @property
    def path(self):
        return os.path.join(CONFIG_DIR, "historico.jsonl")

    def add(self, kind: str, item: str) -> dict:
        rec = {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "kind": kind, "item": item}
        with self.lock:
            try:
                os.makedirs(CONFIG_DIR, exist_ok=True)
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            except OSError:
                pass
            self.pending.append(rec)
        return rec

    def drain(self) -> list:
        with self.lock:
            out = list(self.pending)
            self.pending.clear()
        return out

    def load(self, n: int = 500) -> list:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError:
            return []
        if os.path.getsize(self.path) > self.MAX_FILE:
            lines = lines[-1000:]
            try:
                with open(self.path, "w", encoding="utf-8") as f:
                    f.writelines(lines)
            except OSError:
                pass
        out = []
        for line in lines[-n:]:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
        return out

    def clear(self):
        with self.lock:
            try:
                open(self.path, "w").close()
            except OSError:
                pass
            self.pending.clear()


# ----------------------------------------------------------------- monitoramento
if IS_WIN:
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    # tipos explicitos: evitam truncar handles de 64 bits
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
    kernel32.OpenMutexW.restype = wintypes.HANDLE
    kernel32.OpenMutexW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
else:
    user32 = kernel32 = None


def visible_windows() -> list:
    """Retorna lista de (hwnd, titulo, pid) das janelas visiveis."""
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


def close_window(hwnd):
    if IS_WIN:
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)


def app_matches(entry: str, proc_name: str) -> bool:
    entry, proc_name = entry.lower(), proc_name.lower()
    if entry.endswith(".exe"):
        return proc_name == entry
    return entry in proc_name


def site_title_terms(sites: list) -> list:
    """'youtube.com' -> 'youtube' (nome do site para procurar em titulos de janela)."""
    out = []
    for s in sites:
        parts = s.lower().split(".")
        if len(parts) < 2:
            continue
        label = parts[-2]
        if label in ("com", "net", "org", "gov", "edu") and len(parts) >= 3:
            label = parts[-3]
        if len(label) >= 4 and label not in out:
            out.append(label)
    return out


class Monitor(threading.Thread):
    def __init__(self, get_cfg, history: History | None = None):
        super().__init__(daemon=True)
        self.get_cfg = get_cfg
        self.history = history
        self.my_pid = os.getpid()
        self.blocked_count = 0
        self.last_error = ""
        self.usage_dirty = False
        self._seen = {}
        self._last_tick = time.time()

    def run(self):
        while True:
            try:
                cfg = self.get_cfg()
                if cfg["active"]:
                    self.sweep(cfg)
                else:
                    self._last_tick = time.time()
                self.last_error = ""
            except Exception as e:
                msg = f"{type(e).__name__}: {e}"
                if msg != self.last_error:
                    log_error("monitor: " + msg)
                self.last_error = msg
            time.sleep(CHECK_INTERVAL)

    # ---- helpers
    def _event(self, kind: str, item: str):
        now = time.time()
        key = (kind, item)
        if now - self._seen.get(key, 0) < 30:
            return
        self._seen[key] = now
        if self.history:
            self.history.add(kind, item)

    def _kill(self, proc, name, kind="app"):
        try:
            proc.kill()
            self.blocked_count += 1
            self._event(kind, name)
        except Exception:
            pass

    def _close(self, hwnd, kind, item):
        close_window(hwnd)
        self.blocked_count += 1
        self._event(kind, item)

    # ---- varredura
    def sweep(self, cfg):
        apps = [a.lower() for a in cfg["apps"]]
        terms = [t.lower() for t in cfg["terms"]]
        site_terms = site_title_terms(cfg["sites"]) if cfg.get("system", {}).get("title_match_sites") else []
        limits = cfg.get("limits", [])
        need_windows = bool(terms or site_terms or any(l["type"] == "term" for l in limits))

        procs = []
        for p in psutil.process_iter(["name", "pid"]):
            name = p.info["name"] or ""
            if p.info["pid"] == self.my_pid or name.lower() in PROTECTED:
                continue
            procs.append((p, name))
        windows = visible_windows() if need_windows else []

        # 1) bloqueios fixos
        if apps or terms:
            for p, name in procs:
                low = name.lower()
                if any(app_matches(a, name) for a in apps):
                    self._kill(p, name, "app")
                elif any(t in low for t in terms):
                    self._kill(p, name, "termo")
        for hwnd, title, pid in windows:
            if pid == self.my_pid:
                continue
            low = title.lower()
            hit = next((t for t in terms if t in low), None)
            if hit:
                self._close(hwnd, "janela", f"{hit} — {title[:70]}")
                continue
            hit = next((t for t in site_terms if t in low), None)
            if hit:
                self._close(hwnd, "site", f"{hit} — {title[:70]}")

        # 2) limites diarios
        if limits:
            self._limits(cfg, procs, windows)
        self._last_tick = time.time()

    def _limits(self, cfg, procs, windows):
        now = time.time()
        dt = max(0.0, min(now - self._last_tick, 5.0))
        usage, today = cfg["usage"], time.strftime("%Y-%m-%d")
        with CFG_LOCK:
            if usage.get("date") != today:
                usage["date"], usage["seconds"] = today, {}
                self.usage_dirty = True
        for lim in cfg["limits"]:
            kind, value, cap = lim["type"], lim["value"], lim["minutes"] * 60
            key = f"{kind}:{value.lower()}"
            if kind == "app":
                hits = [(p, n) for p, n in procs if app_matches(value, n)]
                wins = []
            else:
                v = value.lower()
                hits = []
                wins = [w for w in windows if v in w[1].lower() and w[2] != self.my_pid]
            if not hits and not wins:
                continue
            used = usage["seconds"].get(key, 0.0)
            if used >= cap:
                for p, n in hits:
                    self._kill(p, n, "limite")
                for hwnd, title, _ in wins:
                    self._close(hwnd, "limite", f"{value} — limite de {lim['minutes']} min")
            else:
                with CFG_LOCK:
                    usage["seconds"][key] = used + dt
                self.usage_dirty = True


def list_programs(only_windows: bool = True) -> list:
    """Programas em execucao: lista de (nome_do_exe, titulo_da_janela)."""
    titles = {}
    for _hwnd, title, pid in visible_windows():
        titles.setdefault(pid, title)
    rows = {}
    for p in psutil.process_iter(["name", "pid"]):
        name = p.info["name"] or ""
        if not name or name.lower() in PROTECTED or p.info["pid"] == os.getpid():
            continue
        title = titles.get(p.info["pid"], "")
        if only_windows and not title:
            continue
        cur = rows.get(name.lower())
        if cur is None or (title and not cur[1]):
            rows[name.lower()] = (name, title)
    return sorted(rows.values(), key=lambda r: r[0].lower())


# ---------------------------------------------------------------------- hosts
def _read_hosts() -> list:
    with open(HOSTS_PATH, "r", encoding="utf-8", errors="replace") as f:
        return f.read().splitlines()


def _strip_block(lines: list) -> list:
    out, inside = [], False
    for line in lines:
        if line.strip() == MARK_BEGIN:
            inside = True
            continue
        if line.strip() == MARK_END:
            inside = False
            continue
        if not inside:
            out.append(line)
    while out and not out[-1].strip():
        out.pop()
    return out


def apply_hosts(sites: list, active: bool):
    old = _read_hosts()
    lines = _strip_block(old)
    if active and sites:
        lines.append("")
        lines.append(MARK_BEGIN)
        for s in sites:
            lines.append(f"127.0.0.1 {s}")
            lines.append(f"127.0.0.1 www.{s}")
            lines.append(f"::1 {s}")
            lines.append(f"::1 www.{s}")
        lines.append(MARK_END)
    if "\n".join(lines).rstrip() == "\n".join(old).rstrip():
        return  # nada mudou
    with open(HOSTS_PATH, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\n".join(lines) + "\n")
    try:
        subprocess.run(["ipconfig", "/flushdns"], capture_output=True,
                       creationflags=CREATE_NO_WINDOW if IS_WIN else 0)
    except OSError:
        pass


# ----------------------------------------------------------------------- senha
def _pbkdf2(pw: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, 200_000).hex()


def has_password(cfg: dict) -> bool:
    return bool(cfg["security"].get("hash"))


def set_password(cfg: dict, pw: str) -> str:
    """Define a senha e devolve um codigo de recuperacao (mostrado uma unica vez)."""
    sec = cfg["security"]
    salt = secrets.token_bytes(16)
    sec["salt"], sec["hash"] = salt.hex(), _pbkdf2(pw, salt)
    code = "-".join(secrets.token_hex(2).upper() for _ in range(3))
    rsalt = secrets.token_bytes(16)
    sec["recovery_salt"], sec["recovery_hash"] = rsalt.hex(), _pbkdf2(code, rsalt)
    return code


def check_password(cfg: dict, pw: str) -> bool:
    sec = cfg["security"]
    if not sec.get("hash"):
        return True
    return hmac.compare_digest(_pbkdf2(pw, bytes.fromhex(sec["salt"])), sec["hash"])


def check_recovery(cfg: dict, code: str) -> bool:
    sec = cfg["security"]
    if not sec.get("recovery_hash"):
        return False
    code = code.strip().upper()
    return hmac.compare_digest(_pbkdf2(code, bytes.fromhex(sec["recovery_salt"])), sec["recovery_hash"])


def clear_password(cfg: dict):
    sec = cfg["security"]
    sec["salt"] = sec["hash"] = sec["recovery_salt"] = sec["recovery_hash"] = ""


# ------------------------------------------- integracao com o Windows (tarefas)
def stop_flag_path() -> str:
    return os.path.join(CONFIG_DIR, "parado.flag")


def set_stop_flag():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    open(stop_flag_path(), "w").close()


def clear_stop_flag():
    try:
        os.remove(stop_flag_path())
    except OSError:
        pass


def stop_flag_set() -> bool:
    return os.path.exists(stop_flag_path())


def task_xml(command: str, arguments: str, trigger: str, description: str = "") -> str:
    user = (os.environ.get("USERDOMAIN", "") + "\\" if os.environ.get("USERDOMAIN") else "") \
        + os.environ.get("USERNAME", "")
    uid = f"<UserId>{escape(user)}</UserId>" if user.strip("\\") else ""
    if trigger == "logon":
        trig = f"<LogonTrigger><Enabled>true</Enabled>{uid}</LogonTrigger>"
    else:  # a cada minuto
        trig = ("<TimeTrigger><Repetition><Interval>PT1M</Interval>"
                "<StopAtDurationEnd>false</StopAtDurationEnd></Repetition>"
                "<StartBoundary>2020-01-01T00:00:00</StartBoundary><Enabled>true</Enabled></TimeTrigger>")
    return (
        '<?xml version="1.0" encoding="UTF-16"?>\n'
        '<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">'
        f"<RegistrationInfo><Description>{escape(description)}</Description></RegistrationInfo>"
        f"<Triggers>{trig}</Triggers>"
        f'<Principals><Principal id="Author">{uid}<LogonType>InteractiveToken</LogonType>'
        "<RunLevel>HighestAvailable</RunLevel></Principal></Principals>"
        "<Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>"
        "<DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>"
        "<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>"
        "<AllowHardTerminate>true</AllowHardTerminate><StartWhenAvailable>true</StartWhenAvailable>"
        "<ExecutionTimeLimit>PT0S</ExecutionTimeLimit><Enabled>true</Enabled></Settings>"
        f'<Actions Context="Author"><Exec><Command>{escape(command)}</Command>'
        f"<Arguments>{escape(arguments)}</Arguments></Exec></Actions></Task>"
    )


def _schtasks(args: list) -> tuple:
    if not IS_WIN:
        return False, "Disponível apenas no Windows."
    r = subprocess.run(["schtasks"] + args, capture_output=True, text=True,
                       creationflags=CREATE_NO_WINDOW)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def task_exists(name: str) -> bool:
    return _schtasks(["/Query", "/TN", name])[0]


def create_task(name: str, trigger: str, extra_args: list, description: str) -> tuple:
    argv = app_argv(extra_args)
    xml = task_xml(argv[0], subprocess.list2cmdline(argv[1:]), trigger, description)
    os.makedirs(CONFIG_DIR, exist_ok=True)
    path = os.path.join(tempfile.mkdtemp(prefix="bloq_"), "task.xml")
    with open(path, "w", encoding="utf-16") as f:
        f.write(xml)
    try:
        return _schtasks(["/Create", "/TN", name, "/XML", path, "/F"])
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def delete_task(name: str) -> tuple:
    if not task_exists(name):
        return True, ""
    return _schtasks(["/Delete", "/TN", name, "/F"])


def set_autostart(enable: bool) -> tuple:
    if enable:
        return create_task(TASK_LOGON, "logon", ["--minimized"], "Inicia o Bloqueador ao entrar no Windows")
    return delete_task(TASK_LOGON)


def set_watchdog(enable: bool) -> tuple:
    if enable:
        return create_task(TASK_WATCHDOG, "minute", ["--watchdog"],
                           "Reabre o Bloqueador se ele for encerrado")
    return delete_task(TASK_WATCHDOG)


# ---- instancia unica / guardiao
_mutex_handle = None


def instance_running() -> bool:
    """True se outra instancia do app esta aberta."""
    if not IS_WIN:
        return False
    h = kernel32.OpenMutexW(0x00100000, False, MUTEX_NAME)
    if h:
        kernel32.CloseHandle(h)
        return True
    return False


def acquire_instance() -> bool:
    """Reserva a instancia unica. False se ja existe outra."""
    global _mutex_handle
    if not IS_WIN:
        return True
    _mutex_handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS


def run_watchdog() -> bool:
    """Reabre o app se ele nao estiver rodando (e nao tiver sido encerrado de proposito)."""
    if stop_flag_set() or instance_running():
        return False
    argv = app_argv(["--minimized"])
    subprocess.Popen(argv, creationflags=(DETACHED_PROCESS | CREATE_NO_WINDOW) if IS_WIN else 0,
                     close_fds=True)
    return True


# ------------------------------------------------- DNS seguro dos navegadores
DOH_POLICIES = [
    (r"SOFTWARE\Policies\Google\Chrome", "DnsOverHttpsMode", "off"),
    (r"SOFTWARE\Policies\Microsoft\Edge", "DnsOverHttpsMode", "off"),
    (r"SOFTWARE\Policies\Mozilla\Firefox\DNSOverHTTPS", "Enabled", 0),
    (r"SOFTWARE\Policies\BraveSoftware\Brave", "DnsOverHttpsMode", "off"),
]


def set_doh_block(enable: bool) -> list:
    """Desliga/restaura o DNS seguro (que ignora o arquivo hosts). Retorna lista de erros."""
    if not IS_WIN:
        return ["Disponível apenas no Windows."]
    import winreg
    errors = []
    for path, name, value in DOH_POLICIES:
        try:
            if enable:
                with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_SET_VALUE) as k:
                    if isinstance(value, int):
                        winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, value)
                    else:
                        winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)
            else:
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_SET_VALUE) as k:
                        winreg.DeleteValue(k, name)
                except FileNotFoundError:
                    pass
        except OSError as e:
            errors.append(f"{path}: {e}")
    return errors


# ------------------------------------------------------------ atualizacao do app
def version_tuple(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v)) or (0,)


def fetch_update() -> dict:
    req = urllib.request.Request(UPDATE_URL, headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read(100_000)
    info = json.loads(data.decode("utf-8-sig", errors="replace"))
    download = str(info.get("download") or REPO_URL + "/releases")
    if not download.lower().startswith("https://"):
        download = REPO_URL + "/releases"
    return {"version": str(info["version"]), "download": download,
            "notes": str(info.get("notes", "")),
            "download_exe": str(info.get("download_exe", "")),
            "sha256": str(info.get("sha256", "")).lower()}


def can_self_update(info: dict) -> bool:
    return bool(IS_WIN and getattr(sys, "frozen", False)
                and info.get("download_exe", "").lower().startswith("https://")
                and re.fullmatch(r"[0-9a-f]{64}", info.get("sha256", "")))


def download_update(info: dict, progress=None, allow_http: bool = False) -> str:
    """Baixa o novo executavel e confere o SHA-256 (obrigatorio). Retorna o caminho do arquivo."""
    url, expected = info.get("download_exe", ""), info.get("sha256", "")
    if not (url.lower().startswith("https://") or (allow_http and url.lower().startswith("http://"))):
        raise ValueError("endereço de download inválido (precisa ser https://)")
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("a versão não informa o SHA-256; atualização automática recusada")
    os.makedirs(CONFIG_DIR, exist_ok=True)
    dest = os.path.join(CONFIG_DIR, "EasyBlock_novo.exe")
    h, total = hashlib.sha256(), 0
    req = urllib.request.Request(url, headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"})
    with urllib.request.urlopen(req, timeout=30) as resp, open(dest, "wb") as out:
        size = int(resp.headers.get("Content-Length") or 0)
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            total += len(chunk)
            if total > 200 * 1024 * 1024:
                raise ValueError("arquivo grande demais")
            h.update(chunk)
            out.write(chunk)
            if progress and size:
                progress(total / size)
    if h.hexdigest() != expected:
        os.remove(dest)
        raise ValueError("SHA-256 do arquivo baixado não confere; atualização cancelada")
    return dest


def apply_update(new_path: str, current_path: str | None = None) -> str:
    """Troca o exe depois que este processo fechar e reabre o app. Retorna o caminho do .bat."""
    current = current_path or sys.executable
    bat = os.path.join(CONFIG_DIR, "atualizar.bat")
    script = (
        "@echo off\r\n"
        f'for /l %%i in (1,1,30) do (\r\n'
        f'  move /y "{new_path}" "{current}" >nul 2>&1 && goto ok\r\n'
        "  ping 127.0.0.1 -n 2 >nul\r\n"
        ")\r\n"
        "exit /b 1\r\n"
        ":ok\r\n"
        f'start "" "{current}" --minimized\r\n'
        'del "%~f0"\r\n'
    )
    with open(bat, "w", encoding="mbcs" if IS_WIN else "utf-8", newline="") as f:
        f.write(script)
    if IS_WIN:
        subprocess.Popen(["cmd", "/c", bat], creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
                         close_fds=True)
    return bat
