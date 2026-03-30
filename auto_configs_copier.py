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
STEAM_SETTINGS_FILE_NAME = "localconfig.vdf"
STEAM_WARNING_COLOR = "#c97a00"


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


def get_required_file(file_path: Path, description: str) -> Path:
    if file_path.exists() and file_path.is_file():
        return file_path
    raise_error(f"{description} was not found:\n{file_path}")


def remove_existing_path(path: Path, log_lines: list[str]) -> None:
    if not path.exists():
        return

    try:
        if path.is_dir():
            shutil.rmtree(path)
            log_lines.append(f"REMOVED DIR: {path}")
        else:
            path.unlink()
            log_lines.append(f"REMOVED FILE: {path}")
    except Exception as e:
        raise_error(f"Failed to remove existing path:\n{path}\n{e}")


# -----------------------------
# Minimal VDF reader
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


def _find_existing_key_ci(mapping: OrderedDict | dict, wanted_key: str) -> str | None:
    wanted_lower = wanted_key.lower()
    for existing_key in mapping.keys():
        if str(existing_key).lower() == wanted_lower:
            return str(existing_key)
    return None


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


def get_userdata_folder(steam_path: Path) -> Path:
    return steam_path / "userdata"


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
    userdata_folder = get_userdata_folder(steam_path)
    if not userdata_folder.exists():
        raise_error(f"Steam userdata folder was not found:\n{userdata_folder}")

    return [p for p in userdata_folder.iterdir() if p.is_dir() and p.name.isdigit()]


def get_user_ids_from_userdata(steam_path: Path) -> list[str]:
    user_folders = get_user_folders(steam_path)
    return sorted((folder.name for folder in user_folders), key=lambda value: int(value))


def get_target_user_folders(steam_path: Path, log_lines: list[str]) -> list[Path]:
    user_folders = get_user_folders(steam_path)
    log_lines.append(f"Using userdata folders directly: {len(user_folders)}")
    return user_folders


def get_selected_user_folder(steam_path: Path, user_id: str) -> Path:
    if not user_id or not user_id.isdigit():
        raise_error("Please choose a primary Steam account first.")

    user_folder = get_userdata_folder(steam_path) / user_id
    if not user_folder.exists() or not user_folder.is_dir():
        raise_error(f"The selected Steam account was not found:\n{user_folder}")

    return user_folder


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


def copy_app_folder_to_users(source_app_folder: Path, user_folders: list[Path], log_lines: list[str]) -> tuple[int, int, int]:
    if not source_app_folder.exists() or not source_app_folder.is_dir():
        log_lines.append(f"SKIPPED missing app folder: {source_app_folder}")
        return 0, 0, 0

    copied = 0
    failed = 0
    users_processed = 0

    for user_folder in user_folders:
        dst_app_folder = user_folder / source_app_folder.name
        c, f = copy_tree_files(source_app_folder, dst_app_folder, log_lines)
        copied += c
        failed += f
        users_processed += 1

    return copied, failed, users_processed


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
# Steam exports / snapshots
# -----------------------------

def load_steam_account_ids() -> list[str]:
    steam_path = get_steam_path()
    return get_user_ids_from_userdata(steam_path)


def export_all_steam_settings() -> str:
    base_folder = get_base_folder()
    log_file = get_log_file_path(base_folder)
    steam_path = get_steam_path()
    user_folders = get_user_folders(steam_path)
    export_root = base_folder / "steam_account_settings"

    if not user_folders:
        raise_error(f"No Steam account folders were found in:\n{get_userdata_folder(steam_path)}")

    log_lines = [
        f"Base folder: {base_folder}",
        f"Steam path: {steam_path}",
        f"Userdata folder: {get_userdata_folder(steam_path)}",
        f"Export folder: {export_root}",
        f"Steam accounts found: {len(user_folders)}",
    ]

    remove_existing_path(export_root, log_lines)

    copied = 0
    failed = 0
    missing = 0

    for user_folder in user_folders:
        src_file = user_folder / "config" / STEAM_SETTINGS_FILE_NAME
        dst_file = export_root / user_folder.name / "config" / STEAM_SETTINGS_FILE_NAME

        if not src_file.exists() or not src_file.is_file():
            missing += 1
            log_lines.append(f"SKIPPED missing file: {src_file}")
            continue

        c, f = copy_file(src_file, dst_file, log_lines)
        copied += c
        failed += f

    log_lines.extend([
        f"Steam settings copied: {copied}",
        f"Steam settings missing: {missing}",
        f"Steam settings failed: {failed}",
    ])
    write_log(log_file, "Steam Settings Export", log_lines)

    if copied == 0:
        raise_error(
            "No Steam settings files were found to copy.\n\n"
            f"Expected file:\n{STEAM_SETTINGS_FILE_NAME}\n\n"
            f"See log:\n{log_file}"
        )

    return "\n".join([
        "Copy all Steam settings completed.",
        f"Steam accounts found: {len(user_folders)}",
        f"Settings copied: {copied}",
        f"Missing settings files: {missing}",
        f"Failed copies: {failed}",
        f"Saved to: {export_root}",
        f"Log file: {log_file}",
    ])


def import_all_steam_settings() -> str:
    base_folder = get_base_folder()
    log_file = get_log_file_path(base_folder)
    steam_path = get_steam_path()
    userdata_folder = get_userdata_folder(steam_path)
    import_root = base_folder / "steam_account_settings"

    if not import_root.exists() or not import_root.is_dir():
        raise_error(f"Saved Steam settings folder was not found:\n{import_root}")

    saved_user_folders = [
        folder for folder in import_root.iterdir()
        if folder.is_dir() and folder.name.isdigit()
    ]
    saved_user_folders.sort(key=lambda folder: int(folder.name))

    if not saved_user_folders:
        raise_error(f"No saved Steam account settings were found in:\n{import_root}")

    log_lines = [
        f"Base folder: {base_folder}",
        f"Steam path: {steam_path}",
        f"Userdata folder: {userdata_folder}",
        f"Import folder: {import_root}",
        f"Saved Steam accounts found: {len(saved_user_folders)}",
    ]

    copied = 0
    failed = 0
    missing = 0

    for saved_user_folder in saved_user_folders:
        src_file = saved_user_folder / "config" / STEAM_SETTINGS_FILE_NAME
        dst_file = userdata_folder / saved_user_folder.name / "config" / STEAM_SETTINGS_FILE_NAME

        if not src_file.exists() or not src_file.is_file():
            missing += 1
            log_lines.append(f"SKIPPED missing file: {src_file}")
            continue

        c, f = copy_file(src_file, dst_file, log_lines)
        copied += c
        failed += f

    log_lines.extend([
        f"Steam settings pasted: {copied}",
        f"Steam settings missing: {missing}",
        f"Steam settings failed: {failed}",
    ])
    write_log(log_file, "Steam Settings Import", log_lines)

    if copied == 0:
        raise_error(
            "No Steam settings files were pasted.\n\n"
            f"Expected file:\n{STEAM_SETTINGS_FILE_NAME}\n\n"
            f"See log:\n{log_file}"
        )

    return "\n".join([
        "Paste all Steam settings completed.",
        f"Saved Steam accounts found: {len(saved_user_folders)}",
        f"Settings pasted: {copied}",
        f"Missing settings files: {missing}",
        f"Failed copies: {failed}",
        f"Source folder: {import_root}",
        f"Log file: {log_file}",
    ])


def export_selected_user_app_settings(app_id: str, config_root_name: str, selected_user_id: str, game_name: str) -> str:
    base_folder = get_base_folder()
    log_file = get_log_file_path(base_folder)
    steam_path = get_steam_path()
    user_folder = get_selected_user_folder(steam_path, selected_user_id)
    source_app_folder = user_folder / app_id
    destination_folder = base_folder / config_root_name / "default_configs" / app_id

    if not source_app_folder.exists() or not source_app_folder.is_dir():
        raise_error(f"{game_name} is not installed.")

    log_lines = [
        f"Base folder: {base_folder}",
        f"Steam path: {steam_path}",
        f"Selected Steam account: {selected_user_id}",
        f"Source folder: {source_app_folder}",
        f"Destination folder: {destination_folder}",
    ]

    remove_existing_path(destination_folder, log_lines)
    copied, failed = copy_tree_files(source_app_folder, destination_folder, log_lines)

    log_lines.extend([
        f"Files copied: {copied}",
        f"Failed copies: {failed}",
    ])
    write_log(log_file, f"{game_name} Current Settings Export", log_lines)

    if copied == 0 and failed == 0:
        raise_error(f"No {game_name} files were copied.\n\nSee log:\n{log_file}")

    return "\n".join([
        f"Copy current {game_name} settings completed.",
        f"Primary Steam account: {selected_user_id}",
        f"Files copied: {copied}",
        f"Failed copies: {failed}",
        f"Saved to: {destination_folder}",
        f"Log file: {log_file}",
    ])


def copy_current_cs2_settings(selected_user_id: str) -> str:
    return export_selected_user_app_settings(CS2_APP_ID, "cs2_cfg", selected_user_id, "CS2")


def copy_current_csgo_settings(selected_user_id: str) -> str:
    return export_selected_user_app_settings(CSGO_APP_ID, "csgo_cfg", selected_user_id, "CS:GO")


# -----------------------------
# Install operations
# -----------------------------

def install_cs2_configs() -> str:
    base_folder = get_base_folder()
    log_file = get_log_file_path(base_folder)
    cs2_cfg_root = get_source_folder(base_folder, "cs2_cfg")

    default_configs_folder = cs2_cfg_root / "default_configs"
    source_user_app_folder = default_configs_folder / CS2_APP_ID
    additional_configs_folder = cs2_cfg_root / "additional_configs"

    if not has_any_files(source_user_app_folder) and not has_any_files(additional_configs_folder):
        raise_error(
            "No files were found in cs2_cfg.\n\n"
            f"Checked:\n{source_user_app_folder}\n{additional_configs_folder}"
        )

    log_lines = [
        f"Base folder: {base_folder}",
        f"CS2 cfg root: {cs2_cfg_root}",
        f"Source 730 folder: {source_user_app_folder}",
        f"Additional configs folder: {additional_configs_folder}",
    ]

    steam_path = get_steam_path()
    library_folders = get_library_folders(steam_path)
    user_folders = get_target_user_folders(steam_path, log_lines)

    log_lines.extend([
        f"Steam path: {steam_path}",
        f"Steam target user folders: {len(user_folders)}",
    ])

    total_copied = 0
    total_failed = 0
    users_processed = 0

    cs2_install_dir = find_cs2_install_dir(library_folders)
    cs2_cfg_destination = cs2_install_dir / "game" / "csgo" / "cfg"

    log_lines.extend([
        f"CS2 install dir: {cs2_install_dir}",
        f"CS2 cfg destination: {cs2_cfg_destination}",
    ])

    c, f = copy_tree_files(additional_configs_folder, cs2_cfg_destination, log_lines)
    total_copied += c
    total_failed += f

    c, f, users_processed = copy_app_folder_to_users(source_user_app_folder, user_folders, log_lines)
    total_copied += c
    total_failed += f

    log_lines.extend([
        f"Users processed: {users_processed}",
        f"Files copied: {total_copied}",
        f"Failed copies: {total_failed}",
    ])

    write_log(log_file, "CS2 Config Paste", log_lines)

    if total_copied == 0 and total_failed == 0:
        raise_error(f"No CS2 files were pasted.\n\nSee log:\n{log_file}")

    return "\n".join([
        "Paste cs2_cfg completed.",
        f"Files copied: {total_copied}",
        f"Failed copies: {total_failed}",
        f"Users processed: {users_processed}",
        f"Log file: {log_file}",
    ])


def install_csgo_configs() -> str:
    base_folder = get_base_folder()
    log_file = get_log_file_path(base_folder)
    csgo_cfg_root = get_source_folder(base_folder, "csgo_cfg")

    default_configs_folder = csgo_cfg_root / "default_configs"
    source_user_app_folder = default_configs_folder / CSGO_APP_ID
    additional_configs_folder = csgo_cfg_root / "additional_configs"
    video_files = [
        file_path for file_path in csgo_cfg_root.iterdir()
        if file_path.is_file() and file_path.suffix.lower() in CSGO_VIDEO_EXTENSIONS
    ]

    if (
        not has_any_files(source_user_app_folder)
        and not has_any_files(additional_configs_folder)
        and not video_files
    ):
        raise_error(
            "No files were found in csgo_cfg.\n\n"
            f"Checked:\n{source_user_app_folder}\n{additional_configs_folder}"
        )

    log_lines = [
        f"Base folder: {base_folder}",
        f"CS:GO cfg root: {csgo_cfg_root}",
        f"Source 4465480 folder: {source_user_app_folder}",
        f"Additional configs folder: {additional_configs_folder}",
        f"Video files found: {len(video_files)}",
    ]

    steam_path = get_steam_path()
    library_folders = get_library_folders(steam_path)
    user_folders = get_target_user_folders(steam_path, log_lines)

    log_lines.extend([
        f"Steam path: {steam_path}",
        f"Steam target user folders: {len(user_folders)}",
    ])

    total_copied = 0
    total_failed = 0
    users_processed = 0

    csgo_install_dir = find_csgo_install_dir(library_folders)
    csgo_cfg_destination = csgo_install_dir / "csgo" / "cfg"
    csgo_videos_destination = csgo_install_dir / "csgo" / "panorama" / "videos"

    log_lines.extend([
        f"CS:GO install dir: {csgo_install_dir}",
        f"CS:GO cfg destination: {csgo_cfg_destination}",
        f"CS:GO videos destination: {csgo_videos_destination}",
    ])

    c, f = copy_tree_files(additional_configs_folder, csgo_cfg_destination, log_lines)
    total_copied += c
    total_failed += f

    for video_file in video_files:
        c, f = copy_file(video_file, csgo_videos_destination / video_file.name, log_lines)
        total_copied += c
        total_failed += f

    c, f, users_processed = copy_app_folder_to_users(source_user_app_folder, user_folders, log_lines)
    total_copied += c
    total_failed += f

    log_lines.extend([
        f"Users processed: {users_processed}",
        f"Files copied: {total_copied}",
        f"Failed operations: {total_failed}",
    ])

    write_log(log_file, "CS:GO Config Paste", log_lines)

    if total_copied == 0 and total_failed == 0:
        raise_error(f"No CS:GO files were pasted.\n\nSee log:\n{log_file}")

    return "\n".join([
        "Paste csgo_cfg completed.",
        f"Files copied: {total_copied}",
        f"Failed operations: {total_failed}",
        f"Users processed: {users_processed}",
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

    write_log(log_file, "CS2 Server Config Paste", log_lines)

    if total_copied == 0 and total_failed == 0:
        raise_error(f"No server files were copied.\n\nSee log:\n{log_file}")

    return "\n".join([
        "Paste cs2_server_cfg completed.",
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
        self.primary_account_var = tk.StringVar()

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
            fg=STEAM_WARNING_COLOR,
            font=("Segoe UI", 9, "bold"),
            anchor="w",
            justify="left",
        )
        yellow_warning.grid(row=2, column=0, sticky="w", pady=(0, 6))

        steam_frame = ttk.LabelFrame(root, text="Steam", padding=6)
        steam_frame.grid(row=3, column=0, sticky="ew", pady=(0, 6))

        primary_label = ttk.Label(steam_frame, text="Choose primary Steam account")
        primary_label.grid(row=0, column=0, sticky="w", padx=(0, 3))

        self.primary_account_combo = ttk.Combobox(
            steam_frame,
            textvariable=self.primary_account_var,
            state="readonly",
            width=16,
            values=[],
        )
        self.primary_account_combo.grid(row=0, column=1, sticky="w", padx=(0, 3))

        load_accounts_button = ttk.Button(
            steam_frame,
            text="Load",
            command=self.on_load_steam_accounts,
        )
        load_accounts_button.grid(row=0, column=2, sticky="w")

        copy_steam_settings_button = ttk.Button(
            steam_frame,
            text="Copy all Steam settings",
            command=self.on_copy_all_steam_settings,
        )
        copy_steam_settings_button.grid(row=1, column=0, sticky="w", pady=(3, 0), padx=(0, 2))

        paste_steam_settings_button = ttk.Button(
            steam_frame,
            text="Paste all Steam settings",
            command=self.on_paste_all_steam_settings,
        )
        paste_steam_settings_button.grid(row=1, column=1, columnspan=2, sticky="e", pady=(3, 0))

        cs2_frame = ttk.LabelFrame(root, text="CS2", padding=6)
        cs2_frame.grid(row=4, column=0, sticky="ew", pady=(0, 6))

        cs2_text = ttk.Label(
            cs2_frame,
            text="Copies cs2_cfg/ files to CS2 directories",
            wraplength=300,
            justify="left",
        )
        cs2_text.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))

        copy_current_cs2_button = ttk.Button(
            cs2_frame,
            text="Copy current CS2 settings",
            command=self.on_copy_current_cs2,
        )
        copy_current_cs2_button.grid(row=1, column=0, sticky="w", padx=(0, 2))

        paste_cs2_button = ttk.Button(cs2_frame, text="Paste cs2_cfg", command=self.on_install_cs2)
        paste_cs2_button.grid(row=1, column=1, sticky="e")

        csgo_frame = ttk.LabelFrame(root, text="CS:GO", padding=6)
        csgo_frame.grid(row=5, column=0, sticky="ew", pady=(0, 6))

        csgo_text = ttk.Label(
            csgo_frame,
            text="Copies csgo_cfg/ files to CS:GO directories",
            wraplength=300,
            justify="left",
        )
        csgo_text.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))

        copy_current_csgo_button = ttk.Button(
            csgo_frame,
            text="Copy current CS:GO settings",
            command=self.on_copy_current_csgo,
        )
        copy_current_csgo_button.grid(row=1, column=0, sticky="w", padx=(0, 2))

        paste_csgo_button = ttk.Button(csgo_frame, text="Paste csgo_cfg", command=self.on_install_csgo)
        paste_csgo_button.grid(row=1, column=1, sticky="e")

        server_frame = ttk.LabelFrame(root, text="CS2 Server", padding=6)
        server_frame.grid(row=6, column=0, sticky="ew")

        server_notice = tk.Label(
            server_frame,
            text="Server installation folder (pick server/)",
            fg="red",
            font=("Segoe UI", 9, "bold"),
            anchor="w",
            justify="left",
        )
        server_notice.grid(row=0, column=0, sticky="w", pady=(0, 4))

        server_path_label = ttk.Label(server_frame, text="Server folder:")
        server_path_label.grid(row=1, column=0, sticky="w")

        server_path_row = ttk.Frame(server_frame)
        server_path_row.grid(row=2, column=0, sticky="ew", pady=(3, 4))

        server_path_entry = ttk.Entry(server_path_row, textvariable=self.server_dir_var, width=34)
        server_path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        browse_button = ttk.Button(server_path_row, text="Choose dir", command=self.on_browse_server_folder)
        browse_button.grid(row=0, column=1)

        server_text = ttk.Label(
            server_frame,
            text="Copies cs2_server_cfg/ files to server directories",
            wraplength=300,
            justify="left",
        )
        server_text.grid(row=3, column=0, sticky="w", pady=(0, 4))

        server_button = ttk.Button(server_frame, text="Paste cs2_server_cfg", command=self.on_install_server)
        server_button.grid(row=4, column=0, sticky="w")

        root.columnconfigure(0, weight=1)
        steam_frame.columnconfigure(0, weight=1)
        steam_frame.columnconfigure(1, weight=1)
        cs2_frame.columnconfigure(0, weight=1)
        cs2_frame.columnconfigure(1, weight=1)
        csgo_frame.columnconfigure(0, weight=1)
        csgo_frame.columnconfigure(1, weight=1)
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

    def _confirm_overwrite(self) -> bool:
        return messagebox.askyesno(
            APP_TITLE,
            "Your current Steam settings will be overwritten",
            parent=self,
        )

    def on_load_steam_accounts(self) -> None:
        try:
            user_ids = load_steam_account_ids()
            if not user_ids:
                raise_error("No Steam accounts were found.")

            self.primary_account_combo["values"] = user_ids
            self.primary_account_var.set(user_ids[0])
        except CopierError as e:
            messagebox.showerror(f"{APP_TITLE} - Error", str(e), parent=self)
        except Exception as e:
            messagebox.showerror(f"{APP_TITLE} - Error", f"Unexpected error:\n{e}", parent=self)

    def on_copy_all_steam_settings(self) -> None:
        if not self._confirm_overwrite():
            return
        self._show_result(export_all_steam_settings)

    def on_paste_all_steam_settings(self) -> None:
        self._show_result(import_all_steam_settings)

    def on_copy_current_cs2(self) -> None:
        if not self._confirm_overwrite():
            return
        self._show_result(lambda: copy_current_cs2_settings(self.primary_account_var.get().strip()))

    def on_copy_current_csgo(self) -> None:
        if not self._confirm_overwrite():
            return
        self._show_result(lambda: copy_current_csgo_settings(self.primary_account_var.get().strip()))

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
