"""Build the offline Windows x64 portable distribution from the local Python runtime."""
import os
import argparse
import struct
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description="Build the offline portable Windows app.")
parser.add_argument("--output", type=Path, default=root / "dist" / "codumi-Windows")
output = parser.parse_args().output.resolve()
runtime = output / "runtime"

if sys.platform != "win32" or struct.calcsize("P") != 8 or sys.version_info < (3, 10):
    raise SystemExit("Execute este build no Windows com Python 3.10+ e Tcl/Tk.")
if output.exists():
    raise SystemExit("dist/codumi-Windows já existe. Use outra pasta ou remova o build anterior explicitamente.")
compiler = Path(os.environ.get("WINDIR", "C:/Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
if not compiler.is_file():
    raise SystemExit("Compilador .NET Framework 4.x não encontrado.")
base = Path(sys.base_prefix)
runtime.mkdir(parents=True)
for name in ("Lib", "DLLs", "tcl"):
    shutil.copytree(base / name, runtime / name,
                    ignore=shutil.ignore_patterns("__pycache__", "site-packages", "test", "tests",
                                                  "ensurepip", "idlelib", "turtledemo", "venv"))
for pattern in ("pythonw.exe", "python.exe", "python*.dll", "vcruntime*.dll", "LICENSE.txt"):
    for path in base.glob(pattern):
        shutil.copy2(path, runtime / path.name)
for name in ("app.py", "sessions.py", "desktop.py", "pet.py", "i18n.py", "terminal.py", "companion.py", "locales.json", "README.md", "CONTRIBUTING.md", "CHANGELOG.md", "LICENSE", "THIRD_PARTY.md", "VALIDATION.md", "Fechar.cmd"):
    shutil.copy2(root / name, output / name)
if (root / "docs").is_dir():
    shutil.copytree(root / "docs", output / "docs")
subprocess.run([str(compiler), "/nologo", "/target:winexe",
                "/reference:System.Windows.Forms.dll", "/out:" + str(output / "codumi.exe"),
                str(root / "Launcher.cs")], check=True)
subprocess.run([str(runtime / "python.exe"), "-B", "-c",
                "import tkinter, app, desktop, pet, sessions, i18n, terminal, companion; r=tkinter.Tk(); r.withdraw(); r.destroy()"],
               cwd=output, check=True)
archive = output.parent / (output.name + "-x64.zip")
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
    for path in output.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix not in {".log", ".tmp"} and path.name != "preferences.json":
            bundle.write(path, path.relative_to(output.parent))
print(archive)
print(f"Portable: {sum(p.stat().st_size for p in output.rglob('*') if p.is_file()) / 1048576:.1f} MiB")
