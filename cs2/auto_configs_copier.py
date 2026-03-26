import shutil
import sys
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import winreg

import vdf


APP_TITLE = "CS2 Config Copier"
PLUGIN_BINARY_EXTENSIONS = {".dll", ".pdb"}


class CopierError(Exception):
    pass


def raise_error(message):
    raise CopierError(message)


def get_base_folder():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_runtime_base_folder():
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def get_app_icon_path():
    icon_path = get_runtime_base_folder() / "img" / "icon.ico"
    if icon_path.exists():
        return icon_path
    return None


def get_cfg_root_folder(base_folder: Path) -> Path:
    folder = base_folder / "cfg"
    if folder.exists() and folder.is_dir():
        return folder
    raise_error(f"Source cfg folder not found at:\n{folder}")


def get_server_cfg_root_folder(base_folder: Path) -> Path:
    folder = base_folder / "server_cfg"
    if folder.exists() and folder.is_dir():
        return folder
    raise_error(f"Source server_cfg folder not found at:\n{folder}")


def get_log_file_path(base_folder: Path) -> Path:
    return base_folder / "logs.txt"


def write_log(log_file: Path, section_title: str, lines: list[str]) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with log_file.open("a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {section_title}\n")
        for line in lines:
            f.write(f"{line}\n")
        f.write("\n")


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

    raise_error("Steam not found in registry.")


def get_library_folders(steam_path: Path) -> list[Path]:
    library_vdf_path = steam_path / "steamapps" / "libraryfolders.vdf"
    if not library_vdf_path.exists():
        raise_error(f"libraryfolders.vdf not found at:\n{library_vdf_path}")

    try:
        with library_vdf_path.open("r", encoding="utf-8") as f:
            kv = vdf.load(f)
    except Exception as e:
        raise_error(f"Failed to read libraryfolders.vdf:\n{e}")

    folders = []
    libraryfolders = kv.get("libraryfolders", {})

    for key, value in libraryfolders.items():
        if not str(key).isdigit():
            continue

        if isinstance(value, dict) and "path" in value:
            folders.append(Path(value["path"]))
        elif isinstance(value, str):
            folders.append(Path(value))

    if steam_path not in folders:
        folders.insert(0, steam_path)

    return folders


def find_cs2_game_folder(library_folders: list[Path]) -> Path:
    for lib in library_folders:
        candidate = lib / "steamapps" / "common" / "Counter-Strike Global Offensive" / "game" / "csgo"
        if candidate.exists():
            return candidate

    raise_error("CS2 game folder not found in any Steam library.")


def get_user_folders(steam_path: Path) -> list[Path]:
    userdata_folder = steam_path / "userdata"
    if not userdata_folder.exists():
        raise_error(f"Steam userdata folder not found at:\n{userdata_folder}")

    return [p for p in userdata_folder.iterdir() if p.is_dir() and p.name.isdigit()]


def has_any_files(folder: Path) -> bool:
    return folder.exists() and folder.is_dir() and any(p.is_file() for p in folder.rglob("*"))


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
        rel_path = src_file.relative_to(src_root)
        c, f = copy_file(src_file, dst_root / rel_path, log_lines)
        copied += c
        failed += f

    return copied, failed


def is_allowed_plugin_binary(file_path: Path) -> bool:
    return file_path.suffix.lower() in PLUGIN_BINARY_EXTENSIONS or file_path.name.lower().endswith(".deps.json")


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
        dest_plugin_folder = dest_plugins_root / plugin_folder.name

        for child in plugin_folder.iterdir():
            if child.is_file() and is_allowed_plugin_binary(child):
                c, f = copy_file(child, dest_plugin_folder / child.name, log_lines)
                copied += c
                failed += f

        cfg_folder = plugin_folder / "cfg"
        if cfg_folder.exists() and cfg_folder.is_dir():
            c, f = copy_tree_files(cfg_folder, dest_plugin_configs_root / plugin_folder.name, log_lines)
            copied += c
            failed += f

    return copied, failed, plugins_processed


def validate_server_folder(server_folder: Path) -> Path:
    if not server_folder.exists() or not server_folder.is_dir():
        raise_error(f"Selected server folder does not exist:\n{server_folder}")

    csgo_folder = server_folder / "game" / "csgo"
    if not csgo_folder.exists() or not csgo_folder.is_dir():
        raise_error(
            "The selected folder does not look like a valid /server folder.\n\n"
            f"Missing:\n{csgo_folder}"
        )

    return server_folder


def install_basic_configs() -> str:
    base_folder = get_base_folder()
    log_file = get_log_file_path(base_folder)
    cfg_root = get_cfg_root_folder(base_folder)

    default_configs_folder = cfg_root / "default_configs"
    additional_configs_folder = cfg_root / "additional_configs"

    if not has_any_files(default_configs_folder) and not has_any_files(additional_configs_folder):
        raise_error(
            "No basic config files were found.\n\n"
            f"Expected files inside:\n{default_configs_folder}\n{additional_configs_folder}"
        )

    log_lines = [
        f"Base folder: {base_folder}",
        f"CFG root folder: {cfg_root}",
        f"Default configs folder: {default_configs_folder}",
        f"Additional configs folder: {additional_configs_folder}",
    ]

    steam_path = get_steam_path()
    library_folders = get_library_folders(steam_path)
    cs2_game_folder = find_cs2_game_folder(library_folders)
    user_folders = get_user_folders(steam_path)

    log_lines.extend([
        f"Steam path: {steam_path}",
        f"CS2 game folder: {cs2_game_folder}",
        f"Steam user folders found: {len(user_folders)}",
    ])

    total_copied = 0
    total_failed = 0
    users_processed = 0
    users_skipped = 0

    c, f = copy_tree_files(additional_configs_folder, cs2_game_folder / "cfg", log_lines)
    total_copied += c
    total_failed += f

    for user_folder in user_folders:
        app_730 = user_folder / "730"
        if not app_730.exists():
            users_skipped += 1
            log_lines.append(f"SKIPPED USER (no 730 folder): {user_folder}")
            continue

        c, f = copy_tree_files(default_configs_folder, app_730 / "local" / "cfg", log_lines)
        total_copied += c
        total_failed += f
        users_processed += 1

    log_lines.extend([
        f"Users processed: {users_processed}",
        f"Users skipped: {users_skipped}",
        f"Files copied: {total_copied}",
        f"Failed copies: {total_failed}",
    ])

    write_log(log_file, "Basic CFG Install", log_lines)

    if total_copied == 0 and total_failed == 0:
        raise_error(f"No basic config files were copied.\n\nSee log:\n{log_file}")

    return "\n".join([
        "Basic cfg install completed.",
        f"Files copied: {total_copied}",
        f"Failed copies: {total_failed}",
        f"Users processed: {users_processed}",
        f"Users skipped: {users_skipped}",
        f"Log file: {log_file}",
    ])


def install_server_configs(server_folder: Path, install_plugins: bool) -> str:
    base_folder = get_base_folder()
    log_file = get_log_file_path(base_folder)
    server_cfg_root = get_server_cfg_root_folder(base_folder)
    server_folder = validate_server_folder(server_folder)

    additional_configs_folder = server_cfg_root / "additional_configs"
    admins_configs_folder = server_cfg_root / "admins_configs"
    plugins_folder = server_cfg_root / "plugins"
    gameinfo_file = server_cfg_root / "gameinfo.gi"
    server_bat_file = server_cfg_root / "server.bat"

    if (
        not has_any_files(additional_configs_folder)
        and not has_any_files(admins_configs_folder)
        and not gameinfo_file.exists()
        and not server_bat_file.exists()
        and (not install_plugins or not plugins_folder.exists())
    ):
        raise_error(f"No server config files were found inside:\n{server_cfg_root}")

    log_lines = [
        f"Base folder: {base_folder}",
        f"Server cfg root: {server_cfg_root}",
        f"Selected server folder: {server_folder}",
        f"Install plugins: {install_plugins}",
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

    plugins_processed = 0
    if install_plugins:
        c, f, plugins_processed = copy_plugin_files(plugins_folder, server_folder, log_lines)
        total_copied += c
        total_failed += f
    else:
        log_lines.append("SKIPPED plugins install by user choice")

    log_lines.extend([
        f"Files copied: {total_copied}",
        f"Failed copies: {total_failed}",
        f"Plugins processed: {plugins_processed}",
    ])

    write_log(log_file, "Server CFG Install", log_lines)

    if total_copied == 0 and total_failed == 0:
        raise_error(f"No server config files were copied.\n\nSee log:\n{log_file}")

    return "\n".join([
        "Server cfg install completed.",
        f"Files copied: {total_copied}",
        f"Failed copies: {total_failed}",
        f"Plugins processed: {plugins_processed if install_plugins else 0}",
        f"Log file: {log_file}",
    ])


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.resizable(False, False)
        self.server_dir_var = tk.StringVar()
        self.install_plugins_var = tk.BooleanVar(value=True)

        icon_path = get_app_icon_path()
        if icon_path is not None:
            try:
                self.iconbitmap(default=str(icon_path))
            except Exception:
                pass

        self._build_ui()

    def _build_ui(self):
        root = ttk.Frame(self, padding=16)
        root.grid(sticky="nsew")

        title = ttk.Label(root, text=APP_TITLE, font=("Segoe UI", 12, "bold"))
        title.grid(row=0, column=0, columnspan=3, sticky="w")

        basic_frame = ttk.LabelFrame(root, text="Basic cfg install", padding=12)
        basic_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(12, 8))

        basic_text = ttk.Label(
            basic_frame,
            text="Installs cfg/default_configs and cfg/additional_configs to your local CS2 folders.",
            wraplength=520,
            justify="left",
        )
        basic_text.grid(row=0, column=0, sticky="w", pady=(0, 10))

        basic_button = ttk.Button(basic_frame, text="Install basic cfg", command=self.on_install_basic)
        basic_button.grid(row=1, column=0, sticky="w")

        server_frame = ttk.LabelFrame(root, text="Server cfg install", padding=12)
        server_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(4, 0))

        warning_label = tk.Label(
            server_frame,
            text="* Install only if you set up a server already.",
            fg="red",
            anchor="w",
        )
        warning_label.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        server_path_label = ttk.Label(server_frame, text="Server folder:")
        server_path_label.grid(row=1, column=0, sticky="w")

        server_path_entry = ttk.Entry(server_frame, textvariable=self.server_dir_var, width=58)
        server_path_entry.grid(row=2, column=0, columnspan=2, sticky="ew", padx=(0, 8))

        browse_button = ttk.Button(server_frame, text="Choose dir", command=self.on_browse_server_folder)
        browse_button.grid(row=2, column=2, sticky="ew")

        plugins_check = ttk.Checkbutton(
            server_frame,
            text="Install plugins on the server",
            variable=self.install_plugins_var,
        )
        plugins_check.grid(row=3, column=0, columnspan=3, sticky="w", pady=(10, 10))

        server_button = ttk.Button(server_frame, text="Install server cfg", command=self.on_install_server)
        server_button.grid(row=4, column=0, sticky="w")

        for i in range(3):
            root.columnconfigure(i, weight=1)
            server_frame.columnconfigure(i, weight=1)

    def on_browse_server_folder(self):
        selected = filedialog.askdirectory(title="Select the /server folder", mustexist=True)
        if selected:
            self.server_dir_var.set(selected)

    def on_install_basic(self):
        try:
            result = install_basic_configs()
            messagebox.showinfo(APP_TITLE, result, parent=self)
        except CopierError as e:
            messagebox.showerror(f"{APP_TITLE} - Error", str(e), parent=self)
        except Exception as e:
            messagebox.showerror(f"{APP_TITLE} - Error", f"Unexpected error:\n{e}", parent=self)

    def on_install_server(self):
        server_path = self.server_dir_var.get().strip()
        if not server_path:
            messagebox.showerror(f"{APP_TITLE} - Error", "Please choose the /server folder first.", parent=self)
            return

        try:
            result = install_server_configs(Path(server_path), self.install_plugins_var.get())
            messagebox.showinfo(APP_TITLE, result, parent=self)
        except CopierError as e:
            messagebox.showerror(f"{APP_TITLE} - Error", str(e), parent=self)
        except Exception as e:
            messagebox.showerror(f"{APP_TITLE} - Error", f"Unexpected error:\n{e}", parent=self)


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()