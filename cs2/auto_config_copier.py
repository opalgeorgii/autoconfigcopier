import os
import shutil
import platform
import sys
from pathlib import Path
import winreg  # built-in Windows registry module
import vdf
import ctypes  # for Windows popup

# -----------------------------
# Determine Steam install path
# -----------------------------

if platform.architecture()[0] == "64bit":
    reg_path = r"SOFTWARE\WOW6432Node\Valve\Steam"
else:
    reg_path = r"SOFTWARE\Valve\Steam"

try:
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as key:
        steam_path, _ = winreg.QueryValueEx(key, "InstallPath")
except FileNotFoundError:
    ctypes.windll.user32.MessageBoxW(
        0, f"Steam not found in registry ({reg_path})", "CS2 Config Copier - Error", 0x10
    )
    exit(1)

# -----------------------------
# Read Steam libraryfolders.vdf
# -----------------------------

library_vdf_path = os.path.join(steam_path, "steamapps", "libraryfolders.vdf")
if not os.path.exists(library_vdf_path):
    ctypes.windll.user32.MessageBoxW(
        0, f"libraryfolders.vdf not found at {library_vdf_path}", "CS2 Config Copier - Error", 0x10
    )
    exit(1)

with open(library_vdf_path, encoding="utf-8") as f:
    kv = vdf.load(f)

# -----------------------------
# Extract all library folders
# -----------------------------

library_folders = []
for key, value in kv.get("libraryfolders", {}).items():
    if key.isdigit():
        if isinstance(value, dict) and "path" in value:
            library_folders.append(value["path"])
        elif isinstance(value, str):
            library_folders.append(value)

# -----------------------------
# Find CS2 game folder
# -----------------------------

cs2_game_folder = None
for lib in library_folders:
    cs2_path_candidate = os.path.join(
        lib, "steamapps", "common", "Counter-Strike Global Offensive", "game", "csgo"
    )
    if os.path.exists(cs2_path_candidate):
        cs2_game_folder = cs2_path_candidate
        break

if cs2_game_folder is None:
    ctypes.windll.user32.MessageBoxW(
        0, "CS2 game folder not found in any Steam library!", "CS2 Config Copier - Error", 0x10
    )
    exit(1)

# -----------------------------
# Find all Steam userdata folders (user IDs)
# -----------------------------

userdata_folder = os.path.join(steam_path, "userdata")
user_folders = [f for f in os.listdir(userdata_folder) if os.path.isdir(os.path.join(userdata_folder, f))]

# -----------------------------
# Files to copy
# -----------------------------

cfg_files = [
    "autoexec.cfg",
    "cs2_1v1.cfg",
    "cs2_fun.cfg",
    "cs2_nades.cfg"
]

vcfg_files = [
    "cs2_user_convars_0_slot0.vcfg",
    "cs2_user_keys_0_slot0.vcfg",
    "cs2_video.txt",
    "cs2_machine_convars.vcfg"
]

# -----------------------------
# Determine source folder (cfg files)
# Works for .exe in dist/ or .py in cs2/
# -----------------------------

if getattr(sys, 'frozen', False):
    # Running as .exe inside dist/
    base_folder = Path(sys.executable).parent.parent  # go up from dist/
else:
    # Running as Python script in project root
    base_folder = Path(__file__).parent

cfg_src_folder = base_folder / "cfg"

# -----------------------------
# Copy cfg files to game folder
# -----------------------------

cfg_dst_folder = os.path.join(cs2_game_folder, "cfg")
os.makedirs(cfg_dst_folder, exist_ok=True)

for file_name in cfg_files:
    src_file = os.path.join(cfg_src_folder, file_name)
    dst_file = os.path.join(cfg_dst_folder, file_name)
    if os.path.exists(src_file):
        shutil.copy2(src_file, dst_file)
        print(f"Copied {file_name} to {cfg_dst_folder}")

# -----------------------------
# Copy vcfg files to each user's local cfg folder
# -----------------------------

for user in user_folders:
    local_cfg_path = os.path.join(userdata_folder, user, "730", "local", "cfg")
    os.makedirs(local_cfg_path, exist_ok=True)
    for file_name in vcfg_files:
        src_file = os.path.join(cfg_src_folder, file_name)
        dst_file = os.path.join(local_cfg_path, file_name)
        if os.path.exists(src_file):
            shutil.copy2(src_file, dst_file)
            print(f"Copied {file_name} to {local_cfg_path}")

# -----------------------------
# Show Windows popup when done
# -----------------------------

ctypes.windll.user32.MessageBoxW(
    0, "All files have been copied successfully!", "CS2 Config Copier", 0x40
)