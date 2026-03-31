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

### First-time setup

0. Download the latest version from the [Releases](https://github.com/opalgeorgii/CS2ConfigCopier/releases)
1. Configure your Steam and CS2/CS:GO settings once.
2. Open `CS2ConfigCopier.exe`, then restart Steam.
3. Click **Load** and choose the primary Steam account from which your CS2/CS:GO settings will be copied.  
   Use [steamid.xyz](https://steamid.xyz/) if you need to look up your SteamID.
4. Click:
   - **Copy all Steam settings**
   - **Copy current CS2 settings** and/or **Copy current CS:GO settings**
5. Save the entire folder, including all subfolders and the `.exe` file.

### Restoring your settings later

Use these steps after reinstalling Windows or Steam, using a different account, or playing from another PC or computer club.

0. Retrieve your saved configuration folder with `CS2ConfigCopier.exe`.
1. Open `CS2ConfigCopier.exe` and close Steam completely.
2. Click:
   - **Paste all Steam settings**
   - **Paste cs2_cfg** and/or **Paste csgo_cfg**
3. Launch CS2.
4. Open CS2 **Steam Properties** and enable **Keep game's saves in the Steam Cloud for Counter-Strike 2**.

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
