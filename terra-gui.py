#!/usr/bin/env python3
"""terra-gui - app con botones para el servidor de Terraria.

Linux: usa el CLI 'terra' (systemd + playit del sistema).
Windows: controla TerrariaServer.exe de la carpeta del paquete.
"""
import platform
import re
import socket
import subprocess
import os
import shlex
import shutil
import sys
import urllib.request
import threading
import time
import webbrowser
from pathlib import Path

import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk

# ---------------- sistema de diseño ----------------
BG = "#151521"
SURFACE = "#1e1e2e"
PANEL = "#181825"          # alias de compatibilidad
BORDER = "#2a2a3d"
FG = "#e6e6f0"
DIM = "#9a9ab0"
ACCENT = "#7c8cff"
GREEN = "#7ee0a1"
RED = "#ff7a90"
YELLOW = "#f5d76e"
BLUE = "#7c8cff"           # alias
BTN = "#2a2a3d"            # alias

FONT_FAMILY = "TkDefaultFont"
FONT = ("TkDefaultFont", 10)
FONT_B = ("TkDefaultFont", 10, "bold")


def setup_fonts(root):
    global FONT_FAMILY, FONT, FONT_B
    try:
        families = set(tkfont.families(root))
    except Exception:
        families = set()
    for name in ("Segoe UI", "Inter", "Helvetica", "DejaVu Sans"):
        if name in families:
            FONT_FAMILY = name
            break
    FONT = (FONT_FAMILY, 10)
    FONT_B = (FONT_FAMILY, 10, "bold")


def setup_styles(root):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=FG, font=FONT)
    style.configure("Card.TLabel", background=SURFACE, foreground=FG, font=FONT)
    style.configure("Title.TLabel", background=BG, foreground=FG, font=(FONT_FAMILY, 22, "bold"))
    style.configure("Subtitle.TLabel", background=BG, foreground=DIM, font=FONT)
    style.configure("Section.TLabel", background=SURFACE, foreground=FG, font=(FONT_FAMILY, 12, "bold"))
    style.configure("Hint.TLabel", background=SURFACE, foreground=DIM, font=(FONT_FAMILY, 9))

    # botones: primario, secundario y peligro
    style.configure("Primary.TButton", background=ACCENT, foreground="#151521",
                    font=FONT_B, padding=(15, 9), borderwidth=0, relief="flat")
    style.map("Primary.TButton",
              background=[("disabled", "#3a3a55"), ("pressed", "#6575e6"), ("active", "#93a0ff")],
              foreground=[("disabled", "#8a8aa0"), ("pressed", "#151521"), ("active", "#151521")])
    style.configure("Secondary.TButton", background=BTN, foreground=FG,
                    font=FONT, padding=(15, 9), borderwidth=0, relief="flat")
    style.map("Secondary.TButton",
              background=[("disabled", "#20202e"), ("pressed", "#20202e"), ("active", "#353550")],
              foreground=[("disabled", "#6f6f88"), ("pressed", FG), ("active", FG)])
    style.configure("Danger.TButton", background=SURFACE, foreground=RED,
                    font=FONT, padding=(15, 9), borderwidth=0, relief="flat")
    style.map("Danger.TButton",
              background=[("disabled", SURFACE), ("pressed", "#2a1a24"), ("active", "#3a2230")],
              foreground=[("disabled", "#7a4a58"), ("pressed", RED), ("active", RED)])

    # campos
    style.configure("Dark.TCombobox", fieldbackground=PANEL, background=PANEL,
                    foreground=FG, arrowcolor=FG, bordercolor=BORDER,
                    lightcolor=PANEL, darkcolor=PANEL, insertcolor=FG, padding=6)
    style.map("Dark.TCombobox",
              fieldbackground=[("readonly", PANEL), ("focus", PANEL), ("active", PANEL)],
              foreground=[("readonly", FG)],
              arrowcolor=[("active", ACCENT), ("!active", FG)])
    style.configure("Dark.TEntry", fieldbackground=PANEL, foreground=FG,
                    bordercolor=BORDER, lightcolor=PANEL, darkcolor=PANEL,
                    insertcolor=FG, padding=6)
    style.map("Dark.TEntry",
              bordercolor=[("focus", ACCENT)],
              lightcolor=[("focus", ACCENT)],
              darkcolor=[("focus", ACCENT)])
    style.configure("Dark.TCheckbutton", background=SURFACE, foreground=FG,
                    font=FONT, focuscolor=ACCENT)
    style.map("Dark.TCheckbutton",
              background=[("active", SURFACE)],
              foreground=[("active", FG)],
              indicatorcolor=[("selected", ACCENT), ("!selected", PANEL)])
    style.configure("Dark.Vertical.TScrollbar", background=PANEL, troughcolor=BG,
                    bordercolor=BG, arrowcolor=FG, darkcolor=PANEL, lightcolor=PANEL)

    root.option_add("*TCombobox*Listbox.background", SURFACE)
    root.option_add("*TCombobox*Listbox.foreground", FG)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", "#151521")


SEEDS = {
    "1": "Normal", "2": "Not the Bees", "3": "Drunk", "4": "Celebration Mk 10",
    "5": "The Constant", "6": "For the Worthy", "7": "No Traps", "8": "Remix",
    "9": "Zenith", "10": "Skyblock",
}


def open_browser(url):
    try:
        webbrowser.open(url)
        return True
    except Exception:
        return False


def port_open(port, host="127.0.0.1", timeout=0.6):
    """True si algo escucha en el puerto. No abre una conexión: el servidor de
    Terraria se cae si un cliente se conecta y se cierra de golpe."""
    port = int(port)
    try:
        if platform.system() == "Linux":
            out = subprocess.run(["ss", "-lnt"], capture_output=True, text=True, timeout=3).stdout
            return any(re.search(rf":{port}\s", line) for line in out.splitlines())
        if platform.system() == "Darwin":
            out = subprocess.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
                                 capture_output=True, text=True, timeout=3).stdout
            return bool(out.strip())
        if platform.system() == "Windows":
            out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=5).stdout
            return any(re.search(rf":{port}\s.*LISTENING", line, re.I) for line in out.splitlines())
    except Exception:
        pass
    # Alternativa: intentar reservar el puerto (no lo conecta).
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", port))
        return False
    except OSError:
        return True
    finally:
        sock.close()


def app_base():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def data_root(base):
    """Carpeta de datos: .dependencias/ (oculta) o dependencias/ en el paquete."""
    base = Path(base)
    for name in (".dependencias", "dependencias"):
        dep = base / name
        if dep.is_dir():
            return dep
    return base


# ---------------- backend Windows ----------------
class WinBackend:
    """Controla el TerrariaServer.exe del paquete portable."""

    SEEDS = SEEDS

    def __init__(self, base):
        self.base = Path(base)
        self.data_dir = getattr(self, "data_dir", self.base)
        self.win_dir = self.base / "server" / "Windows"
        self.exe = self.win_dir / "TerrariaServer.exe"
        self.worlds_dir = self.data_dir / "worlds"
        self.meta_file = self.data_dir / "meta.json"
        self.tunnel_file = self.data_dir / "playit" / "tunnel.txt"
        self.log_file = self.data_dir / "server.log"
        self.proc = None
        self.worlds_dir.mkdir(parents=True, exist_ok=True)

    # config
    def cfg(self):
        values = {"WORLD_NAME": "mundo", "PORT": "7777", "PLAYERS": "8",
                  "PASSWORD": "", "AUTOCREATE": "1"}
        f = self.data_dir / "config.bat"
        if f.exists():
            for line in f.read_text(errors="ignore").splitlines():
                m = re.search(r'set\s+"([^=]+)=([^"]*)"', line)
                if m:
                    values[m.group(1)] = m.group(2)
        return values

    def set_cfg(self, key, value):
        cfg = self.cfg()
        cfg[key] = str(value)
        lines = ["@echo off", 'rem Configuracion del servidor portatil (Windows)']
        for k, v in cfg.items():
            lines.append(f'set "{k}={v}"')
        if cfg.get("PASSWORD"):
            lines.append('if not "%PASSWORD%"=="" set "PASSWORDARG=-password %PASSWORD%"')
        (self.data_dir / "config.bat").write_text("\n".join(lines) + "\n")

    # mundos
    def list_worlds(self):
        return sorted(p.stem for p in self.worlds_dir.glob("*.wld"))

    def world_path(self, name):
        return self.worlds_dir / f"{name}.wld"

    def load_meta(self):
        import json
        if self.meta_file.exists():
            try:
                return json.loads(self.meta_file.read_text())
            except Exception:
                return {}
        return {}

    def save_meta(self, meta):
        import json
        self.meta_file.write_text(json.dumps(meta, indent=2, ensure_ascii=False))

    # estado
    def _running(self):
        return self.proc is not None and self.proc.poll() is None

    def status(self):
        cfg = self.cfg()
        port = int(cfg.get("PORT", "7777"))
        return {
            "server": self._running(),
            "playit": bool(self.tunnel_addr()),
            "port": port_open(port),
            "world": Path(self.world_path(cfg.get("WORLD_NAME", "mundo"))).name,
            "portnum": str(port),
        }

    def log_lines(self, n=40):
        if not self.log_file.exists():
            return "sin registro"
        return "".join(self.log_file.read_text(errors="ignore").splitlines(True)[-n:])

    def tunnel_addr(self):
        try:
            txt = self.tunnel_file.read_text().strip()
            return txt or None
        except OSError:
            return None

    # acciones
    def start(self, wait=True):
        cfg = self.cfg()
        if self._running():
            return True
        world = self.world_path(cfg.get("WORLD_NAME", "mundo"))
        args = [str(self.exe), "-world", str(world), "-port", cfg.get("PORT", "7777"),
                "-maxplayers", cfg.get("PLAYERS", "8")]
        if cfg.get("PASSWORD"):
            args += ["-password", cfg["PASSWORD"]]
        if not world.exists():
            args += ["-autocreate", cfg.get("AUTOCREATE", "1"),
                     "-worldname", cfg.get("WORLD_NAME", "mundo")]
        fh = open(self.log_file, "a", errors="ignore")
        self.proc = subprocess.Popen(args, cwd=str(self.win_dir), stdin=subprocess.DEVNULL,
                                     stdout=fh, stderr=subprocess.STDOUT)
        if wait:
            for _ in range(180):
                if port_open(int(cfg.get("PORT", "7777"))):
                    return True
                time.sleep(1)
        return True

    def stop(self):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.proc = None
        return True

    def use_world(self, name, restart=True):
        if not self.world_path(name).exists():
            return False
        self.set_cfg("WORLD_NAME", name)
        if restart:
            self.stop()
            self.start()
        return True

    def create_world(self, name, size, diff, evil, seed, specials):
        """Crea el mundo con el asistente del servidor: permite semilla libre,
        maldad y semillas especiales. El mundo queda en worlds/."""
        cfg = self.cfg()
        target = self.world_path(name)
        if target.exists():
            target.unlink()
        self.stop()
        conf = self.data_dir / "creacion.conf"
        worldpath = str(self.worlds_dir)
        if platform.system() != "Windows":
            worldpath = worldpath.replace("\\", "/")
        conf.write_text(f"worldpath={worldpath}\n")
        answers = ["n", str(size), str(diff), str(evil), name, seed or ""]
        answers += [str(x) for x in specials]
        answers += ["", cfg.get("PORT", "7777"), cfg.get("PASSWORD", ""), cfg.get("PLAYERS", "8"), "n"]
        log = self.data_dir / "creacion.log"
        fh = open(log, "w", errors="ignore")
        env = os.environ.copy()
        if platform.system() == "Linux":
            env["LD_LIBRARY_PATH"] = str(self.win_dir / "lib64") + os.pathsep + env.get("LD_LIBRARY_PATH", "")
            env["MONO_IOMAP"] = "all"
        kwargs = {"cwd": str(self.win_dir), "stdin": subprocess.PIPE, "stdout": fh,
                  "stderr": subprocess.STDOUT, "text": True, "env": env}
        if platform.system() == "Windows":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.Popen([str(self.exe), "-config", str(conf)], **kwargs)
        try:
            proc.stdin.write("\n".join(answers) + "\n")
            proc.stdin.flush()
            proc.stdin.close()
        except Exception:
            pass
        stable, prev, t0 = 0, -1, time.time()
        while time.time() - t0 < 1800:
            time.sleep(1)
            if target.exists():
                sz = target.stat().st_size
                if sz == prev and sz > 1000:
                    stable += 1
                else:
                    stable = 0
                prev = sz
                if stable >= 5:
                    break
            if proc.poll() is not None and target.exists() and target.stat().st_size > 1000:
                break
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        conf.unlink(missing_ok=True)
        if not target.exists():
            # Por si el servidor ignoró worldpath: buscar en las carpetas habituales.
            for candidate in (
                Path.home() / ".local/share/Terraria/Worlds" / f"{name}.wld",
                Path.home() / "Documents" / "My Games" / "Terraria" / "Worlds" / f"{name}.wld",
            ):
                if candidate.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(candidate), str(target))
                    break
        if not target.exists():
            return False
        meta = self.load_meta()
        meta[name] = {
            "size": {"1": "pequeño", "2": "mediano", "3": "grande"}.get(size, size),
            "difficulty": {"1": "clásico", "2": "experto", "3": "maestro", "4": "viaje"}.get(diff, diff),
            "evil": {"1": "aleatoria", "2": "corrupción", "3": "carmesí"}.get(evil, evil),
            "seed": seed or "aleatoria",
            "special": ", ".join(SEEDS.get(str(x), str(x)) for x in specials) or "ninguna",
        }
        self.save_meta(meta)
        return True


class PortableBackend(WinBackend):
    """Backend que usa los binarios y datos que viajan junto a la app."""

    def __init__(self, base):
        self.base = Path(base)
        self.data_dir = data_root(self.base)
        super().__init__(base)
        system = platform.system()
        if system == "Windows":
            self.win_dir = self.data_dir / "server" / "Windows"
            self.exe = self.win_dir / "TerrariaServer.exe"
        elif system == "Linux":
            self.win_dir = self.data_dir / "server" / "Linux"
            arch = platform.machine().lower()
            binary = "TerrariaServer.bin.x86_64" if arch in ("x86_64", "amd64") else "TerrariaServer.bin.arm64"
            self.exe = self.win_dir / binary
        elif system == "Darwin":
            self.win_dir = self.data_dir / "server" / "Mac" / "Terraria Server.app" / "Contents" / "MacOS"
            self.exe = self.win_dir / "TerrariaServer"
        else:
            raise RuntimeError(f"Sistema operativo no compatible: {system}.")
        self.log_file = self.data_dir / "server.log"
        self.tunnel_file = self.data_dir / "playit" / "tunnel.txt"

    def cfg(self):
        if platform.system() == "Windows":
            return super().cfg()
        values = {"WORLD_NAME": "mundo", "PORT": "7777", "PLAYERS": "8",
                  "PASSWORD": "", "AUTOCREATE": "1"}
        f = self.data_dir / "config.env"
        if f.exists():
            for line in f.read_text(errors="ignore").splitlines():
                match = re.match(r"\s*([A-Z_]+)\s*=\s*(.*?)\s*(?:#.*)?$", line)
                if match:
                    try:
                        parsed = shlex.split(match.group(2), comments=True)
                        values[match.group(1)] = parsed[0] if parsed else ""
                    except ValueError:
                        continue
        return values

    def set_cfg(self, key, value):
        if platform.system() == "Windows":
            return super().set_cfg(key, value)
        cfg = self.cfg()
        cfg[key] = str(value)
        lines = ["# Terraria portable app settings"]
        for name, val in cfg.items():
            escaped = str(val).replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{name}="{escaped}"')
        (self.data_dir / "config.env").write_text("\n".join(lines) + "\n")

    def start(self, wait=True):
        cfg = self.cfg()
        if self._running():
            return True
        if not self.exe.is_file():
            raise RuntimeError(f"No encuentro el servidor de Terraria para {platform.system()} en {self.win_dir}.")
        if port_open(cfg.get("PORT", "7777")):
            raise RuntimeError(f"El puerto {cfg.get('PORT')} ya está en uso. Cierra el otro servidor o cambia el puerto.")
        world_name = cfg.get("WORLD_NAME", "mundo")
        if not re.fullmatch(r"[\w -]{1,40}", world_name):
            raise RuntimeError("El nombre del mundo en la configuración no es válido.")
        world = self.world_path(world_name)
        args = [str(self.exe), "-world", str(world), "-port", cfg.get("PORT", "7777"),
                "-maxplayers", cfg.get("PLAYERS", "8"), "-noupnp"]
        if cfg.get("PASSWORD"):
            args += ["-password", cfg["PASSWORD"]]
        if not world.exists():
            args += ["-autocreate", cfg.get("AUTOCREATE", "1"), "-worldname", world_name]
        env = os.environ.copy()
        if platform.system() == "Linux":
            libdir = str(self.win_dir / "lib64")
            env["LD_LIBRARY_PATH"] = libdir + os.pathsep + env.get("LD_LIBRARY_PATH", "")
            env["MONO_IOMAP"] = "all"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = self.log_file.open("a", encoding="utf-8", errors="ignore")
        options = {"cwd": str(self.win_dir), "stdin": subprocess.DEVNULL,
                   "stdout": fh, "stderr": subprocess.STDOUT, "env": env}
        if platform.system() == "Windows":
            options["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self.proc = subprocess.Popen(args, **options)
        except Exception:
            fh.close()
            raise
        if wait:
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                if self.proc.poll() is not None:
                    details = self.log_lines(30).strip()
                    raise RuntimeError("El servidor terminó durante el inicio. " + (details[-1200:] or "Revisa la configuración."))
                try:
                    if port_open(int(cfg.get("PORT", "7777"))):
                        return True
                except ValueError:
                    self.stop()
                    raise RuntimeError("El puerto configurado no es válido.")
                time.sleep(1)
            self.stop()
            raise RuntimeError("El servidor no abrió el puerto en tres minutos. Revisa el registro de la app.")
        return True


def pick_backend():
    """La app siempre usa los binarios y datos que viajan con ella."""
    return PortableBackend(app_base())


B = pick_backend()


class PlayitController:
    """Configura y ejecuta el agente incluido en el paquete de la app."""

    def __init__(self, base):
        self.base = Path(base)
        self.directory = data_root(self.base) / "playit"
        self.secret = self.directory / "secret.toml"
        self.log = self.directory / "agent.log"
        self.socket = self.directory / "playit.sock"
        self.cache = self.directory / "tunnel.txt"
        self.pid_file = self.directory / "agent.pid"
        self.process = None

    def agent_path(self):
        name = "playitd.exe" if platform.system() == "Windows" else "playitd"
        return self.directory / name

    def has_secret(self):
        try:
            return bool(re.search(r"secret_key\s*=\s*\"[0-9a-fA-F]{64}\"", self.secret.read_text(errors="ignore")))
        except OSError:
            return False

    def extract_key(self, value):
        # Acepta la clave sola o el bloque completo de Docker/Compose.
        match = re.search(r"(?:SECRET_KEY\s*=|secret_key\s*=\s*\"?)\s*([0-9a-fA-F]{64})", value)
        return match.group(1).lower() if match else None

    def _download_agent(self):
        path = self.agent_path()
        if path.is_file():
            return path
        self.directory.mkdir(parents=True, exist_ok=True)
        system = platform.system()
        machine = platform.machine().lower()
        if system == "Windows":
            url = "https://github.com/playit-cloud/playit-agent/releases/latest/download/playitd-windows-x86_64.exe"
        elif system == "Darwin":
            raise RuntimeError("Falta el agente de playit. Ejecuta playit.sh una vez para instalarlo y vuelve a abrir la app.")
        elif system == "Linux":
            arch = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "aarch64", "arm64": "aarch64", "armv7l": "armv7"}.get(machine)
            if not arch:
                raise RuntimeError(f"playit no ofrece un agente automático para la arquitectura {machine}.")
            url = f"https://github.com/playit-cloud/playit-agent/releases/latest/download/playit-linux-{arch}"
        else:
            raise RuntimeError(f"Sistema operativo no compatible: {system}.")
        try:
            with urllib.request.urlopen(url, timeout=30) as response, path.open("wb") as output:
                output.write(response.read())
            if system != "Windows":
                path.chmod(path.stat().st_mode | 0o111)
            return path
        except Exception as exc:
            path.unlink(missing_ok=True)
            raise RuntimeError(f"No pude descargar el agente de playit. Revisa tu conexión e inténtalo de nuevo. Detalle: {exc}") from exc

    def address(self):
        try:
            text = self.cache.read_text(errors="ignore").strip()
            if text:
                return text
        except OSError:
            pass
        try:
            text = self.log.read_text(errors="ignore")
            found = re.findall(r"connect_addr:\s*([\w.-]+:\d+)", text)
            if found:
                self.cache.write_text(found[-1] + "\n")
                return found[-1]
        except OSError:
            pass
        return None

    def connected(self):
        try:
            log = self.log.read_text(errors="ignore")
            return bool(re.search(
                r"account_status\s*[:=]\s*\"?verified\"?|tunnel_count\s*[:=]\s*[1-9]", log, re.I))
        except OSError:
            return False

    def stop(self):
        """Detiene el agente de esta app (no toca otros agentes del sistema)."""
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=10)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
        self.process = None
        try:
            pid = int(self.pid_file.read_text().strip())
            if platform.system() == "Windows":
                subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                               capture_output=True, timeout=5)
            else:
                os.kill(pid, 15)
        except Exception:
            pass
        self.pid_file.unlink(missing_ok=True)

    def save_address(self, text):
        text = (text or "").strip()
        if not re.search(r"[\w.-]+:\d+", text):
            raise RuntimeError("Esa dirección no parece válida. Debe verse como nombre.tun.ply.gg:12345.")
        self.directory.mkdir(parents=True, exist_ok=True)
        self.cache.write_text(text + "\n")
        return text

    def start_and_check(self, key=None):
        self.directory.mkdir(parents=True, exist_ok=True)
        if key:
            temp = self.secret.with_suffix(".tmp")
            temp.write_text(f'secret_key = "{key}"\n')
            try:
                temp.chmod(0o600)
            except OSError:
                pass
            temp.replace(self.secret)
        agent = self._download_agent()
        self.stop()
        # Evita interpretar como éxito la confirmación de una ejecución anterior.
        with self.log.open("w", encoding="utf-8") as log_file:
            kwargs = {"cwd": str(self.directory), "stdin": subprocess.DEVNULL,
                      "stdout": log_file, "stderr": subprocess.STDOUT}
            if platform.system() == "Windows":
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self.process = subprocess.Popen(
                [str(agent), "--secret-path", str(self.secret), "--socket-path", str(self.socket)], **kwargs)
        self.pid_file.write_text(str(self.process.pid))
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                detail = self.log.read_text(errors="ignore")[-2500:]
                if "InvalidAgentKey" in detail or "invalid agent key" in detail.lower():
                    raise RuntimeError("playit rechazó esa clave (InvalidAgentKey). Crea un agente nuevo en el wizard y pega su SECRET_KEY.")
                if "connect" in detail.lower() and ("fail" in detail.lower() or "error" in detail.lower()):
                    raise RuntimeError("El agente no pudo conectarse a playit.gg. Revisa tu conexión a internet e inténtalo de nuevo.")
                raise RuntimeError("El agente de playit se cerró al iniciar. Revisa playit/agent.log para ver el motivo.")
            if self.connected():
                return self.address()
            try:
                detail = self.log.read_text(errors="ignore")[-2500:]
                if "InvalidAgentKey" in detail or "invalid agent key" in detail.lower():
                    raise RuntimeError("playit rechazó esa clave (InvalidAgentKey). Crea un agente nuevo en el wizard y pega su SECRET_KEY.")
            except OSError:
                pass
            time.sleep(1)
        if self.process.poll() is None:
            # A key may be valid even while playit has not created a tunnel yet.
            detail = self.log.read_text(errors="ignore")[-2500:]
            if "InvalidAgentKey" in detail:
                raise RuntimeError("playit rechazó esa clave (InvalidAgentKey). Crea un agente nuevo en el wizard y pega su SECRET_KEY.")
        raise RuntimeError("No recibí confirmación de playit en 60 segundos. Revisa internet y agent.log; luego vuelve a intentar.")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        setup_fonts(self)
        setup_styles(self)
        self.title("TerraServer")
        self.geometry("760x800")
        self.minsize(760, 700)
        self.configure(bg=BG)
        self.worlds = []
        self.busy = False
        self.is_running = False
        self.copied_until = 0.0
        self.playit = PlayitController(app_base())
        self.build()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.refresh()
        if self.playit.has_secret():
            self._safe(lambda: self.playit.start_and_check(), lambda: self.refresh())
        else:
            self.after(700, lambda: PlayitSetupDialog(self))

    # ---------- construcción ----------
    def build(self):
        # Contenido centrado con un ancho cómodo (no estirado a toda la ventana).
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(2, weight=1)
        self.content = tk.Frame(self, bg=BG, width=680)
        self.content.grid(row=0, column=1, sticky="n", padx=24, pady=24)
        tk.Frame(self.content, bg=BG, width=680, height=1).pack(fill="x")

        header = tk.Frame(self.content, bg=BG)
        header.pack(fill="x", pady=(0, 12))
        tk.Label(header, text="TerraServer", bg=BG, fg=FG,
                 font=(FONT_FAMILY, 22, "bold")).pack(anchor="w")
        tk.Label(header, text="Tu servidor de Terraria para jugar con amigos",
                 bg=BG, fg=DIM, font=FONT).pack(anchor="w", pady=(2, 0))

        # 1. Estado + una sola acción principal
        inner = self.card()
        top = tk.Frame(inner, bg=SURFACE)
        top.pack(fill="x")
        self.dot = tk.Label(top, text="●", bg=SURFACE, fg=DIM,
                            font=(FONT_FAMILY, 16))
        self.dot.pack(side="left", padx=(0, 10))
        left = tk.Frame(top, bg=SURFACE)
        left.pack(side="left", fill="x", expand=True)
        self.lbl_status = tk.Label(left, text="Servidor detenido", bg=SURFACE, fg=FG,
                                   font=(FONT_FAMILY, 14, "bold"))
        self.lbl_status.pack(anchor="w")
        self.lbl_detail = tk.Label(left, text="Pulsa Iniciar servidor para abrirlo",
                                   bg=SURFACE, fg=DIM, font=FONT)
        self.lbl_detail.pack(anchor="w", pady=(2, 0))
        self.btn_toggle = ttk.Button(top, text="Iniciar servidor", style="Primary.TButton",
                                     command=self.on_toggle)
        self.btn_toggle.pack(side="right")

        # 2. Conexión con amigos
        inner = self.card("Conexión con amigos")
        self.lbl_playit = tk.Label(inner, text="playit.gg: sin conectar", bg=SURFACE,
                                   fg=YELLOW, font=FONT_B)
        self.lbl_playit.pack(anchor="w")
        self.btn_playit = ttk.Button(inner, text="Conectar", style="Secondary.TButton",
                                     command=self.on_link)
        self.btn_playit.pack(anchor="w", pady=(8, 12))
        addr_row = tk.Frame(inner, bg=SURFACE)
        addr_row.pack(fill="x")
        self.lbl_addr = tk.Label(addr_row, text="Conecta playit.gg para obtener tu dirección",
                                 bg=PANEL, fg=DIM, font=("DejaVu Sans Mono", 11),
                                 anchor="w", padx=10, pady=8,
                                 highlightthickness=1, highlightbackground=BORDER)
        self.lbl_addr.pack(side="left", fill="x", expand=True)
        self.btn_copy = ttk.Button(addr_row, text="Copiar", style="Secondary.TButton",
                                   command=self.copy_addr, state="disabled")
        self.btn_copy.pack(side="right", padx=(8, 0))

        # 3. Mundo
        inner = self.card("Mundo")
        self.lbl_world = tk.Label(inner, text="Mundo activo", bg=SURFACE, fg=DIM,
                                  font=(FONT_FAMILY, 9))
        self.lbl_world.pack(anchor="w")
        row = tk.Frame(inner, bg=SURFACE)
        row.pack(fill="x", pady=(4, 8))
        self.cmb_world = ttk.Combobox(row, state="readonly", style="Dark.TCombobox", font=FONT)
        self.cmb_world.pack(side="left", fill="x", expand=True)
        self.btn_use = ttk.Button(row, text="Usar", style="Secondary.TButton",
                                  command=self.on_use)
        self.btn_use.pack(side="left", padx=(8, 0))
        self.btn_new = ttk.Button(inner, text="Crear mundo", style="Secondary.TButton",
                                  command=self.on_new)
        self.btn_new.pack(anchor="w", pady=(8, 0))
        sep = tk.Frame(inner, bg=BORDER, height=1)
        sep.pack(fill="x", pady=(14, 10))
        self.btn_delete = ttk.Button(inner, text="Borrar mundo", style="Danger.TButton",
                                     command=self.on_delete)
        self.btn_delete.pack(anchor="w")
        self.lbl_world_hint = tk.Label(inner, text="", bg=SURFACE, fg=DIM,
                                       font=(FONT_FAMILY, 9), justify="left")
        self.lbl_world_hint.pack(anchor="w", pady=(6, 0))

        # 4. Detalles técnicos plegables
        self.detail_btn = ttk.Button(self.content, text="▸ Detalles técnicos",
                                     style="Secondary.TButton", command=self.toggle_details)
        self.detail_btn.pack(anchor="w", pady=(4, 0))
        self.details = tk.Frame(self.content, bg=BG)
        self.txt = tk.Text(self.details, height=6, bg="#11111b", fg=FG,
                           font=("DejaVu Sans Mono", 9), relief="flat",
                           highlightthickness=1, highlightbackground=BORDER,
                           state="disabled", wrap="word", padx=8, pady=8)
        self.txt.pack(side="left", fill="both", expand=True)
        sl = ttk.Scrollbar(self.details, style="Dark.Vertical.TScrollbar",
                           command=self.txt.yview)
        sl.pack(side="right", fill="y")
        self.txt.config(yscrollcommand=sl.set)

    def card(self, title=None):
        """Tarjeta de superficie con borde sutil."""
        card = tk.Frame(self.content, bg=SURFACE,
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x", pady=(0, 10))
        inner = tk.Frame(card, bg=SURFACE)
        inner.pack(fill="x", padx=20, pady=14)
        if title:
            tk.Label(inner, text=title, bg=SURFACE, fg=FG,
                     font=(FONT_FAMILY, 12, "bold")).pack(anchor="w", pady=(0, 10))
        return inner

    def mk_btn(self, parent, text, color, cmd):
        """Compatibilidad: botón con estilo según el color pedido."""
        style = "Primary.TButton" if color in (BLUE, GREEN) else "Secondary.TButton"
        return ttk.Button(parent, text=text, style=style, command=cmd)

    # ---------- estado ----------
    def set_state(self, text, color):
        self.lbl_status.config(text=text, fg=color)
        self.dot.config(fg=color)
        self.btn_toggle.config(text="Detener servidor" if self.is_running else "Iniciar servidor")

    def refresh(self):
        try:
            st = B.status()
            self.worlds = B.list_worlds()
            self.cmb_world["values"] = self.worlds
            cfg = B.cfg()
            current = cfg.get("WORLD_NAME") or Path(cfg.get("WORLD", "")).stem
            if current and current not in self.worlds:
                current = self.worlds[0] if self.worlds else current
            if current:
                self.cmb_world.set(current)

            self.is_running = bool(st["server"])
            self.btn_toggle.config(text="Detener servidor" if self.is_running else "Iniciar servidor")
            self.btn_toggle.config(state="disabled" if self.busy else "normal")

            if st["server"] and st["port"]:
                self.set_state("Servidor disponible", GREEN)
                self.lbl_detail.config(text=f"Escuchando en el puerto {st['portnum']}", fg=DIM)
            elif st["server"]:
                self.set_state("Iniciando servidor…", YELLOW)
                self.lbl_detail.config(text="Cargando el mundo; puede tardar ~1 minuto", fg=DIM)
            else:
                self.set_state("Servidor detenido", DIM)
                self.lbl_detail.config(text="Pulsa Iniciar servidor para abrirlo", fg=DIM)

            if self.playit.connected():
                self.lbl_playit.config(text="playit.gg: conectado", fg=GREEN)
            elif self.playit.has_secret():
                self.lbl_playit.config(text="playit.gg: conectando…", fg=YELLOW)
            else:
                self.lbl_playit.config(text="playit.gg: sin conectar", fg=YELLOW)

            addr = self.playit.address()
            self.lbl_addr.config(text=addr or "Conecta playit.gg para obtener tu dirección",
                                 fg=FG if addr else DIM)
            self.btn_copy.config(state="normal" if addr else "disabled")
            if time.time() >= self.copied_until:
                self.btn_copy.config(text="Copiar")

            if self.is_running:
                self.btn_use.config(state="disabled")
                self.btn_delete.config(state="disabled")
                self.lbl_world_hint.config(text="Detén el servidor para cambiar o borrar el mundo.")
            else:
                self.btn_use.config(state="normal")
                self.btn_delete.config(state="normal")
                self.lbl_world_hint.config(text="")
        except Exception as e:
            self.lbl_detail.config(text=f"Error: {e}", fg=RED)
        self.after(3000, self.refresh)

    def log(self, msg):
        self.txt.config(state="normal")
        self.txt.insert("end", msg.rstrip() + "\n")
        self.txt.see("end")
        self.txt.config(state="disabled")

    def _safe(self, fn, done=None):
        def wrap():
            try:
                if fn:
                    fn()
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally:
                if done:
                    self.after(0, done)
        threading.Thread(target=wrap, daemon=True).start()

    def friendly_error(self, message):
        low = message.lower()
        if "no encuentro el servidor" in low:
            return "Faltan los archivos del servidor dentro de la app. Vuelve a instalar TerraServer."
        if "no es válido" in low and "puerto" in low:
            return "El puerto configurado no es válido. Revisa la configuración."
        if "no abrió el puerto" in low:
            return "El servidor tardó demasiado en abrir. Puede que el puerto esté ocupado; cierra otras apps y reintenta."
        if "terminó durante el inicio" in low:
            return "El servidor se cerró al arrancar. Revisa los detalles técnicos."
        return "No se pudo iniciar el servidor. Revisa los detalles técnicos."

    # ---------- acciones ----------
    def on_toggle(self):
        if self.busy:
            return
        if self.is_running:
            self.on_stop()
        else:
            self.on_start()

    def on_start(self):
        if self.busy:
            return
        self.busy = True
        self.is_running = True
        self.set_state("Preparando servidor…", YELLOW)
        self.lbl_detail.config(text="Esto puede tardar hasta un minuto", fg=DIM)
        self.btn_toggle.config(state="disabled", text="Detener servidor")
        self.log("iniciando servidor…")

        def work():
            try:
                B.start()
            except Exception as e:
                self.after(0, lambda: self.start_failed(str(e)))
            else:
                self.after(0, self.start_ok)
        threading.Thread(target=work, daemon=True).start()

    def start_ok(self):
        self.busy = False
        self.log("servidor iniciado")
        self.refresh()

    def start_failed(self, message):
        self.busy = False
        self.is_running = False
        self.set_state("No se pudo iniciar", RED)
        self.lbl_detail.config(text="Revisa los detalles técnicos", fg=RED)
        self.log("error: " + message)
        messagebox.showerror("No se pudo iniciar", self.friendly_error(message), parent=self)
        self.refresh()

    def on_stop(self):
        self._safe(B.stop, lambda: (self.log("servidor detenido"), self.refresh()))

    def on_restart(self):
        self._safe(lambda: (B.stop(), B.start()), lambda: (self.log("reiniciado"), self.refresh()))

    def on_link(self):
        if not self.playit.has_secret():
            PlayitSetupDialog(self)
        else:
            open_browser("https://playit.gg/account/analytics/overview")
            TunnelHelpDialog(self)

    def paste_addr(self):
        # Se mantiene por compatibilidad; la interfaz ya no expone este botón.
        TunnelHelpDialog(self)

    def copy_addr(self):
        addr = self.playit.address()
        if not addr:
            return
        self.clipboard_clear()
        self.clipboard_append(addr)
        self.copied_until = time.time() + 2
        self.btn_copy.config(text="¡Copiado!")

    def on_use(self):
        if self.is_running:
            messagebox.showinfo("Mundo", "Detén el servidor para cambiar de mundo.")
            return
        world = self.cmb_world.get().strip()
        if not world:
            messagebox.showinfo("Mundo", "Primero crea un mundo.")
            return
        if world == B.cfg().get("WORLD_NAME"):
            messagebox.showinfo("Mundo", f"«{world}» ya es el mundo activo.")
            return
        if messagebox.askyesno("Cambiar mundo", f"¿Usar «{world}»?"):
            self._safe(lambda: B.use_world(world, restart=False),
                       lambda: (self.log(f"mundo: {world}"), self.refresh()))

    def on_delete(self):
        if self.is_running:
            messagebox.showinfo("Mundo", "Detén el servidor para borrar un mundo.")
            return
        world = self.cmb_world.get().strip()
        if not world:
            messagebox.showinfo("Mundo", "Primero elige un mundo.")
            return
        if messagebox.askyesno("Borrar mundo", f"¿Borrar «{world}»? Esta acción no se puede deshacer."):
            def go():
                B.world_path(world).unlink(missing_ok=True)
                meta = B.load_meta()
                meta.pop(world, None)
                B.save_meta(meta)
            self._safe(go, lambda: (self.log(f"borrado {world}"), self.refresh()))

    def on_new(self):
        NewWorldDialog(self)

    def toggle_details(self):
        if self.details.winfo_ismapped():
            self.details.pack_forget()
            self.detail_btn.config(text="▸ Detalles técnicos")
        else:
            self.details.pack(fill="x", pady=(8, 0))
            self.detail_btn.config(text="▾ Detalles técnicos")
            self._safe(lambda: self.log(B.log_lines()))

    def on_close(self):
        if B._running():
            stop_server = messagebox.askyesno(
                "Servidor activo", "¿Detengo el servidor al cerrar la app?", parent=self)
            if stop_server:
                try:
                    B.stop()
                except Exception as exc:
                    messagebox.showerror("No se pudo detener", str(exc), parent=self)
                    return
        self.playit.stop()
        self.destroy()

class PlayitSetupDialog(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Conectar con playit.gg")
        self.geometry("590x490")
        self.minsize(540, 430)
        self.configure(bg=BG)
        self.transient(app)
        self.grab_set()
        self.build()

    def build(self):
        self.geometry("620x600")
        self.minsize(560, 520)
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=24, pady=22)
        tk.Label(body, text="Conecta tu servidor con playit.gg", bg=BG, fg=FG,
                 font=(FONT_FAMILY, 15, "bold"), justify="left").pack(anchor="w")
        tk.Label(body, text="Haz estos pasos una sola vez para vincular esta app.",
                 bg=BG, fg=DIM, font=FONT).pack(anchor="w", pady=(2, 12))
        instructions = (
            "1. Inicia sesión en playit.gg (o crea una cuenta).\n"
            "2. Abre Setup y pulsa New Agent Wizard.\n"
            "3. Elige Docker y copia el bloque de configuración que aparece.\n"
            "4. Pega aquí el bloque completo o solo el valor de SECRET_KEY.\n"
            "5. Pulsa Conectar; la app guardará la clave y arrancará el agente.\n\n"
            "Luego crea en el panel un túnel Terraria (TCP) hacia 127.0.0.1 y el puerto configurado en la app."
        )
        tk.Label(body, text=instructions, bg=BG, fg=FG, font=FONT,
                 justify="left", anchor="w", wraplength=560).pack(fill="x", pady=(0, 12))
        ttk.Button(body, text="Abrir playit.gg", style="Secondary.TButton",
                   command=lambda: open_browser("https://playit.gg/account/analytics/overview")).pack(anchor="w", pady=(0, 14))
        tk.Label(body, text="Pega el bloque de Docker o la SECRET_KEY:", bg=BG, fg=FG,
                 font=FONT_B).pack(anchor="w")
        self.input = tk.Text(body, height=5, bg=PANEL, fg=FG, insertbackground=FG,
                             relief="flat", font=("DejaVu Sans Mono", 9), wrap="word",
                             highlightthickness=1, highlightbackground=BORDER)
        self.input.pack(fill="x", pady=(6, 10))
        self.status = tk.Label(body, text="", bg=BG, fg=YELLOW, font=FONT,
                               justify="left", wraplength=560)
        self.status.pack(fill="x", anchor="w")
        buttons = tk.Frame(body, bg=BG)
        buttons.pack(fill="x", side="bottom", pady=(12, 0))
        self.connect_button = ttk.Button(buttons, text="Conectar", style="Primary.TButton",
                                         command=self.connect)
        self.connect_button.pack(side="right")
        ttk.Button(buttons, text="Más tarde", style="Secondary.TButton",
                   command=self.destroy).pack(side="right", padx=(0, 8))

    def connect(self):
        pasted = self.input.get("1.0", "end").strip()
        key = self.app.playit.extract_key(pasted)
        if not key:
            self.status.config(text="No encontré una SECRET_KEY válida. Pega el bloque de Docker completo o una clave de 64 caracteres hexadecimales.", fg=RED)
            return
        self.connect_button.config(state="disabled", text="Conectando…")
        self.status.config(text="Guardando la clave e intentando conectar con playit.gg (puede tardar hasta un minuto)…", fg=YELLOW)

        def work():
            try:
                address = self.app.playit.start_and_check(key)
                self.app.after(0, lambda: self.success(address))
            except Exception as exc:
                self.app.after(0, lambda: self.failed(str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def failed(self, message):
        self.connect_button.config(state="normal", text="Reintentar")
        self.status.config(text=message, fg=RED)
        self.app.log(f"playit: {message}")

    def success(self, address):
        self.input.delete("1.0", "end")
        self.app.log("playit quedó vinculado y el agente está activo.")
        self.app.refresh()
        self.destroy()
        open_browser("https://playit.gg/account/analytics/overview")
        TunnelHelpDialog(self.app)


class TunnelHelpDialog(tk.Toplevel):
    """Explica cómo crear el túnel y permite guardar la dirección manualmente."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Crea el túnel en playit.gg")
        self.geometry("560x440")
        self.configure(bg=BG)
        self.transient(app)
        self.grab_set()
        self.build()

    def build(self):
        self.geometry("580x500")
        self.minsize(520, 440)
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=24, pady=22)
        tk.Label(body, text="Crea el túnel de Terraria", bg=BG, fg=FG,
                 font=(FONT_FAMILY, 15, "bold"), justify="left").pack(anchor="w")
        port = B.cfg().get("PORT", "7777")
        steps = ("1. En el panel de playit.gg pulsa «Create Tunnel».\n"
                 "2. Elige «Terraria».\n"
                 f"3. En «Local» pon 127.0.0.1 y el puerto {port}.\n"
                 "4. Copia la dirección que te muestre (algo.tun.ply.gg:NNNNN).\n"
                 "5. Pégala aquí y pulsa Guardar.")
        tk.Label(body, text=steps, bg=BG, fg=FG, font=FONT, justify="left",
                 anchor="w", wraplength=530).pack(fill="x", pady=(10, 12))
        ttk.Button(body, text="Abrir playit.gg", style="Secondary.TButton",
                   command=lambda: open_browser("https://playit.gg/account/analytics/overview")).pack(anchor="w", pady=(0, 14))
        tk.Label(body, text="Dirección del túnel:", bg=BG, fg=FG, font=FONT_B).pack(anchor="w")
        self.entry = ttk.Entry(body, style="Dark.TEntry", font=("DejaVu Sans Mono", 10))
        current = self.app.playit.address()
        if current:
            self.entry.insert(0, current)
        self.entry.pack(fill="x", pady=(6, 8))
        self.status = tk.Label(body, text="", bg=BG, fg=YELLOW, font=FONT,
                               justify="left", wraplength=530)
        self.status.pack(fill="x", anchor="w")
        buttons = tk.Frame(body, bg=BG)
        buttons.pack(fill="x", side="bottom", pady=(12, 0))
        ttk.Button(buttons, text="Guardar", style="Primary.TButton",
                   command=self.save).pack(side="right")
        ttk.Button(buttons, text="Cerrar", style="Secondary.TButton",
                   command=self.destroy).pack(side="right", padx=(0, 8))

    def save(self):
        try:
            address = self.app.playit.save_address(self.entry.get())
        except Exception as exc:
            self.status.config(text=str(exc), fg=RED)
            return
        self.app.log(f"dirección guardada: {address}")
        self.app.refresh()
        self.destroy()


# ---------------- widgets redondeados (solo tkinter) ----------------
def _hex_to_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v))) for v in rgb)


def lerp_color(start, end, t):
    a, b = _hex_to_rgb(start), _hex_to_rgb(end)
    return _rgb_to_hex(tuple(a[i] + (b[i] - a[i]) * t for i in range(3)))


def draw_round_rect(canvas, x1, y1, x2, y2, radius, fill, outline=None, width=1, tags=()):
    """Rectángulo redondeado con create_arc + create_rectangle (sin smooth)."""
    r = max(0, min(int(radius), int((x2 - x1) / 2), int((y2 - y1) / 2)))
    if r > 0:
        canvas.create_arc(x1, y1, x1 + 2 * r, y1 + 2 * r, start=90, extent=90,
                          style="pieslice", fill=fill, outline=fill, tags=tags)
        canvas.create_arc(x2 - 2 * r, y1, x2, y1 + 2 * r, start=0, extent=90,
                          style="pieslice", fill=fill, outline=fill, tags=tags)
        canvas.create_arc(x2 - 2 * r, y2 - 2 * r, x2, y2, start=270, extent=90,
                          style="pieslice", fill=fill, outline=fill, tags=tags)
        canvas.create_arc(x1, y2 - 2 * r, x1 + 2 * r, y2, start=180, extent=90,
                          style="pieslice", fill=fill, outline=fill, tags=tags)
    canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline=fill, tags=tags)
    canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline=fill, tags=tags)
    if outline:
        if r > 0:
            canvas.create_arc(x1, y1, x1 + 2 * r, y1 + 2 * r, start=90, extent=90,
                              style="arc", outline=outline, width=width, tags=tags)
            canvas.create_arc(x2 - 2 * r, y1, x2, y1 + 2 * r, start=0, extent=90,
                              style="arc", outline=outline, width=width, tags=tags)
            canvas.create_arc(x2 - 2 * r, y2 - 2 * r, x2, y2, start=270, extent=90,
                              style="arc", outline=outline, width=width, tags=tags)
            canvas.create_arc(x1, y2 - 2 * r, x1 + 2 * r, y2, start=180, extent=90,
                              style="arc", outline=outline, width=width, tags=tags)
        canvas.create_line(x1 + r, y1, x2 - r, y1, fill=outline, width=width, tags=tags)
        canvas.create_line(x2, y1 + r, x2, y2 - r, fill=outline, width=width, tags=tags)
        canvas.create_line(x1 + r, y2, x2 - r, y2, fill=outline, width=width, tags=tags)
        canvas.create_line(x1, y1 + r, x1, y2 - r, fill=outline, width=width, tags=tags)


class RoundedButton(tk.Canvas):
    """Botón plano con esquinas redondeadas y hover animado."""

    def __init__(self, parent, text, command=None, variant="primary",
                 width=130, height=40, font=None, parent_bg=BG):
        super().__init__(parent, width=width, height=height, bg=parent_bg,
                         highlightthickness=0, bd=0)
        self.text = text
        self.command = command
        self.variant = variant
        self.font = font or FONT_B
        self.state = "normal"
        self._hover = False
        self._anim = None
        self._i = 0
        self._bg = self._normal_bg()
        self._fg = self._normal_fg()
        self._border = self._normal_border()
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self.redraw()

    def _normal_bg(self):
        return {"primary": ACCENT, "secondary": BTN, "danger": SURFACE}[self.variant]

    def _normal_fg(self):
        return {"primary": "#151521", "secondary": FG, "danger": RED}[self.variant]

    def _normal_border(self):
        return {"primary": None, "secondary": None, "danger": BORDER}[self.variant]

    def _hover_bg(self):
        return {"primary": "#93a0ff", "secondary": "#353550", "danger": "#3a2230"}[self.variant]

    def _press_bg(self):
        return {"primary": "#6575e6", "secondary": "#20202e", "danger": "#2a1a24"}[self.variant]

    def _disabled_bg(self):
        return {"primary": "#3a3a55", "secondary": "#20202e", "danger": SURFACE}[self.variant]

    def _disabled_fg(self):
        return {"primary": "#8a8aa0", "secondary": "#6f6f88", "danger": "#7a4a58"}[self.variant]

    def redraw(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4:
            return
        self.delete("all")
        draw_round_rect(self, 1, 1, w - 1, h - 1, 10, self._bg, self._border, 1)
        self.create_text(w / 2, h / 2, text=self.text, fill=self._fg, font=self.font)

    def _animate_bg(self, target):
        if self._anim:
            self.after_cancel(self._anim)
        self._start = self._bg
        self._target = target
        self._i = 0
        self._tick()

    def _tick(self):
        self._i += 1
        t = self._i / 8
        self._bg = lerp_color(self._start, self._target, t)
        self.redraw()
        if self._i < 8:
            self._anim = self.after(16, self._tick)
        else:
            self._bg = self._target
            self._anim = None
            self.redraw()

    def _enter(self, event=None):
        if self.state == "normal":
            self._hover = True
            self._animate_bg(self._hover_bg())

    def _leave(self, event=None):
        self._hover = False
        if self.state == "normal":
            self._animate_bg(self._normal_bg())

    def _press(self, event=None):
        if self.state == "normal":
            self._animate_bg(self._press_bg())

    def _release(self, event=None):
        if self.state != "normal":
            return
        if self._hover:
            self._animate_bg(self._hover_bg())
        else:
            self._animate_bg(self._normal_bg())
        if self.command:
            self.command()

    def configure(self, cnf=None, **kw):
        if isinstance(cnf, dict):
            kw.update(cnf)
        state = kw.pop("state", None)
        text = kw.pop("text", None)
        command = kw.pop("command", None)
        if self._anim:
            self.after_cancel(self._anim)
            self._anim = None
        if state is not None:
            self.state = state
        if text is not None:
            self.text = text
        if command is not None:
            self.command = command
        if self.state == "disabled":
            self._bg = self._disabled_bg()
            self._fg = self._disabled_fg()
        else:
            self._bg = self._normal_bg()
            self._fg = self._normal_fg()
        self._border = self._normal_border()
        self.redraw()

    config = configure


class RoundedEntry(tk.Frame):
    """Entry sin borde visible dentro de un contenedor redondeado."""

    def __init__(self, parent, width=200, font=None, show=None, parent_bg=BG):
        super().__init__(parent, bg=parent_bg, highlightthickness=0, bd=0)
        self.canvas = tk.Canvas(self, width=width, height=40, bg=parent_bg,
                                highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.entry = tk.Entry(self, bd=0, relief="flat", bg=PANEL, fg=FG,
                              insertbackground=FG, font=font or FONT,
                              highlightthickness=0, show=show or "")
        self.entry.place(x=12, y=8, width=10, height=24)
        self.border = BORDER
        self._anim = None
        self.canvas.bind("<Configure>", lambda e: self._layout())
        self.entry.bind("<FocusIn>", lambda e: self._focus(True))
        self.entry.bind("<FocusOut>", lambda e: self._focus(False))
        self._layout()

    def _layout(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4:
            return
        self.entry.place(x=12, y=(h - 24) // 2, width=max(20, w - 24), height=24)
        self.redraw()

    def redraw(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4:
            return
        self.canvas.delete("all")
        draw_round_rect(self.canvas, 1, 1, w - 1, h - 1, 10, PANEL, self.border, 1)

    def _focus(self, on):
        target = ACCENT if on else BORDER
        if self._anim:
            self.after_cancel(self._anim)
        self._start_border = self.border
        self._target_border = target
        self._i = 0
        self._tick_border()

    def _tick_border(self):
        self._i += 1
        self.border = lerp_color(self._start_border, self._target_border, self._i / 8)
        self.redraw()
        if self._i < 8:
            self._anim = self.after(16, self._tick_border)
        else:
            self.border = self._target_border
            self._anim = None
            self.redraw()

    def get(self):
        return self.entry.get()

    def insert(self, *args):
        return self.entry.insert(*args)

    def delete(self, *args):
        return self.entry.delete(*args)

    def focus_set(self):
        self.entry.focus_set()

    def bind(self, *args, **kwargs):
        return self.entry.bind(*args, **kwargs)


class RoundedSelect(tk.Frame):
    """Combobox estilizado dentro de un contenedor redondeado.

    Limitación: el desplegable nativo no puede tener esquinas redondeadas; se
    estiliza con option_add y se deja el borde redondeado del contenedor.
    """

    def __init__(self, parent, values, var, width=200, font=None, parent_bg=BG):
        super().__init__(parent, bg=parent_bg, highlightthickness=0, bd=0)
        self.values = list(values)
        self.var = var
        self.canvas = tk.Canvas(self, width=width, height=40, bg=parent_bg,
                                highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.combo = ttk.Combobox(self, textvariable=var, values=self.values,
                                  state="readonly", style="Dark.TCombobox",
                                  font=font or FONT)
        self.combo.place(x=12, y=6, width=10, height=28)
        self.canvas.bind("<Configure>", lambda e: self._layout())
        self.combo.bind("<<ComboboxSelected>>", lambda e: self.redraw())
        self._layout()

    def _layout(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4:
            return
        self.combo.place(x=12, y=(h - 28) // 2, width=max(20, w - 24), height=28)
        self.redraw()

    def redraw(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4:
            return
        self.canvas.delete("all")
        draw_round_rect(self.canvas, 1, 1, w - 1, h - 1, 10, PANEL, BORDER, 1)

    def current(self, index=None):
        if index is None:
            try:
                return self.values.index(self.var.get())
            except ValueError:
                return 0
        self.var.set(self.values[index])

    def set(self, value):
        self.var.set(value)

    def get(self):
        return self.var.get()

    def focus_set(self):
        self.combo.focus_set()


class SeedChip(tk.Canvas):
    """Píldora redondeada que actúa como Checkbutton sobre una BooleanVar."""

    def __init__(self, parent, text, var, width=200, height=34, font=None):
        super().__init__(parent, width=width, height=height, bg=BG,
                         highlightthickness=0, bd=0)
        self.text = text
        self.var = var
        self.font = font or (FONT_FAMILY, 9)
        self.selected = bool(var.get())
        self._hover = False
        self._anim = None
        self._bg = SURFACE
        self._border = BORDER
        self._fg = DIM
        self._apply(instant=True)
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<Button-1>", self._toggle)
        self.bind("<space>", self._toggle)
        self.var.trace_add("write", lambda *args: self._sync())

    def _targets(self):
        if self.selected:
            return ("#2a2b4a" if self._hover else "#23243d", ACCENT, ACCENT)
        if self._hover:
            return ("#24243a", "#3a3a55", FG)
        return (SURFACE, BORDER, DIM)

    def _apply(self, instant=False):
        bg, border, fg = self._targets()
        if instant:
            self._bg, self._border, self._fg = bg, border, fg
            self.redraw()
            return
        if self._anim:
            self.after_cancel(self._anim)
        self._start = (self._bg, self._border, self._fg)
        self._target = (bg, border, fg)
        self._i = 0
        self._tick()

    def _tick(self):
        self._i += 1
        t = self._i / 8
        self._bg = lerp_color(self._start[0], self._target[0], t)
        self._border = lerp_color(self._start[1], self._target[1], t)
        self._fg = lerp_color(self._start[2], self._target[2], t)
        self.redraw()
        if self._i < 8:
            self._anim = self.after(16, self._tick)
        else:
            self._bg, self._border, self._fg = self._target
            self._anim = None
            self.redraw()

    def redraw(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4:
            return
        self.delete("all")
        draw_round_rect(self, 1, 1, w - 1, h - 1, 10, self._bg, self._border, 1)
        if self.selected:
            self.create_text(14, h / 2, text="✓", fill=ACCENT,
                             font=(FONT_FAMILY, 10, "bold"))
            self.create_text(30, h / 2, text=self.text, fill=self._fg,
                             font=self.font, anchor="w")
        else:
            self.create_text(14, h / 2, text=self.text, fill=self._fg,
                             font=self.font, anchor="w")

    def _enter(self, event=None):
        self._hover = True
        self._apply()

    def _leave(self, event=None):
        self._hover = False
        self._apply()

    def _toggle(self, event=None):
        self.var.set(not self.var.get())

    def _sync(self):
        self.selected = bool(self.var.get())
        self._apply()


class NewWorldDialog(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Crear mundo")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()
        self.busy = False
        self.build()
        self._fade_in()
        self.update_idletasks()
        height = self.winfo_reqheight()
        self.geometry(f"480x{height}")
        try:
            x = self.app.winfo_rootx() + max(0, (self.app.winfo_width() - 480) // 2)
            y = self.app.winfo_rooty() + max(0, (self.app.winfo_height() - height) // 3)
            self.geometry(f"480x{height}+{x}+{y}")
        except Exception:
            pass
        self.e_name.focus_set()
        self.bind("<Return>", lambda e: self.create())
        self.bind("<Escape>", lambda e: self.destroy())

    def build(self):
        wrap = tk.Frame(self, bg=BG)
        wrap.pack(fill="both", expand=True, padx=24, pady=22)
        tk.Label(wrap, text="Crea un mundo nuevo", bg=BG, fg=FG,
                 font=(FONT_FAMILY, 15, "bold")).pack(anchor="w")
        tk.Label(wrap, text="Puede tardar 1-2 minutos.", bg=BG, fg=DIM,
                 font=FONT).pack(anchor="w", pady=(2, 12))

        form = tk.Frame(wrap, bg=BG)
        form.pack(fill="x")
        r = 0

        def row(label, widget, hint=None):
            nonlocal r
            tk.Label(form, text=label, bg=BG, fg=FG, font=FONT).grid(
                row=r, column=0, sticky="w", pady=6, padx=(0, 12))
            widget.grid(row=r, column=1, sticky="w", pady=6)
            r += 1
            if hint:
                tk.Label(form, text=hint, bg=BG, fg=DIM,
                         font=(FONT_FAMILY, 8)).grid(row=r, column=1, sticky="w")
                r += 1

        self.e_name = RoundedEntry(form)
        row("Nombre", self.e_name)
        self.e_name.bind("<KeyRelease>", lambda e: self._update_create_state())
        self.e_name.bind("<<Paste>>", lambda e: self.after(10, self._update_create_state))
        self.e_name.bind("<ButtonRelease-1>", lambda e: self.after(10, self._update_create_state))

        self.v_size = tk.StringVar(value="pequeño")
        self.c_size = RoundedSelect(form, ["pequeño", "mediano", "grande"], self.v_size)
        self.c_size.current(0)
        row("Tamaño", self.c_size)

        self.v_diff = tk.StringVar(value="clásico")
        self.c_diff = RoundedSelect(form, ["clásico", "experto", "maestro", "viaje"], self.v_diff)
        self.c_diff.current(0)
        row("Dificultad", self.c_diff)

        self.v_evil = tk.StringVar(value="aleatoria")
        self.c_evil = RoundedSelect(form, ["aleatoria", "corrupción", "carmesí"], self.v_evil)
        self.c_evil.current(0)
        row("Maldad", self.c_evil)

        self.e_seed = RoundedEntry(form)
        row("Semilla", self.e_seed, hint="vacío = aleatoria")

        tk.Label(wrap, text="Semillas especiales", bg=BG, fg=FG,
                 font=FONT_B).pack(anchor="w", pady=(14, 6))
        grid = tk.Frame(wrap, bg=BG)
        grid.pack(fill="x")
        grid.grid_columnconfigure(0, weight=1, uniform="seeds")
        grid.grid_columnconfigure(1, weight=1, uniform="seeds")
        self.vars = {}
        options = [(k, v) for k, v in SEEDS.items() if k != "1"]
        for i, (key, label) in enumerate(options):
            var = tk.BooleanVar(value=False)
            self.vars[key] = var
            chip = SeedChip(grid, label, var, width=160)
            chip.grid(row=i // 2, column=i % 2, sticky="we", padx=4, pady=4)

        self.status = tk.Label(wrap, text="", bg=BG, fg=YELLOW, font=FONT,
                               wraplength=430, justify="left")
        self.status.pack(fill="x", pady=(10, 0))

        buttons = tk.Frame(wrap, bg=BG)
        buttons.pack(fill="x", pady=(12, 0))
        self.btn_cancel = RoundedButton(buttons, "Cancelar", self.destroy, "secondary", width=120)
        self.btn_cancel.pack(side="right")
        self.btn_create = RoundedButton(buttons, "Crear", self.create, "primary", width=120)
        self.btn_create.pack(side="right", padx=(0, 12))
        self._update_create_state()

    def _update_create_state(self):
        if self.busy:
            return
        self.btn_create.configure(state="normal" if self.e_name.get().strip() else "disabled")

    def _fade_in(self):
        try:
            self.attributes("-alpha", 0.0)
            self._alpha = 0.0
            self._fade_tick()
        except Exception:
            pass

    def _fade_tick(self):
        try:
            self._alpha = min(1.0, self._alpha + 0.1)
            self.attributes("-alpha", self._alpha)
            if self._alpha < 1.0:
                self.after(15, self._fade_tick)
        except Exception:
            pass

    def create(self):
        name = self.e_name.get().strip()
        if not name or B.world_path(name).exists() or not re.fullmatch(r"[\w \-]{1,30}", name):
            messagebox.showerror("Nombre", "nombre vacío, ya existe o con caracteres no permitidos")
            return
        size = str(self.c_size.current() + 1)
        diff = str(self.c_diff.current() + 1)
        evil = str(self.c_evil.current() + 1)
        seed = self.e_seed.get().strip()
        specials = [int(k) for k, v in self.vars.items() if v.get()]
        self.busy = True
        self.btn_create.configure(state="disabled")
        self.status.config(text="Creando mundo... puede tardar 1-2 minutos.", fg=YELLOW)

        def go():
            try:
                ok = B.create_world(name, size, diff, evil, seed, specials)
            except Exception as exc:
                self.app.after(0, lambda: self.failed(str(exc)))
                return
            self.app.after(0, lambda: self.finish(ok, name))
        threading.Thread(target=go, daemon=True).start()

    def failed(self, message):
        self.busy = False
        self.btn_create.configure(state="normal")
        self.status.config(text=f"No se pudo crear: {message}", fg=RED)

    def finish(self, ok, name):
        if not ok:
            self.failed("revisa dependencias/creacion.log")
            return
        self.status.config(text=f"Mundo «{name}» creado.", fg=GREEN)
        if messagebox.askyesno("Mundo creado", f"¿Activar «{name}» ahora?"):
            self.app._safe(lambda: B.use_world(name), self.app.refresh)
        self.destroy()

if __name__ == "__main__":
    try:
        App().mainloop()
    except KeyboardInterrupt:
        pass
