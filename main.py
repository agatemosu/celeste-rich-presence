import os
import sys
import time
from pathlib import Path

import psutil
from bs4 import BeautifulSoup
from discoIPC import ipc

CHAPTERS = [
    {"pic": "intro", "name": "Prologue"},
    {"pic": "city", "name": "Chapter 1: Forsaken City"},
    {"pic": "oldsite", "name": "Chapter 2: Old Site"},
    {"pic": "resort", "name": "Chapter 3: Celestial Resort"},
    {"pic": "golden", "name": "Chapter 4: Golden Ridge"},
    {"pic": "temple", "name": "Chapter 5: Mirror Temple"},
    {"pic": "reflection", "name": "Chapter 6: Reflection"},
    {"pic": "summit", "name": "Chapter 7: The Summit"},
    {"pic": "intro", "name": "Epilogue"},
    {"pic": "core", "name": "Chapter 8: Core"},
    {"pic": "farewell", "name": "Farewell"},
]

SIDES = {
    "Normal": ("A-Side", "aside"),
    "BSide": ("B-Side", "bside"),
    "CSide": ("C-Side", "cside"),
}


def get_game_location(cmdline: str):
    if sys.platform == "win32":
        return os.path.dirname(cmdline[0])

    if sys.platform == "linux":
        return os.path.expanduser("~/.local/share/Celeste")

    raise Exception(f"Unsupported operating system: {sys.platform}")


def get_latest_save(game_location: Path):
    save_files = [
        f
        for f in game_location.iterdir()
        if f.is_file() and f.suffix == ".celeste" and f.stem != "settings"
    ]

    if not save_files:
        return None

    return max(save_files, key=lambda f: f.stat().st_mtime)


def main():
    start_time = int(time.time())
    activity = {'details': 'In menus',  # this is what gets modified and sent to Discord via discoIPC
                'timestamps': {'start': start_time},
                'assets': {'small_image': ' ', 'small_text': 'In menus', 'large_image': 'logo', 'large_text': 'Celeste'},
                'state': 'yeet'}
    client = ipc.DiscordIPC('1243103531615916052')

    while True:
        game_is_running = False

        for process in psutil.process_iter():
            if game_is_running:
                break

            with process.oneshot():
                p_name = process.name()

                if "Celeste" in p_name:
                    game_location = get_game_location(process.cmdline()[0])
                    start_time = int(process.create_time())
                    game_is_running = True

            time.sleep(0.001)

        if game_is_running:
            if not client.connected:
                # connects to Discord
                client.connect()

            current_save_file_path = get_latest_save(Path(game_location) / 'Saves')
            if not current_save_file_path:
                print("No save files found")
                return

            with current_save_file_path.open("r") as current_save_file:
                xml_soup = BeautifulSoup(current_save_file.read(), 'xml')

                try:
                    current_save_number = int(current_save_file_path.stem) + 1
                except ValueError:
                    current_save_number = None

            save_slot_name = xml_soup.find('Name').string
            current_area_id = int(xml_soup.find('LastArea').get('ID'))
            current_area_mode = xml_soup.find('LastArea').get('Mode')
            total_deaths = xml_soup.find('TotalDeaths').string
            total_berries = int(xml_soup.find('TotalStrawberries').string)

            current_session = xml_soup.find('CurrentSession')
            if current_session:
                in_area = current_session.get('InArea') == 'true'
            else:
                in_area = True

            for area in xml_soup.find_all('AreaStats'):
                if area.get('ID') == str(current_area_id):
                    current_area_info = area.find_all('AreaModeStats')[list(SIDES.keys()).index(current_area_mode)]
                    current_area_deaths = current_area_info.get('Deaths')

            if save_slot_name == 'Madeline':
                save_slot_text = ""
            else:
                save_slot_text = f": \"{save_slot_name}\""

            activity['details'] = CHAPTERS[current_area_id]["name"]
            activity['assets']['small_image'] = ' '
            activity['assets']['large_image'] = CHAPTERS[current_area_id]["pic"]
            activity['assets']['small_text'] = f"{CHAPTERS[current_area_id]["name"]} ({SIDES[current_area_mode][0]})"
            activity['timestamps']['start'] = start_time

            if not current_save_number and current_save_file_path.name == "debug.celeste":
                activity['state'] = "In debug mode"
                activity['assets']['large_text'] = CHAPTERS[current_area_id]["name"]
            else:
                activity['assets']['large_text'] = f"Totals: {total_deaths} deaths, {total_berries} strawberries (save slot #{current_save_number}{save_slot_text})"

                if time.time() - start_time < 15:
                    activity['state'] = "Loading game"
                elif in_area:
                    activity['state'] = f"{SIDES[current_area_mode][0]} ({current_area_deaths} deaths)"
                else:
                    activity['state'] = "In level select"

            print(activity['details'])
            print(activity['state'])
            print(activity['assets']['large_text'])
            time_elapsed = time.time() - start_time
            print("{:02}:{:02} elapsed".format(int(time_elapsed / 60), round(time_elapsed % 60)))
            print()

            if not os.path.exists('history.txt'):
                open('history.txt', 'w').close()

            activity_str = f'{activity}\n'
            with open('history.txt', 'r') as history_file_r:
                history = history_file_r.readlines()
            if activity_str not in history:
                with open('history.txt', 'a') as history_file_a:
                    history_file_a.write(activity_str)

            # send everything to discord
            client.update_activity(activity)
        else:
            if client.connected:
                client.disconnect()
                print("Exiting...")
                return
            else:
                print("Celeste isn't running\n")

        # rich presence only updates every 15 seconds, but it listens constantly so sending every 5 seconds is fine
        time.sleep(10)


if __name__ == '__main__':
    main()
