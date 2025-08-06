import os
import sys
import time
import base64
import subprocess
import urllib.request
import shutil
import logging

__version__ = '1.2.0'

logging.basicConfig(
    level=logging.INFO, #Set .DEBUG for debugging
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S')
log = logging.getLogger(__name__)
logging.getLogger('urllib3').setLevel(logging.INFO)

REPO = 'rBazan98/league-enter'
EXE_NAME = 'league-enter.exe'

def run_imports():
    from packaging.version import Version
    import psutil
    import requests
    import urllib3
    import keyboard
    import pygetwindow as gw
    import win32gui
    import win32con

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    return Version, psutil, requests, keyboard, gw, win32gui, win32con, urllib3

def get_latest_version():
    """
    Returns the latest version from the repository releases.
    """
    import requests
    url = f'https://api.github.com/repos/{REPO}/releases/latest'
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            latest = response.json()['tag_name']
            # return latest != f'v{__version__}'
            log.debug(f'New version {latest} available.')
            return latest
    except Exception:
        pass
    return False

def get_real_exe_path():
    """
    Returns the path from where the program is running.
    """
    exe_path = sys.executable
    if getattr(sys, 'frozen', False) and '_MEI' in exe_path:
        real_path = os.path.abspath(os.path.join(os.path.dirname(exe_path), '..', EXE_NAME))
        logging.warning(f'Probably running from a temporary directory: {exe_path}')
        return real_path
    return exe_path

def offer_update(latest=None):
    """
    Prompts the user to update to the latest version.
    If the user agrees, copies the current executable to a helper updater executable
    and launches it with parameters to perform the update, then exits the current process.
    """
    choice = input(f'New version {latest} available. Update now? [y/N]: ').lower()
    if choice != 'y':
        return

    exe_real_path = str(get_real_exe_path())
    download_url = f'https://github.com/{REPO}/releases/latest/download/{EXE_NAME}'

    updater_path = os.path.join(os.path.dirname(exe_real_path), 'league-updater.exe')
    try:
        shutil.copy2(exe_real_path, updater_path)
    except Exception as e:
        logging.error(f'Failed to copy updater exe: {e}')
        return

    subprocess.Popen([
        'cmd', '/c', 'start', '', updater_path,
        '--update',
        str(os.getpid()),
        exe_real_path,
        download_url
    ], shell=True)

    sys.exit()


def run_updater(args):
    """
    Handles the update process by waiting for the main application to exit,
    downloading the new executable from the specified URL, replacing the old executable,
    launching the updated application, and finally cleaning up the updater executable before exiting.
    """

    log.info('Updating...')
    if len(args) != 3:
        print('Usage: --update <PID> <target_exe_path> <download_url>')
        time.sleep(3)
        return

    target_pid = int(args[0])
    target_exe = args[1]
    download_url = args[2]

    print('Waiting for main process to exit...')
    while True:
        try:
            os.kill(target_pid, 0)
            time.sleep(0.5)
        except OSError:
            break

    tmp_path = target_exe + '.new'
    try:
        print(f'Downloading new version from {download_url}')
        with urllib.request.urlopen(download_url) as response, open(tmp_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
    except Exception as e:
        print(f'Download failed: {e}')
        time.sleep(3)
        return

    try:
        os.remove(target_exe)
        os.rename(tmp_path, target_exe)
    except Exception as e:
        print(f'Failed to replace executable: {e}')
        time.sleep(3)
        return

    print('Launching updated exe...')
    subprocess.Popen([target_exe])
    time.sleep(1)

    updater_exe = sys.executable
    print('Cleaning up updater...')
    subprocess.Popen(f'cmd /c ping 127.0.0.1 -n 2 > nul & del /f /q "{updater_exe}"', shell=True)
    sys.exit()

paused = False
def toggle_pause():
    global paused
    paused = not paused
    log.info(f'Paused:{paused}')


def handle_window(window_name='League of Legends'):
    windows = gw.getWindowsWithTitle(window_name)
    if windows:
        hwnd = windows[0]._hWnd
        return hwnd
    else:
        log.debug(f'{window_name} window not found.')
        return None

def find_lockfile(process_name='LeagueClientUx.exe'):
    for proc in psutil.process_iter(['name', 'exe']):
        if proc.info['name'] == process_name:
            base_path = os.path.dirname(proc.info['exe'])
            lockfile_path = os.path.join(base_path, 'lockfile')
            if os.path.exists(lockfile_path):
                log.debug(f'Lockfile found: {lockfile_path}')
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
            log.debug(f'Current phase: {phase}')
            return phase
    except requests.RequestException:
        log.debug(f'Request to get game phase failed.')
        raise ConnectionError(f'Unable to connect to league client.')
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
        log.info('Accepted!')
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
        'Lobby': 4,
        'Matchmaking': 0.3,
        'InProgress': 60,
        'ChampSelect': 8,
        'PreEndOfGame': 12,
        'EndOfGame': 10,
        'None': 5
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
    try:
        log.info(f'Welcome to League Enter v{__version__}')

        on_python = get_real_exe_path().lower().endswith('python.exe')
        on_python = False
        do_update = len(sys.argv) >= 2 and sys.argv[1] == '--update'

        if do_update and not on_python:
            run_updater(sys.argv[2:])
        else:
            Version, psutil, requests, keyboard, gw, win32gui, win32con, urllib3 = run_imports()
            latest_version = get_latest_version()
            log.debug(f'Latest release: {latest_version}')
            new_version = Version(latest_version.lstrip('v')) > Version(__version__)
            if new_version and not on_python:
                offer_update(latest_version)

        keyboard.add_hotkey('ctrl+p',toggle_pause)

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
                custom_delay = 10 # Sets a 10 seconds delay in the next run()
            except ConnectionError:
                log.debug('League Client not responding...')
                custom_delay = 1 # Sets a 10 seconds delay in the next run()
            except KeyboardInterrupt:
                log.info('Bye!')
                break
            except Exception as e:
                log.error(f'Unexpected Error: {e}')
                break

    except KeyboardInterrupt:
        print()
        log.info('Bye!')
    except Exception as e:
        print()
        log.error(f'Unexpected Error: {e}')

#Phases: None > Lobby > Matchmaking > ReadyCheck > ChampSelect > InProgress > PreEndOfGame