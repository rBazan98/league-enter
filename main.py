__version__ = '1.1.0'
import os
import time
import base64

import psutil
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import keyboard
import pygetwindow as gw
import win32gui
import win32con
import logging


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)
logging.getLogger("urllib3").setLevel(logging.INFO)  


paused = False
def toggle_pause():
    global paused
    paused = not paused
    log.info(f'Paused:{paused}')
keyboard.add_hotkey('ctrl+p',toggle_pause)

def handle_window(window_name="League of Legends"):
    windows = gw.getWindowsWithTitle(window_name)
    if windows:
        hwnd = windows[0]._hWnd
        return hwnd
    else:
        log.error(f'{window_name} window not found.')
        return None    

def find_lockfile(process_name='LeagueClientUx.exe'):
    for proc in psutil.process_iter(['name', 'exe']):
        if proc.info['name'] == process_name:
            base_path = os.path.dirname(proc.info['exe'])
            lockfile_path = os.path.join(base_path, 'lockfile')
            if os.path.exists(lockfile_path):
                log.info(f'Lockfile found: {lockfile_path}')
                return lockfile_path

    log.debug('Lockfile not found')
    return None

def minimize(window_handle):
    if window_handle:
        while not win32gui.IsIconic(window_handle):  # si NO está minimizada
            win32gui.ShowWindow(window_handle, win32con.SW_MINIMIZE)
    else:
        raise Exception('No window found.')

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
            phase = response.json()
            log.debug(f"Current phase: {phase}")
            return phase
    except requests.RequestException:
        log.warning(f"Request to get game phase failed: {e}")
    return None

#Main feature: automatically accept match
def accept_match(port, password, window_handle):
    url = f'https://127.0.0.1:{port}/lol-matchmaking/v1/ready-check/accept'
    auth = base64.b64encode(f'riot:{password}'.encode()).decode()
    headers = {
        'Authorization': f'Basic {auth}',
        'Accept': 'application/json'
    }
    try:
        log.info('Acepted!')
        response = requests.post(url, headers=headers, verify=False)
        # response = requests.post(url, headers=headers, verify=True)
        log.debug('POST: /lol-matchmaking/v1/ready-check/accept')
        log.info(f'Status: {response.status_code}, Content: {response.text}')
        time.sleep(0.2)
        minimize(window_handle)
        if response.status_code == 204:
            # time.sleep(0.2)
            return True
    except requests.RequestException as e:
        log.error(f'Error sending accept request: {e}')

#Future features:
#Pick and ban desire champs.
def pick_champ(champ):
    pass
def ban_champ(champ):
    pass

#Save/load runes for each champ. 
def save_runes(champ):
    pass
def load_runes(champ):
    pass

def run(init_delay=0):

    time.sleep(init_delay)
    lockfile_path = find_lockfile()
    if not lockfile_path:
        raise FileNotFoundError('Lockfile not found.')

    client_window_handle = handle_window()

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
        log.info(f'Current phase: {phase}')

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
                log.debug('Client not responding!')

        previous_phase = phase
        time.sleep(delay)


if __name__ == '__main__':
    custom_delay = 0
    DEFAULT_DELAY = 0
    while True:
        try:
            delay = custom_delay if custom_delay else DEFAULT_DELAY
            custom_delay = 0

            if not paused:
                run(delay)

        except FileNotFoundError:
            log.info('Waiting for League Client...')
            custom_delay = 10 # Sets a 10 seconds delay in the next run() excecutation
        except KeyboardInterrupt:
            log.info('Bye!')
            break
        except Exception as e:
            log.error(f'Unexpected Error: {e}')
            break

#Phases: Lobby > Matchmaking > ReadyCheck > ChampSelect > InProgress > PreEndOfGame