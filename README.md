# League Auto-Accept Bot📎

Automatically accepts League of Legends matches so you never miss a game because you were distracted. It also minimizes the game window so it doesn't get in your way. 🕹️✨

---

## Why use this bot? 🚀

- Auto-accept matches fast and reliably. ⚡
- Stop staring at the client waiting to accept. 👀
- Minimizes the game window to keep your desktop clean. 🖥️
- Adjusts check frequency based on game phase to save CPU. 🛠️💻
- Pause and resume easily with the `P` key. ⏸️▶️

###  Reminder ⚠️
Please use this tool responsibly. Make sure to be ready to make your ban and manually pick your champion on time to avoid inconveniencing other players and to prevent inactivity penalties.

---

## Requirements 📋

- Python 3.x 🐍
- Install dependencies with:

```bash
pip install -r requirements.txt
```
## How to Build the Executable (.exe)

If you want to create the standalone Windows executable of this app, follow these steps like a pro:

1. **Set up your environment (optional but recommended):**

   ```bash
   python -m venv venv
   source venv/Scripts/activate #for PowerShell
   # Or
   venv\Scripts\activate.bat #for CMD
   ```
2. **Install the dependencies:**
   ```bash
    pip install -r requirements.txt
    pip install pyinstaller
    ```
3. **Generate the executable:**
   ```bash
    pyinstaller --onefile --windowed main.py
    ```
4. **Find your executable in:**
   ```bash
    dist/main.exe
    ```

---
<p align="center">
  <sub>⚠️ <strong>Disclaimer</strong><br>
  This project is intended for educational and demonstrative purposes only. It is not meant to be used to gain unfair advantages or interact with any official game clients in production environments.<br>
  Use at your own risk. The author is not responsible for any consequences arising from misuse.<br>
  League of Legends and its related trademarks are property of Riot Games, Inc.</sub>
</p>

---