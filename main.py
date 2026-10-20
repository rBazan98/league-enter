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
    url = f'https://api.github.com/repos/{REPO}/releases/latest'
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            latest = response.json()['tag_name']
            # return latest != f'v{__version__}'
            log.debug(f'New version {latest} available.')
            return latest
    except requests.exceptions.Timeout:
        log.error('Request timed out. Check your internet connection.')
        return None

    except requests.exceptions.ConnectionError:
        log.error('No internet connection or DNS failure.')
        return None

    except Exception as e:
        log.error(f'Unexpected error: {e}')
        return None

def get_real_exe_path():
    """
    Returns the path from where the program is running.
    """
    return os.path.abspath(sys.executable)

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

    try:
        subprocess.Popen([
            updater_path, '--update', str(os.getpid()),
            exe_real_path, download_url
        ])
    except OSError as exc:
        log.error('Failed to launch updater: %s', exc)
        return

    sys.exit()


def run_updater(args):
    """
    Handles the update process by waiting for the main application to exit,
    downloading the new executable from the specified URL, replacing the old executable,
    launching the updated application, and finally cleaning up the updater executable before exiting.
    """

    import psutil as updater_psutil

    log.info('Updating...')
    if len(args) != 3:
        print('Usage: --update <PID> <target_exe_path> <download_url>')
        return 1

    try:
        target_pid = int(args[0])
        if target_pid <= 0:
            raise ValueError('PID must be positive')
    except ValueError:
        log.error('Invalid process ID for update.')
        return 1
    target_exe = args[1]
    download_url = args[2]

    print('Waiting for main process to exit...')
    try:
        updater_psutil.Process(target_pid).wait(timeout=30)
    except updater_psutil.NoSuchProcess:
        pass
    except (updater_psutil.AccessDenied, updater_psutil.TimeoutExpired) as exc:
        log.error('Unable to wait for main process: %s', exc)
        return 1

    tmp_path = target_exe + '.new'
    try:
        print(f'Downloading new version from {download_url}')
        with urllib.request.urlopen(download_url, timeout=30) as response, open(tmp_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        os.replace(tmp_path, target_exe)
    except Exception as e:
        log.error('Failed to download or replace executable: %s', e)
        return 1
    finally:
        try:
            os.remove(tmp_path)
        except FileNotFoundError:
            pass
        except OSError as exc:
            log.warning('Unable to remove temporary download: %s', exc)

    print('Launching updated exe...')
    try:
        subprocess.Popen([target_exe])
    except OSError as exc:
        log.error('Failed to launch updated executable: %s', exc)
        return 1
    time.sleep(1)

    updater_exe = sys.executable
    print('Cleaning up updater...')
    try:
        subprocess.Popen(f'cmd /c ping 127.0.0.1 -n 2 > nul & del /f /q "{updater_exe}"', shell=True)
    except OSError as exc:
        log.warning('Unable to schedule updater cleanup: %s', exc)
    return 0

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
            exe_path = proc.info['exe']
            if not exe_path:
                log.debug('Unable to read League Client executable path.')
                continue
            base_path = os.path.dirname(exe_path)
            lockfile_path = os.path.join(base_path, 'lockfile')
            if os.path.exists(lockfile_path):
                log.debug(f'Lockfile found: {lockfile_path}')
                return lockfile_path

    log.debug('Lockfile not found')
    return None

def minimize(window_title):
    try:
        window = gw.getWindowsWithTitle(window_title)[0]
        if not window.isMinimized:
            window.minimize()
            log.info('Minimize!')
        else:
            log.info('Window already minimized.')
    except IndexError:
        log.debug('No window found.')


def old_minimize(window_handle):
    if window_handle:
        while not win32gui.IsIconic(window_handle):
            win32gui.ShowWindow(window_handle, win32con.SW_FORCEMINIMIZE)
            log.info('Minimize!')
            win32gui.PumpWaitingMessages()
            log.info('PostPump!')

    else:
        log.debug('No window found.')

def read_lockfile(lockfile_path):
    try:
        with open(lockfile_path, 'r') as f:
            content = f.read().strip().split(':')
    except (OSError, UnicodeError) as exc:
        raise ConnectionError('Unable to read League Client lockfile.') from exc

    if len(content) != 5:
        raise ConnectionError('League Client lockfile is incomplete.')
    port, password = content[2:4]
    if (not port.isascii() or not port.isdigit() or len(port) > 5
            or not 1 <= int(port) <= 65535 or not password):
        raise ConnectionError('League Client lockfile is invalid.')
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
        response = requests.post(url, headers=headers, verify=False, timeout=2)
        log.debug('POST: /lol-matchmaking/v1/ready-check/accept')
        log.info(f'Status: {response.status_code}, Content: {response.text}')
        if response.status_code != 204:
            log.warning('Match acceptance failed (HTTP %s).', response.status_code)
            return False
        log.info('Accepted!')
        time.sleep(0.2)
        minimize('League of Legends')
        # old_minimize(window_handle)
        time.sleep(0.2)
        return True
    except requests.RequestException as e:
        log.error(f'Error sending accept request: {e}')
    return False

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
            minimize('League of Legends')
            # minimize(client_window_handle)
            time.sleep(3)
            minimize('League of Legends')
            # minimize(client_window_handle)

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


def run_bot():
    custom_delay = 0
    DEFAULT_DELAY = 0
    while True:
        try:
            if paused:
                time.sleep(0.1)
                continue
            delay = custom_delay if custom_delay else DEFAULT_DELAY
            custom_delay = 0
            run(delay)
        except FileNotFoundError:
            log.info('Waiting for League Client...')
            custom_delay = 10
        except ConnectionError:
            log.debug('League Client not responding...')
            custom_delay = 1
        except KeyboardInterrupt:
            log.info('Bye!')
            break
        except Exception as e:
            log.error(f'Unexpected Error: {e}')
            break


def main(args=None):
    global Version, psutil, requests, keyboard, gw, win32gui, win32con, urllib3

    args = sys.argv[1:] if args is None else args
    try:
        log.info(f'Welcome to League Enter v{__version__}')

        frozen = getattr(sys, 'frozen', False)
        if args and args[0] == '--update':
            if not frozen:
                log.error('The updater must run from the packaged executable.')
                return 1
            return run_updater(args[1:])

        Version, psutil, requests, keyboard, gw, win32gui, win32con, urllib3 = run_imports()
        latest_version = get_latest_version()
        if latest_version:
            log.debug(f'Latest release: {latest_version}')
            new_version = Version(latest_version.lstrip('v')) > Version(__version__)
            if new_version and frozen:
                offer_update(latest_version)
        else:
            log.info('Unable to get latest version')

        keyboard.add_hotkey('ctrl+p',toggle_pause)

        run_bot()
        return 0

    except KeyboardInterrupt:
        print()
        log.info('Bye!')
        return 0
    except Exception as e:
        print()
        log.error(f'Unexpected Error: {e}')
        return 1


if __name__ == '__main__':
    sys.exit(main())

#Phases: None > Lobby > Matchmaking > ReadyCheck > ChampSelect > InProgress > PreEndOfGame
