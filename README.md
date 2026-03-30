# CS2ConfigCopier

[![Donate](https://img.shields.io/badge/Support-Donatello-blue)](https://donatello.to/opalgeorgii)

## Overview

**CS2ConfigCopier** is a Windows tool for quickly saving and restoring your **CS2**, **CS2 server**, **CS:GO**, and **Steam account** settings to the correct folders for all Steam accounts automatically.

It is designed for people who want to keep their configs organized, restore settings faster, and reuse the same setup across multiple Steam accounts without manually copying files into each directory. It can also help preserve Steam settings such as Invisible mode and other Steam- or game-related settings when reinstalling Steam or Windows.

### You can download the latest version here: [Releases](https://github.com/opalgeorgii/CS2ConfigCopier/releases)

### You can view the screenshots here: [Screenshots](#screenshots)

## Important

**Close Steam completely before running the program.**

If Steam is still running, some files may not copy correctly, or Steam may overwrite them after the program finishes.

## Usage

The program automatically detects Steam regardless of where it is installed, finds the installed game folders, and saves or copies files to the correct folders for **all** Steam accounts that have been logged in on that PC.

1. Download the latest version from the [Releases](https://github.com/opalgeorgii/CS2ConfigCopier/releases) page.
2. Configure your CS2, CS:GO, and Steam settings manually once on your primary account.  
   If you have other accounts, configure only the Steam settings on them.  
   Skip this step if everything is already set up.
3. Close Steam completely.
4. Open `CS2ConfigCopier.exe` and click **Load** to load all current Steam account IDs.
5. Select the ID that corresponds to your primary account.  
   If you do not know your Steam ID, use [Steam32ID](https://steamid.xyz/) and paste your Steam profile link there.
6. Click **Copy all Steam settings** to copy Steam settings from all accounts into the `steam_account_settings/` folder that will be created.
7. Click **Copy current CS2 settings** or **Copy current CS:GO settings** to copy config files from the selected primary account.
8. If you do not need the `cs2_cfg/`, `cs2_server_cfg/`, `csgo_cfg/`, or `steam_account_settings/` folders, you can delete them.
9. Inside the first three folders, you will also find `additional_configs/` or other files that you may want to replace or remove. These are my own configs, so feel free to use them if you want.
10. It is recommended not to delete base folders such as `cs2_cfg/`, `cs2_server_cfg/`, or `csgo_cfg/`. It is better to keep the folder structure and only remove the files you do not need, although this is not mandatory.
11. Once your configs are copied, save those folders somewhere safe. Later, if you reinstall Windows, move to another PC, go to a computer club, or lose your settings for any reason, you can restore them by opening `CS2ConfigCopier.exe` and clicking either **Paste all Steam settings**, **Paste cs2_cfg**, or **Paste csgo_cfg**.
12. It is best not to modify the `default_configs/` folder. You can delete or replace other files if needed, but keep the same overall folder structure as in the downloaded project.
13. When everything has been copied successfully, open Steam again.

## CS2 Server Installation

At the bottom of the program, you can find the **CS2 Server** section. If your CS2 server is already set up, the program can automatically copy all required server config files, plugins, and plugin cfg files.

### How to set it up

- Follow this dedicated server guide: [Server installation guide](https://hub.tcno.co/games/cs2/dedicated_server/)
- Follow this CounterStrikeSharp guide: [Counter-Strike Sharp installation guide](https://docs.cssharp.dev/docs/guides/getting-started.html)
- Put your server configs, plugins, and plugin cfg files into their respective folders inside `cs2_server_cfg/`
- Open `CS2ConfigCopier.exe`
- Click **Choose dir** and select your server installation folder (`/server`)
- Click **Paste cs2_server_cfg** to copy everything

**Only the files that exist in your project folders will be copied.**

## Recommended Setup

A practical way to use this project is to keep the provided folder structure and simply replace the included files with your own.

Recommended approach:

- keep the folder structure unchanged
- replace existing config files with your own versions
- remove files you do not need
- leave unrelated folders in place for easier maintenance

This makes the project easier to update and helps avoid breaking the intended layout.

**Only the files that exist in your project folders will be copied.**

## Notes

- Works with multiple Steam accounts on the same PC
- Missing files or folders are skipped and will not be copied
- Only the files you keep in the project structure are copied
- If Steam, required game folders, or config folders cannot be found, the program will show an error popup
- For `.exe` usage, keep the expected folder structure in the correct relative location
- Always close Steam completely before running the program

### CS:GO Danger Zone Note

If you use a **Danger Zone cfg** for CS:GO, it must be applied in the correct order:

1. execute it in the **main menu before loading the map**
2. execute it **again after the map has loaded**

If you skip the first step, CS:GO may crash.

## Screenshots

### Main Window

![Main window](screenshots/main-window.jpg)

Shows the main application layout.

### Folder Structure

![Folder structure](screenshots/folder-structure.jpg)

Shows the expected project structure.

## Requirements

- **Windows**
- **Steam installed**
- **Counter-Strike 2 and/or CS:GO installed**
- Python only if you want to run the `.py` file directly

If you use the compiled `.exe`, Python is not required.

## Support

If you would like to support me, you can donate here:

**[Donate via Donatello](https://donatello.to/opalgeorgii)**

## Related Project

For my Counter-Strike 2 plugin project, see:

- [WallhackPluginCS2](https://github.com/opalgeorgii/WallhackPluginCS2)

## Contact

If you find bugs or want to suggest improvements, open an issue in the repository.
