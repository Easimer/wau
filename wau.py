#!/usr/bin/python3

# wau
# Copyright (C) 2020 easimer <easimer@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import typing
import sys
import getopt
import json
import shutil
import os.path
import zipfile
import logging
from threading import Thread, Lock
import requests
import dateutil.parser

TWITCH_APP_API_URL="https://addons-ecs.forgesvc.net/api/v2"

ARG_API_URL     = '-a'
ARG_FORCE       = '-f'
ARG_FLAVOR      = '-g'
ARG_PAUSE       = '-p'

class WAU_Manifest:
    def __init__(self, base_path):
        self.addons = {}
        self.manifest_path = base_path + "/wau_manifest.txt"
        try:
            with open(self.manifest_path) as f:
                self.version = f.readline().rstrip()
                for line in f:
                    cols = line.split()
                    id = int(cols[0])
                    install_alpha = int(cols[1]) != 0
                    version = cols[2]
                    self.addons[id] = {
                        "install_alpha": install_alpha,
                        "version": version,
                    }
        except OSError:
            # No manifest file
            logging.info("No manifest file found, creating an empty one")
    
    def update_version(self, addon_id, version):
        """Updates the installed version number field for an addon."""
        self.addons[addon_id]['version'] = version
    
    def commit(self):
        """Writes the manifest to disk."""
        with open(self.manifest_path, "w") as f:
            f.write("{}\n".format(self.version))
            for key, data in self.addons.items():
                install_alpha = 1 if data['install_alpha'] else 0
                version = data['version']
                f.write("{} {} {}\n".format(key, install_alpha, version))

class TwitchAppAPI:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36'
        }
    
    def get_addon_info(self, id: int) -> dict:
        url = self.base_url + "/addon/{}".format(id)
        response = requests.get(url, headers = self.headers)

        if response.status_code != 200:
            self.throw_api_error(response)
        
        return json.loads(response.text)
    
    def get_addon_database_version(self) -> str:
        url = self.base_url + "/addon/timestamp"
        response = requests.get(url, headers = self.headers)
        if response.status_code != 200:
            self.throw_api_error(response)
        
        return json.loads(response.text)

    def throw_api_error(self, response):
        raise Exception("Status code was {} response='{}'".format(response.status_code, response.text))

def load_manifest(base_path: str) -> WAU_Manifest:
    """Loads a WAU manifest file and returns a WAU_Manifest instance.

    ``base_path`` -- Path to the directory containing the manifest file
    """
    manifest = WAU_Manifest(base_path)
    return manifest

def get_latest_file(api: TwitchAppAPI, addon_info: dict, install_alpha: bool, game_version_flavor: str):
    """Finds the latest release of an addon.

    ``api`` -- TwitchAppAPI instance

    ``addon_info`` -- dict returned by a call to TwitchAppAPI.get_addon_info

    ``install_alpha`` -- should alpha releases be considered

    ``game_version_flavor`` -- should be ``"wow_retail"`` on retail clients, ``"wow_classic"`` on classic clients
    """
    latest_files = addon_info['latestFiles']
    latest_date = None
    latest_file = None
    for file in latest_files:
        if file['gameVersionFlavor'] != game_version_flavor:
            continue

        # Skip alpha releases
        release_type = int(file['releaseType'])
        if not install_alpha and release_type != 1:
            continue

        # Find max by date
        file_date = dateutil.parser.isoparse(file['fileDate'])
        if latest_date is None or file_date > latest_date:
            latest_date = file_date
            latest_file = file
    
    return latest_file

def get_version(release: dict) -> str:
    return release['displayName'].replace(' ', '_')

def erase_local(addons_path: str, release: dict):
    """Erases all directories related to the given addon."""

    for module in release['modules']:
        dir_name = module['foldername']
        path_to_module = os.path.join(addons_path, dir_name)
        logging.debug("Erasing {}".format(path_to_module))
        try:
            shutil.rmtree(path_to_module)
        except:
            pass

def download_release(addons_path: str, release: dict):
    """Downloads a given release and puts it into the AddOns directory."""
    try:
        file_name = release['fileName']
        target_path = os.path.join(addons_path, file_name)
        download_url = release['downloadUrl']

        with requests.get(download_url, stream = True) as R:
            with open(target_path, "wb") as F:
                shutil.copyfileobj(R.raw, F)
        return target_path
    except Exception as ex:
        logging.error("Download failed: {}".format(ex))
        return None

def extract_release(addons_path: str, zip_path: str):
    """Extracts a zip file straight into the addons directory."""
    logging.debug("Extracting {}".format(zip_path))
    with zipfile.ZipFile(zip_path, "r") as Z:
        Z.extractall(addons_path)

def delete_release_cache(zip_path: str):
    """Removes the downloaded addon zip file."""
    try:
        os.remove(zip_path)
        logging.debug("Removed cache file {}".format(zip_path))
    except Exception as ex:
        logging.error("Couldn't remove cache file '{}': {}".format(zip_path, ex))

def process_addon(manifest: WAU_Manifest, manifest_lock: Lock, api: TwitchAppAPI, addons_path: str, addon_id: int, game_flavor: str):
    logging.debug("Processing addon #{}".format(addon_id))
    installed_version = manifest.addons[addon_id]['version']
    install_alpha = manifest.addons[addon_id]['install_alpha']
    addon_info = api.get_addon_info(addon_id)
    latest_file = get_latest_file(api, addon_info, install_alpha, game_flavor)
    latest_version = get_version(latest_file)
    name = addon_info['name']
    if latest_version != installed_version:
        logging.info("Addon '{}' is out-of-date '{}' != '{}'".format(name, installed_version, latest_version))
        zip_path = download_release(addons_path, latest_file)
        if zip_path != None:
            erase_local(addons_path, latest_file)
            extract_release(addons_path, zip_path)
            delete_release_cache(zip_path)
            logging.info("Addon '{}' has been updated!".format(name))
            with manifest_lock:
                manifest.update_version(addon_id, latest_version)
                manifest.commit()
    else:
        logging.info("Addon '{}' is up to date!".format(name))

def print_usage(exit_code = None):
    """Prints the usage text and optionally exits with the supplied code."""
    usage_dict = {
        ARG_FLAVOR: "sets the game flavor; can be either 'wow_retail' (default) or 'wow_classic'",
        ARG_FORCE: "check addon versions regardless of manifest timestamp",
        ARG_PAUSE: "pause execution after all tasks are finished",
        ARG_API_URL: "[dev] sets the base URI to the Twitch App API",
    }

    print("Usage: {} [-fp] [-a URL] [-g game_flavor] path_to_AddOns_directory".format(sys.argv[0]))
    for k, v in usage_dict.items():
        print("\t{}\t{}".format(k, v))
    
    if exit_code != None:
        exit(exit_code)

# GPL notice
print("""wau  Copyright (C) 2021  easimer <easimer@gmail.com>
This program comes with ABSOLUTELY NO WARRANTY.
This is free software, and you are welcome to redistribute it under certain
conditions.
""")

logging.basicConfig(level=logging.INFO)

# Parse arguments
optlist = None
args = None

try:
    optlist, args = getopt.getopt(sys.argv[1:], 'a:fg:p')
    optlist = dict(optlist)
except getopt.GetoptError as ex:
    print("Invalid argument: {}".format(ex.msg))
    print_usage(1)

# Process arguments
api_url = TWITCH_APP_API_URL
forced_update = False
game_flavor = "wow_retail"
pause_after_finish = False

if len(args) < 1:
    logging.error("Please specify path to WoW AddOns directory")
    print_usage(1)

addons_path = args[0]

if ARG_API_URL in optlist:
    api_url = optlist[ARG_API_URL]

if ARG_FORCE in optlist:
    forced_update = True

if ARG_FLAVOR in optlist:
    game_flavor = optlist[ARG_FLAVOR]

if ARG_PAUSE in optlist:
    pause_after_finish = True

logging.info("API URL: {}".format(api_url))
logging.info("Addons path: {}".format(addons_path))

# Load manifest, query remote database timestamp

manifest = load_manifest(addons_path)
manifest_lock = Lock()
api = TwitchAppAPI(api_url)

api_db_version = api.get_addon_database_version()

# Compare manifest timestamp vs remote database timestamp
if api_db_version == manifest.version and not forced_update:
    logging.info("Not updating addons; manifest is up to date. Pass {} in arguments to force update.".format(ARG_FORCE))
    exit(0)

# Update manifest timestamp
manifest.version = api_db_version

# Create and start a new thread for each addon
threads = []
for addon_id in manifest.addons:
    args = (manifest, manifest_lock, api, addons_path, addon_id, game_flavor,)
    thread = Thread(target = process_addon, args = args)
    threads.append(thread)
    thread.start()

for thread in threads: thread.join()

if pause_after_finish:
    input("Press Enter to continue...")