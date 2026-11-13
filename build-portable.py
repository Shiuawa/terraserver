#!/usr/bin/env python3
"""Build the app into terraserver/<platform>/app + dependencias/."""
import argparse
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PLAYIT_RELEASE = "https://github.com/playit-cloud/playit-agent/releases/latest/download/"
PLATFORM_DIR = {"Linux": "linux", "Windows": "windows"}


def fetch(url, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "TerrariaPortableBuilder/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as out:
        shutil.copyfileobj(response, out)


def stage_playit(data_dir):
    directory = data_dir / "playit"
    directory.mkdir(parents=True, exist_ok=True)
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Windows":
        fetch(PLAYIT_RELEASE + "playitd-windows-x86_64.exe", directory / "playitd.exe")
    elif system == "Linux":
        arch = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "aarch64", "arm64": "aarch64", "armv7l": "armv7"}.get(machine)
        if not arch:
            raise RuntimeError(f"No hay un agente playit para esta arquitectura: {machine}")
        bundled = ROOT / "playit" / "playitd"
        if arch == "amd64" and bundled.is_file():
            shutil.copy2(bundled, directory / "playitd")
        else:
            fetch(PLAYIT_RELEASE + f"playit-linux-{arch}", directory / "playitd")
        (directory / "playitd").chmod(0o755)
    else:
        raise RuntimeError(f"Este constructor genera paquetes para Linux y Windows; sistema actual: {system}.")


def copy_runtime_data(stage):
    system = platform.system()
    server_name = {"Windows": "Windows", "Linux": "Linux"}[system]
    server_source = ROOT / "server" / server_name
    if not server_source.is_dir():
        raise RuntimeError(f"No está incluido el servidor de Terraria para {system}: {server_source}")
    data_dir = stage / ".dependencias"
    server_target = data_dir / "server" / server_name
    if server_target.exists():
        shutil.rmtree(server_target)
    shutil.copytree(server_source, server_target)
    config_name = "config.bat" if system == "Windows" else "config.env"
    if not (data_dir / config_name).exists():
        shutil.copy2(ROOT / config_name, data_dir / config_name)
    worlds_target = data_dir / "worlds"
    worlds_target.mkdir(exist_ok=True)
    worlds_source = ROOT / "worlds"
    if worlds_source.is_dir():
        for world in worlds_source.glob("*.wld"):
            target = worlds_target / world.name
            if not target.exists():
                shutil.copy2(world, target)
    shutil.copy2(ROOT / "README.md", data_dir / "LÉEME.txt")
    stage_playit(data_dir)
    # La app es el único punto de entrada: nada suelto en la raíz.
    for name in ("config.env", "config.bat", "README.md", "Abrir Terraria.sh", ".hidden"):
        extra = stage / name
        if extra.exists():
            extra.unlink()
    old_worlds = stage / "worlds"
    if old_worlds.is_dir():
        shutil.rmtree(old_worlds)


def main():
    system = platform.system()
    if system not in PLATFORM_DIR:
        raise RuntimeError("Ejecuta este constructor en Linux o Windows.")
    parser = argparse.ArgumentParser(description="Construye terraserver/<sistema>/app y dependencias/.")
    parser.add_argument("--output", type=Path, default=ROOT / "terraserver" / PLATFORM_DIR[system],
                        help="Carpeta del sistema donde se coloca app y dependencias")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="terraserver-build-") as temp_name:
        temp = Path(temp_name)
        compiled = temp / "compiled"
        work = temp / "work"
        contents_name = ".dependencias"
        for stale in ("dependencias", ".dependencias"):
            stale_dir = output / stale
            if stale_dir.is_dir() and stale != contents_name:
                shutil.rmtree(stale_dir)
        command = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", "--onedir",
                   "--windowed", "--name", "app", "--contents-directory", contents_name,
                   "--specpath", str(temp / "spec"), "--distpath", str(compiled),
                   "--workpath", str(work), str(ROOT / "terra-gui.py")]
        subprocess.run(command, cwd=ROOT, check=True)

        built_app = compiled / "app"
        if not built_app.is_dir():
            raise RuntimeError("PyInstaller no generó la carpeta app esperada.")
        app_file = output / ("app.exe" if system == "Windows" else "app")
        dependency_dir = output / contents_name
        dependency_dir.mkdir(exist_ok=True)
        if app_file.exists():
            app_file.unlink()
        for item in dependency_dir.iterdir():
            if item.name in {"server", "playit"}:
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        for item in built_app.iterdir():
            if item.name == contents_name:
                shutil.copytree(item, dependency_dir, dirs_exist_ok=True)
            elif item.is_file():
                shutil.copy2(item, app_file)
        copy_runtime_data(output)
        if system == "Windows":
            subprocess.run(["attrib", "+h", str(dependency_dir)], check=False)
        elif system == "Linux":
            subprocess.run(["chmod", "700", str(dependency_dir)], check=False)
        shutil.rmtree(compiled, ignore_errors=True)
        shutil.rmtree(work, ignore_errors=True)

    print(f"Estructura lista en: {output}")


if __name__ == "__main__":
    main()
