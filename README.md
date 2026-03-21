# AutoConfigCopier

Automatically copies your CS2 (Counter-Strike 2 / **CS:GO under maintenance**) configuration files to the correct game and user folders.

---

## Features

- Copies game `.cfg` files (autoexec, custom configs) to the CS2 game `cfg` folder.
- Copies user-specific `.vcfg` files and `cs2_video.txt` to all Steam users’ local cfg folders.
- Automatically detects Steam installation and all library folders.
- Works for both Python scripts and compiled `.exe` files.
- Shows a Windows popup when copying is complete.

---

## How It Works

- **Python script**: The program detects its folder and looks for a `cfg` folder in the project root.
- **Compiled `.exe`**: The program detects the `.exe` location (usually in `dist/`) and automatically searches for a `cfg` folder relative to the project root.
- This ensures the source `cfg` folder is correctly found whether running the script directly or as an `.exe`.

---

## How to Use

1. Place all your configuration files in a `cfg` folder in the same directory as your project root.

   Example files:
   - `autoexec.cfg`
   - `cs2_1v1.cfg`
   - `cs2_fun.cfg`
   - `cs2_nades.cfg`
   - `cs2_user_convars_0_slot0.vcfg`
   - `cs2_user_keys_0_slot0.vcfg`
   - `cs2_video.txt`
   - `cs2_machine_convars.vcfg`

2. Run the program:
   - **Python**: `python auto_config_copier.py`
   - **Compiled `.exe`**: Double-click the `.exe` file

3. The program will:
   - Copy `.cfg` files to the CS2 game `cfg` folder.
   - Copy `.vcfg` and `cs2_video.txt` files to all Steam users’ local cfg folders.
   - Show a Windows popup confirming that all files have been copied.

4. Check the console output (if running as a script) to see which files were copied and to which folders.

---

## Requirements

- Windows OS
- Steam installed with CS2/CS:GO
- If using `.exe`: No Python installation needed.

---

## Notes

- Works with multiple Steam accounts on the same PC.
- Make sure your configuration files are named exactly as listed above; otherwise, they won’t be copied.
- If the program cannot find Steam, the game folder, or the `cfg` folder, it will show an error popup.
- `.exe` users must keep the `cfg` folder in the correct relative location (**don't move/create any folders**).