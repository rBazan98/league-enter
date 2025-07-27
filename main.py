import os
import time
import base64

import psutil
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import keyboard
import pygetwindow as gw
# import pyautogui
import win32gui
import win32con

paused = False

def toggle_pause():
    global paused
    paused = not paused
    print('Paused:',paused)

keyboard.add_hotkey('p',toggle_pause)

def handle_window(window_name="League of Legends"):
    windows = gw.getWindowsWithTitle(window_name)
    if windows:
        hwnd = windows[0]._hWnd
        return hwnd
    raise ValueError(f"{window_name} window not found.")

def find_lockfile(process_name='LeagueClientUx.exe'):
    for proc in psutil.process_iter(['name', 'exe']):
        if proc.info['name'] == process_name:
            base_path = os.path.dirname(proc.info['exe'])
            lockfile_path = os.path.join(base_path, 'lockfile')
            if os.path.exists(lockfile_path):
                return lockfile_path

    raise FileNotFoundError("League of Legends client lockfile not found.")

def minimize(window_handle):
    win32gui.ShowWindow(window_handle, win32con.SW_MINIMIZE)

def read_lockfile(lockfile_path):
    with open(lockfile_path, 'r') as f:
        content = f.read().split(':')
        port = content[2]
        password = content[3]
    return port, password

def get_game_phase(port, password):
    url = f'https://127.0.0.1:{port}/lol-gameflow/v1/gameflow-phase'
    auth = base64.b64encode(f'riot:{password}'.encode()).decode()
    headers = {
        'Authorization': f'Basic {auth}',
        'Accept': 'application/json'
    }
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=2)
        if response.status_code == 200:
            return response.json()
    except requests.RequestException:
        pass
    return None


def accept_match(port, password, window_handle):
    url = f'https://127.0.0.1:{port}/lol-matchmaking/v1/ready-check/accept'
    auth = base64.b64encode(f'riot:{password}'.encode()).decode()
    headers = {
        'Authorization': f'Basic {auth}',
        'Accept': 'application/json'
    }
    try:
        print('Acepted')
        response = requests.post(url, headers=headers, verify=False)
        # response = requests.post(url, headers=headers, verify=True)
        print('POST: /lol-matchmaking/v1/ready-check/accept')
        print(f'Status: {response.status_code}, Content: {response.text}')
        time.sleep(0.2)
        minimize(window_handle)
        if response.status_code == 204:
            # time.sleep(0.2)
            return True
    except requests.RequestException as e:
        print('Error sending accept request:', e)

def run():

    try:
        lockfile_path = find_lockfile()
        client_window_handle = handle_window()
    except FileNotFoundError:
        return

    port, password = read_lockfile(lockfile_path)

    DELAY_UNKNOWN = 1
    PHASE_DELAYS = {
        'Lobby': 3,
        'Matchmaking': 0.3,
        'InProgress': 60,
        'ChampSelect': 10,
        'PreEndOfGame': 10,
        'EndOfGame': 10,
    }
    
    previous_phase = None
    while not paused:
        phase = get_game_phase(port, password)
        print('Current phase:', phase)

        if previous_phase == 'ReadyCheck' and phase == 'ChampSelect':
            minimize(client_window_handle)
            time.sleep(3)
            minimize(client_window_handle)

        if phase == 'ReadyCheck':
            delay = 0.5
            if accept_match(port, password,client_window_handle):
                time.sleep(5)

        else:
            delay = PHASE_DELAYS.get(phase, DELAY_UNKNOWN)
            if phase not in PHASE_DELAYS:
                print("Client not responding!")

        previous_phase = phase
        time.sleep(delay)


if __name__ == '__main__':
    while True:
        try:
            if not paused: run()
        except FileNotFoundError:
            print("Waiting for League Client...")
            time.sleep(10)  
        except KeyboardInterrupt:
            print("\nBye!")
            time.sleep(3)
            break
        
        except Exception as e:
            print(f"Unexpected Error: {e}")
            time.sleep(2)


#Phases: Lobby > Matchmaking > ReadyCheck > ChampSelect > InProgress > PreEndOfGame
