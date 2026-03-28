import shutil
import sys
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import winreg


APP_TITLE = "CS2ConfigCopier"
CS2_APP_ID = "730"
CSGO_APP_ID = "4465480"
CS2_INSTALL_FALLBACK_DIRS = ("Counter-Strike Global Offensive",)
CSGO_INSTALL_FALLBACK_DIRS = ("csgo legacy",)
CSGO_VIDEO_EXTENSIONS = {".webm", ".web"}


class CopierError(Exception):
    pass


class VDFError(Exception):
    pass


# -----------------------------
# Generic helpers
# -----------------------------

def raise_error(message: str) -> None:
    raise CopierError(message)


def get_base_folder() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_runtime_base_folder() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def get_app_icon_path() -> Path | None:
    icon_path = get_runtime_base_folder() / "img" / "icon.ico"
    return icon_path if icon_path.exists() else None


def get_log_file_path(base_folder: Path) -> Path:
    return base_folder / "logs.txt"


def write_log(log_file: Path, section_title: str, lines: list[str]) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with log_file.open("a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {section_title}\n")
        for line in lines:
            f.write(f"{line}\n")
        f.write("\n")


def get_source_folder(base_folder: Path, folder_name: str) -> Path:
    folder = base_folder / folder_name
    if folder.exists() and folder.is_dir():
        return folder
    raise_error(f"Source folder not found:\n{folder}")


def has_any_files(folder: Path) -> bool:
    return folder.exists() and folder.is_dir() and any(p.is_file() for p in folder.rglob("*"))


# -----------------------------
# Minimal VDF reader/writer
# -----------------------------

def _vdf_tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    i = 0
    length = len(text)

    while i < length:
        ch = text[i]

        if ch.isspace():
            i += 1
            continue

        if ch == "/" and i + 1 < length and text[i + 1] == "/":
            i += 2
            while i < length and text[i] not in "\r\n":
                i += 1
            continue

        if ch in "{}":
            tokens.append(ch)
            i += 1
            continue

        if ch == '"':
            i += 1
            chars: list[str] = []
            while i < length:
                curr = text[i]
                if curr == "\\" and i + 1 < length:
                    chars.append(text[i + 1])
                    i += 2
                    continue
                if curr == '"':
                    i += 1
                    break
                chars.append(curr)
                i += 1
            else:
                raise VDFError("Unterminated quoted string in VDF.")

            tokens.append("".join(chars))
            continue

        start = i
        while i < length and not text[i].isspace() and text[i] not in '{}':
            i += 1
        tokens.append(text[start:i])

    return tokens


def _vdf_parse_object(tokens: list[str], pos: int = 0, expect_closing_brace: bool = False) -> tuple[OrderedDict, int]:
    data: OrderedDict[str, object] = OrderedDict()

    while pos < len(tokens):
        token = tokens[pos]

        if token == "}":
            if not expect_closing_brace:
                raise VDFError("Unexpected closing brace in VDF.")
            return data, pos + 1

        key = token
        pos += 1
        if pos >= len(tokens):
            raise VDFError(f"Missing value for key '{key}' in VDF.")

        next_token = tokens[pos]
        if next_token == "{":
            child, pos = _vdf_parse_object(tokens, pos + 1, expect_closing_brace=True)
            data[key] = child
        else:
            data[key] = next_token
            pos += 1

    if expect_closing_brace:
        raise VDFError("Missing closing brace in VDF.")

    return data, pos


def parse_vdf_text(text: str) -> OrderedDict:
    text = text.lstrip("\ufeff")
    tokens = _vdf_tokenize(text)
    if not tokens:
        return OrderedDict()
    data, pos = _vdf_parse_object(tokens)
    if pos != len(tokens):
        raise VDFError("Unexpected trailing tokens in VDF.")
    return data


def read_vdf_file(file_path: Path) -> OrderedDict:
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = file_path.read_text(encoding="utf-8-sig")
    except Exception as e:
        raise VDFError(f"Failed to read VDF file:\n{file_path}\n{e}")

    return parse_vdf_text(text)


def _escape_vdf_string(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def _dump_vdf_mapping(mapping: OrderedDict | dict, indent: int = 0) -> list[str]:
    lines: list[str] = []
    tabs = "\t" * indent

    for key, value in mapping.items():
        lines.append(f'{tabs}"{_escape_vdf_string(key)}"')
        if isinstance(value, dict):
            lines.append(f"{tabs}{{")
            lines.extend(_dump_vdf_mapping(value, indent + 1))
            lines.append(f"{tabs}}}")
        else:
            lines[-1] = f'{tabs}"{_escape_vdf_string(key)}"\t\t"{_escape_vdf_string(value)}"'

    return lines


def write_vdf_file(file_path: Path, data: OrderedDict | dict) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    contents = "\n".join(_dump_vdf_mapping(data)) + "\n"
    file_path.write_text(contents, encoding="utf-8")


def _find_existing_key_ci(mapping: OrderedDict | dict, wanted_key: str) -> str | None:
    wanted_lower = wanted_key.lower()
    for existing_key in mapping.keys():
        if str(existing_key).lower() == wanted_lower:
            return str(existing_key)
    return None


def get_or_create_nested_mapping(root: OrderedDict, keys: list[str]) -> OrderedDict:
    current: OrderedDict = root

    for key in keys:
        existing_key = _find_existing_key_ci(current, key)
        actual_key = existing_key if existing_key is not None else key

        if actual_key not in current or not isinstance(current[actual_key], dict):
            current[actual_key] = OrderedDict()

        current = current[actual_key]  # type: ignore[assignment]

    return current


# -----------------------------
# Steam / install detection
# -----------------------------

def get_steam_path() -> Path:
    reg_paths = [
        r"SOFTWARE\WOW6432Node\Valve\Steam",
        r"SOFTWARE\Valve\Steam",
    ]

    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for reg_path in reg_paths:
            try:
                with winreg.OpenKey(root, reg_path) as key:
                    steam_path, _ = winreg.QueryValueEx(key, "InstallPath")
                    path = Path(steam_path)
                    if path.exists():
                        return path
            except FileNotFoundError:
                continue
            except OSError:
                continue

    raise_error("Steam was not found in the Windows registry.")


def get_library_folders(steam_path: Path) -> list[Path]:
    library_vdf_path = steam_path / "steamapps" / "libraryfolders.vdf"
    if not library_vdf_path.exists():
        raise_error(f"libraryfolders.vdf was not found:\n{library_vdf_path}")

    try:
        data = read_vdf_file(library_vdf_path)
    except Exception as e:
        raise_error(f"Failed to read libraryfolders.vdf:\n{e}")

    libraryfolders_key = _find_existing_key_ci(data, "libraryfolders")
    libraryfolders = data[libraryfolders_key] if libraryfolders_key else data

    folders: list[Path] = []
    for key, value in libraryfolders.items():
        if not str(key).isdigit():
            continue

        if isinstance(value, dict):
            path_key = _find_existing_key_ci(value, "path")
            if path_key:
                folder = Path(str(value[path_key]))
                if folder.exists():
                    folders.append(folder)
        elif isinstance(value, str):
            folder = Path(value)
            if folder.exists():
                folders.append(folder)

    if steam_path not in folders and steam_path.exists():
        folders.insert(0, steam_path)

    unique: list[Path] = []
    seen: set[str] = set()
    for folder in folders:
        key = str(folder).lower()
        if key not in seen:
            seen.add(key)
            unique.append(folder)

    return unique


def get_user_folders(steam_path: Path) -> list[Path]:
    userdata_folder = steam_path / "userdata"
    if not userdata_folder.exists():
        raise_error(f"Steam userdata folder was not found:\n{userdata_folder}")

    return [p for p in userdata_folder.iterdir() if p.is_dir() and p.name.isdigit()]


def find_installed_app_dir(library_folders: list[Path], app_id: str, fallback_dir_names: tuple[str, ...]) -> Path:
    for library_folder in library_folders:
        manifest_path = library_folder / "steamapps" / f"appmanifest_{app_id}.acf"
        if manifest_path.exists():
            try:
                manifest = read_vdf_file(manifest_path)
                appstate_key = _find_existing_key_ci(manifest, "AppState")
                if appstate_key and isinstance(manifest[appstate_key], dict):
                    appstate = manifest[appstate_key]
                    installdir_key = _find_existing_key_ci(appstate, "installdir")
                    if installdir_key:
                        install_dir = library_folder / "steamapps" / "common" / str(appstate[installdir_key])
                        if install_dir.exists():
                            return install_dir
            except Exception:
                pass

        for fallback_name in fallback_dir_names:
            candidate = library_folder / "steamapps" / "common" / fallback_name
            if candidate.exists():
                return candidate

    raise_error("The requested game installation was not found in any Steam library.")


def find_cs2_install_dir(library_folders: list[Path]) -> Path:
    try:
        return find_installed_app_dir(library_folders, CS2_APP_ID, CS2_INSTALL_FALLBACK_DIRS)
    except CopierError:
        raise_error("CS2 is not installed.")


def find_csgo_install_dir(library_folders: list[Path]) -> Path:
    try:
        return find_installed_app_dir(library_folders, CSGO_APP_ID, CSGO_INSTALL_FALLBACK_DIRS)
    except CopierError:
        raise_error("CS:GO is not installed.")


# -----------------------------
# File copy helpers
# -----------------------------

def copy_file(src_file: Path, dst_file: Path, log_lines: list[str]) -> tuple[int, int]:
    try:
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst_file)
        log_lines.append(f"COPIED: {src_file} -> {dst_file}")
        return 1, 0
    except Exception as e:
        log_lines.append(f"FAILED COPY: {src_file} -> {dst_file} | {e}")
        return 0, 1


def copy_tree_files(src_root: Path, dst_root: Path, log_lines: list[str]) -> tuple[int, int]:
    if not src_root.exists() or not src_root.is_dir():
        log_lines.append(f"SKIPPED missing folder: {src_root}")
        return 0, 0

    copied = 0
    failed = 0

    for src_file in src_root.rglob("*"):
        if not src_file.is_file():
            continue
        relative_path = src_file.relative_to(src_root)
        c, f = copy_file(src_file, dst_root / relative_path, log_lines)
        copied += c
        failed += f

    return copied, failed


def backup_file(file_path: Path, log_lines: list[str]) -> tuple[int, int]:
    if not file_path.exists():
        return 0, 0

    backup_path = file_path.with_name(file_path.name + ".bak")
    try:
        shutil.copy2(file_path, backup_path)
        log_lines.append(f"BACKUP: {file_path} -> {backup_path}")
        return 1, 0
    except Exception as e:
        log_lines.append(f"FAILED BACKUP: {file_path} -> {backup_path} | {e}")
        return 0, 1


def copy_plugin_files(source_plugins_root: Path, server_folder: Path, log_lines: list[str]) -> tuple[int, int, int]:
    if not source_plugins_root.exists() or not source_plugins_root.is_dir():
        log_lines.append(f"SKIPPED missing plugins folder: {source_plugins_root}")
        return 0, 0, 0

    dest_plugins_root = server_folder / "game" / "csgo" / "addons" / "counterstrikesharp" / "plugins"
    dest_plugin_configs_root = server_folder / "game" / "csgo" / "addons" / "counterstrikesharp" / "configs" / "plugins"

    copied = 0
    failed = 0
    plugins_processed = 0

    for plugin_folder in source_plugins_root.iterdir():
        if not plugin_folder.is_dir():
            continue

        plugins_processed += 1
        dest_plugin_root = dest_plugins_root / plugin_folder.name
        cfg_folder = plugin_folder / "cfg"

        for src_item in plugin_folder.rglob("*"):
            if not src_item.is_file():
                continue

            try:
                src_item.relative_to(cfg_folder)
                is_plugin_cfg = True
            except ValueError:
                is_plugin_cfg = False

            if is_plugin_cfg:
                relative_cfg_path = src_item.relative_to(cfg_folder)
                c, f = copy_file(src_item, dest_plugin_configs_root / plugin_folder.name / relative_cfg_path, log_lines)
            else:
                relative_plugin_path = src_item.relative_to(plugin_folder)
                c, f = copy_file(src_item, dest_plugin_root / relative_plugin_path, log_lines)

            copied += c
            failed += f

    return copied, failed, plugins_processed


def validate_server_folder(server_folder: Path) -> Path:
    if not server_folder.exists() or not server_folder.is_dir():
        raise_error(f"The selected server folder does not exist:\n{server_folder}")
    return server_folder


# -----------------------------
# Launch options patching
# -----------------------------

def set_launch_options_for_user(user_folder: Path, app_id: str, launch_options: str, log_lines: list[str]) -> tuple[int, int]:
    config_folder = user_folder / "config"
    localconfig_path = config_folder / "localconfig.vdf"

    try:
        if localconfig_path.exists():
            data = read_vdf_file(localconfig_path)
        else:
            data = OrderedDict()
            log_lines.append(f"CREATED new localconfig.vdf structure for user: {user_folder.name}")

        app_mapping = get_or_create_nested_mapping(
            data,
            ["UserLocalConfigStore", "Software", "Valve", "Steam", "apps", app_id],
        )
        app_mapping["LaunchOptions"] = launch_options

        _, backup_failed = backup_file(localconfig_path, log_lines)
        if backup_failed:
            return 0, 1

        write_vdf_file(localconfig_path, data)
        log_lines.append(f"UPDATED LaunchOptions for app {app_id}: {localconfig_path}")
        return 1, 0
    except Exception as e:
        log_lines.append(f"FAILED LaunchOptions update: {localconfig_path} | {e}")
        return 0, 1


# -----------------------------
# Install operations
# -----------------------------

def install_cs2_configs() -> str:
    base_folder = get_base_folder()
    log_file = get_log_file_path(base_folder)
    cs2_cfg_root = get_source_folder(base_folder, "cs2_cfg")

    default_configs_folder = cs2_cfg_root / "default_configs"
    additional_configs_folder = cs2_cfg_root / "additional_configs"

    if not has_any_files(default_configs_folder) and not has_any_files(additional_configs_folder):
        raise_error(
            "No files were found in cs2_cfg.\n\n"
            f"Checked:\n{default_configs_folder}\n{additional_configs_folder}"
        )

    log_lines = [
        f"Base folder: {base_folder}",
        f"CS2 cfg root: {cs2_cfg_root}",
        f"Default configs folder: {default_configs_folder}",
        f"Additional configs folder: {additional_configs_folder}",
    ]

    steam_path = get_steam_path()
    library_folders = get_library_folders(steam_path)
    cs2_install_dir = find_cs2_install_dir(library_folders)
    user_folders = get_user_folders(steam_path)

    cs2_cfg_destination = cs2_install_dir / "game" / "csgo" / "cfg"

    log_lines.extend([
        f"Steam path: {steam_path}",
        f"CS2 install dir: {cs2_install_dir}",
        f"CS2 cfg destination: {cs2_cfg_destination}",
        f"Steam user folders found: {len(user_folders)}",
    ])

    total_copied = 0
    total_failed = 0
    users_processed = 0
    users_skipped = 0

    c, f = copy_tree_files(additional_configs_folder, cs2_cfg_destination, log_lines)
    total_copied += c
    total_failed += f

    for user_folder in user_folders:
        app_folder = user_folder / CS2_APP_ID
        if not app_folder.exists():
            users_skipped += 1
            log_lines.append(f"SKIPPED USER (no {CS2_APP_ID} folder): {user_folder}")
            continue

        c, f = copy_tree_files(default_configs_folder, app_folder / "local" / "cfg", log_lines)
        total_copied += c
        total_failed += f
        users_processed += 1

    log_lines.extend([
        f"Users processed: {users_processed}",
        f"Users skipped: {users_skipped}",
        f"Files copied: {total_copied}",
        f"Failed copies: {total_failed}",
    ])

    write_log(log_file, "CS2 Config Copy", log_lines)

    if total_copied == 0 and total_failed == 0:
        raise_error(f"No CS2 files were copied.\n\nSee log:\n{log_file}")

    return "\n".join([
        "Copy cs2_cfg completed.",
        f"Files copied: {total_copied}",
        f"Failed copies: {total_failed}",
        f"Users processed: {users_processed}",
        f"Users skipped: {users_skipped}",
        f"Log file: {log_file}",
    ])


def install_csgo_configs() -> str:
    base_folder = get_base_folder()
    log_file = get_log_file_path(base_folder)
    csgo_cfg_root = get_source_folder(base_folder, "csgo_cfg")

    default_configs_folder = csgo_cfg_root / "default_configs"
    additional_configs_folder = csgo_cfg_root / "additional_configs"
    launch_options_file = csgo_cfg_root / "launch_options.txt"
    video_files = [
        file_path for file_path in csgo_cfg_root.iterdir()
        if file_path.is_file() and file_path.suffix.lower() in CSGO_VIDEO_EXTENSIONS
    ]

    if (
        not has_any_files(default_configs_folder)
        and not has_any_files(additional_configs_folder)
        and not launch_options_file.exists()
        and not video_files
    ):
        raise_error(
            "No files were found in csgo_cfg.\n\n"
            f"Checked:\n{default_configs_folder}\n{additional_configs_folder}\n{launch_options_file}"
        )

    log_lines = [
        f"Base folder: {base_folder}",
        f"CS:GO cfg root: {csgo_cfg_root}",
        f"Default configs folder: {default_configs_folder}",
        f"Additional configs folder: {additional_configs_folder}",
        f"Launch options file: {launch_options_file}",
        f"Video files found: {len(video_files)}",
    ]

    steam_path = get_steam_path()
    library_folders = get_library_folders(steam_path)
    csgo_install_dir = find_csgo_install_dir(library_folders)
    user_folders = get_user_folders(steam_path)

    csgo_cfg_destination = csgo_install_dir / "csgo" / "cfg"
    csgo_videos_destination = csgo_install_dir / "csgo" / "panorama" / "videos"

    log_lines.extend([
        f"Steam path: {steam_path}",
        f"CS:GO install dir: {csgo_install_dir}",
        f"CS:GO cfg destination: {csgo_cfg_destination}",
        f"CS:GO videos destination: {csgo_videos_destination}",
        f"Steam user folders found: {len(user_folders)}",
    ])

    launch_options = ""
    if launch_options_file.exists() and launch_options_file.is_file():
        try:
            launch_options = launch_options_file.read_text(encoding="utf-8").strip()
        except Exception as e:
            raise_error(f"Failed to read launch_options.txt:\n{e}")

    total_copied = 0
    total_failed = 0
    users_processed = 0
    users_skipped = 0
    localconfigs_updated = 0

    c, f = copy_tree_files(additional_configs_folder, csgo_cfg_destination, log_lines)
    total_copied += c
    total_failed += f

    for video_file in video_files:
        c, f = copy_file(video_file, csgo_videos_destination / video_file.name, log_lines)
        total_copied += c
        total_failed += f

    for user_folder in user_folders:
        app_folder = user_folder / CSGO_APP_ID
        if not app_folder.exists():
            users_skipped += 1
            log_lines.append(f"SKIPPED USER (no {CSGO_APP_ID} folder): {user_folder}")
            continue

        c, f = copy_tree_files(default_configs_folder, app_folder / "local" / "cfg", log_lines)
        total_copied += c
        total_failed += f

        if launch_options:
            c, f = set_launch_options_for_user(user_folder, CSGO_APP_ID, launch_options, log_lines)
            localconfigs_updated += c
            total_failed += f

        users_processed += 1

    log_lines.extend([
        f"Users processed: {users_processed}",
        f"Users skipped: {users_skipped}",
        f"localconfig.vdf files updated: {localconfigs_updated}",
        f"Files copied: {total_copied}",
        f"Failed operations: {total_failed}",
    ])

    write_log(log_file, "CS:GO Config Copy", log_lines)

    if total_copied == 0 and total_failed == 0 and localconfigs_updated == 0:
        raise_error(f"No CS:GO files were copied.\n\nSee log:\n{log_file}")

    return "\n".join([
        "Copy csgo_cfg completed.",
        f"Files copied: {total_copied}",
        f"localconfig.vdf files updated: {localconfigs_updated}",
        f"Failed operations: {total_failed}",
        f"Users processed: {users_processed}",
        f"Users skipped: {users_skipped}",
        f"Log file: {log_file}",
    ])


def install_server_configs(server_folder: Path) -> str:
    base_folder = get_base_folder()
    log_file = get_log_file_path(base_folder)
    server_cfg_root = get_source_folder(base_folder, "cs2_server_cfg")
    server_folder = validate_server_folder(server_folder)

    additional_configs_folder = server_cfg_root / "additional_configs"
    admins_configs_folder = server_cfg_root / "admins_configs"
    plugins_folder = server_cfg_root / "plugins"
    gameinfo_file = server_cfg_root / "gameinfo.gi"
    server_bat_file = server_cfg_root / "server.bat"

    if (
        not has_any_files(additional_configs_folder)
        and not has_any_files(admins_configs_folder)
        and not has_any_files(plugins_folder)
        and not gameinfo_file.exists()
        and not server_bat_file.exists()
    ):
        raise_error(f"No files were found in cs2_server_cfg:\n{server_cfg_root}")

    log_lines = [
        f"Base folder: {base_folder}",
        f"Server cfg root: {server_cfg_root}",
        f"Selected server folder: {server_folder}",
    ]

    total_copied = 0
    total_failed = 0

    c, f = copy_tree_files(additional_configs_folder, server_folder / "game" / "csgo" / "cfg", log_lines)
    total_copied += c
    total_failed += f

    c, f = copy_tree_files(
        admins_configs_folder,
        server_folder / "game" / "csgo" / "addons" / "counterstrikesharp" / "configs",
        log_lines,
    )
    total_copied += c
    total_failed += f

    if gameinfo_file.exists() and gameinfo_file.is_file():
        c, f = copy_file(gameinfo_file, server_folder / "game" / "csgo" / "gameinfo.gi", log_lines)
        total_copied += c
        total_failed += f
    else:
        log_lines.append(f"SKIPPED missing file: {gameinfo_file}")

    if server_bat_file.exists() and server_bat_file.is_file():
        c, f = copy_file(server_bat_file, server_folder.parent / "server.bat", log_lines)
        total_copied += c
        total_failed += f
    else:
        log_lines.append(f"SKIPPED missing file: {server_bat_file}")

    c, f, plugins_processed = copy_plugin_files(plugins_folder, server_folder, log_lines)
    total_copied += c
    total_failed += f

    log_lines.extend([
        f"Plugins processed: {plugins_processed}",
        f"Files copied: {total_copied}",
        f"Failed operations: {total_failed}",
    ])

    write_log(log_file, "CS2 Server Config Copy", log_lines)

    if total_copied == 0 and total_failed == 0:
        raise_error(f"No server files were copied.\n\nSee log:\n{log_file}")

    return "\n".join([
        "Copy cs2_server_cfg completed.",
        f"Files copied: {total_copied}",
        f"Failed operations: {total_failed}",
        f"Plugins processed: {plugins_processed}",
        f"Log file: {log_file}",
    ])


# -----------------------------
# UI
# -----------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.resizable(False, False)
        self.server_dir_var = tk.StringVar()

        icon_path = get_app_icon_path()
        if icon_path is not None:
            try:
                self.iconbitmap(default=str(icon_path))
            except Exception:
                pass

        self._build_ui()
        self.update_idletasks()
        self.geometry(f"{self.winfo_reqwidth()}x{self.winfo_reqheight()}")

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=10)
        root.grid(sticky="nsew")

        title = ttk.Label(root, text=APP_TITLE, font=("Segoe UI", 12, "bold"))
        title.grid(row=0, column=0, sticky="w")

        red_warning = tk.Label(
            root,
            text="Close Steam before executing",
            fg="red",
            font=("Segoe UI", 9, "bold"),
            anchor="w",
            justify="left",
        )
        red_warning.grid(row=1, column=0, sticky="w", pady=(6, 1))

        yellow_warning = tk.Label(
            root,
            text="Make sure CS2/CS:GO are installed",
            fg="#b8860b",
            font=("Segoe UI", 9, "bold"),
            anchor="w",
            justify="left",
        )
        yellow_warning.grid(row=2, column=0, sticky="w", pady=(0, 8))

        cs2_frame = ttk.LabelFrame(root, text="CS2", padding=8)
        cs2_frame.grid(row=3, column=0, sticky="ew", pady=(0, 6))

        cs2_text = ttk.Label(
            cs2_frame,
            text="Copies files from cs2_cfg/ into their respective CS2 directories",
            wraplength=300,
            justify="left",
        )
        cs2_text.grid(row=0, column=0, sticky="w", pady=(0, 6))

        cs2_button = ttk.Button(cs2_frame, text="Copy cs2_cfg", command=self.on_install_cs2)
        cs2_button.grid(row=1, column=0, sticky="w")

        csgo_frame = ttk.LabelFrame(root, text="CS:GO", padding=8)
        csgo_frame.grid(row=4, column=0, sticky="ew", pady=(0, 6))

        csgo_text = ttk.Label(
            csgo_frame,
            text="Copies csgo_cfg/ into their respective CS:GO directories",
            wraplength=300,
            justify="left",
        )
        csgo_text.grid(row=0, column=0, sticky="w", pady=(0, 6))

        csgo_button = ttk.Button(csgo_frame, text="Copy csgo_cfg", command=self.on_install_csgo)
        csgo_button.grid(row=1, column=0, sticky="w")

        server_frame = ttk.LabelFrame(root, text="CS2 Server", padding=8)
        server_frame.grid(row=5, column=0, sticky="ew")

        server_notice = tk.Label(
            server_frame,
            text="Server installation folder (pick server/)",
            fg="red",
            font=("Segoe UI", 9, "bold"),
            anchor="w",
            justify="left",
        )
        server_notice.grid(row=0, column=0, sticky="w", pady=(0, 6))

        server_path_label = ttk.Label(server_frame, text="Server folder:")
        server_path_label.grid(row=1, column=0, sticky="w")

        server_path_row = ttk.Frame(server_frame)
        server_path_row.grid(row=2, column=0, sticky="ew", pady=(3, 6))

        server_path_entry = ttk.Entry(server_path_row, textvariable=self.server_dir_var, width=34)
        server_path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        browse_button = ttk.Button(server_path_row, text="Choose dir", command=self.on_browse_server_folder)
        browse_button.grid(row=0, column=1)

        server_text = ttk.Label(
            server_frame,
            text="Copies cs2_server_cfg/ into their respective server directories",
            wraplength=300,
            justify="left",
        )
        server_text.grid(row=3, column=0, sticky="w", pady=(0, 6))

        server_button = ttk.Button(server_frame, text="Copy cs2_server_cfg", command=self.on_install_server)
        server_button.grid(row=4, column=0, sticky="w")

        root.columnconfigure(0, weight=1)
        cs2_frame.columnconfigure(0, weight=1)
        csgo_frame.columnconfigure(0, weight=1)
        server_frame.columnconfigure(0, weight=1)
        server_path_row.columnconfigure(0, weight=1)

    def on_browse_server_folder(self) -> None:
        selected = filedialog.askdirectory(title="Select the server folder", mustexist=True)
        if selected:
            self.server_dir_var.set(selected)

    def _show_result(self, action) -> None:
        try:
            result = action()
            messagebox.showinfo(APP_TITLE, result, parent=self)
        except CopierError as e:
            messagebox.showerror(f"{APP_TITLE} - Error", str(e), parent=self)
        except Exception as e:
            messagebox.showerror(f"{APP_TITLE} - Error", f"Unexpected error:\n{e}", parent=self)

    def on_install_cs2(self) -> None:
        self._show_result(install_cs2_configs)

    def on_install_csgo(self) -> None:
        self._show_result(install_csgo_configs)

    def on_install_server(self) -> None:
        server_path = self.server_dir_var.get().strip()
        if not server_path:
            messagebox.showerror(f"{APP_TITLE} - Error", "Please choose the server folder first.", parent=self)
            return

        self._show_result(lambda: install_server_configs(Path(server_path)))


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
