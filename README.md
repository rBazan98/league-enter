# League Auto-Accept Bot **v1.2.0**📎

Automatically accepts League of Legends matches so you never miss a game because you were distracted. It also minimizes the game window so it doesn't get in your way. 🕹️✨

---

## Why use this bot? 🚀

- Auto-accept matches fast and reliably. ⚡
- Stop staring at the client waiting to accept. 👀
- Minimizes the game window to keep your desktop clean. 🖥️
- Adjusts check frequency based on game phase to save CPU. 🛠️💻
- Pause and resume easily with  `CTRL + P` hot-key. ⏸️▶️
- Executable auto-updates itself to keep you always current. 🔄

###  Reminder ⚠️
Please use this tool responsibly. Make sure to be ready to make your ban and manually pick your champion on time to avoid inconveniencing other players and to prevent inactivity penalties.

---

## Requirements 📋

- Windows and Python 3.9 or newer 🐍
- Run these PowerShell commands from the repository directory. Dependencies stay inside `.venv`; activating it is optional.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
- Run the main script:

```powershell
.\.venv\Scripts\python.exe main.py
```

To activate the environment in PowerShell, use `.\.venv\Scripts\Activate.ps1`.
For Command Prompt (CMD), use `.venv\Scripts\activate.bat`.

## Tests

After installing the dependencies, run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
```

The tests simulate client responses, process waiting, downloads, hotkeys, and executable launches. They do not start the bot, connect to League of Legends, or perform an actual update. Updater file operations use temporary test files.

## How to Build the Executable (.exe)

1. **Create `.venv` and install the dependencies** using the commands above.

2. **Install PyInstaller inside the same environment:**

   ```powershell
   .\.venv\Scripts\python.exe -m pip install pyinstaller
   ```

3. **Build directly with PyInstaller:**

   ```powershell
   .\.venv\Scripts\python.exe -m PyInstaller --clean --onefile --name league-enter main.py
   ```

4. **Find the executable at `dist\league-enter.exe`.** Building does not launch it.

The packaged executable prompts before downloading a newer release from this repository. Running `main.py` from Python does not offer executable updates.

---
<p align="center">
  <sub>⚠️ <strong>Disclaimer</strong><br>
  This project is intended for educational and demonstrative purposes only. It is not meant to be used to gain unfair advantages or interact with any official game clients in production environments.<br>
  Use at your own risk. The author is not responsible for any consequences arising from misuse.<br>
  League of Legends and its related trademarks are property of Riot Games, Inc.</sub>
</p>

---
