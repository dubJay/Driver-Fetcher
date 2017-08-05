from __future__ import print_function
import httplib2
import io
import os

from apiclient import discovery
from apiclient import errors
from apiclient.http import MediaIoBaseDownload
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

try:
    import argparse
    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None

# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/rom-fetcher.json
SCOPES = 'https://www.googleapis.com/auth/drive'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'Drive ROM Fetcher'

# Hardcoded Drive-to-Pi folders/files.
FOLDERS = {
    "Atari2600": "atari2600",
    "Atari7800": "atari7800",
    "AtariLynx": "atarilynx",
    "GameBoy": "gb",
    "GameBoyAdvanced": "gba",
    "GameBoyColor": "gbc",
    "GameGear": "gamegear",
    "Huge Game Collection": None,
    "MasterSystem": "mastersystem",
    "N64": "n64",
    "NEOGEO": "neogeo",
    "NEOGEOPocket": "ngp",
    "NEOGEOPocketColor": "ngpc",
    "NES": "nes",
    "Pictures": "../splashscreens",
    "SG100": "sg100",
    "SNES": "snes",
    "ZXSpectrum": "zxspectrum",
}

def _GetCredentials(home_dir):
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Args:
        home_dir: home directory path.
    Returns:
        Credentials, the obtained credential.
    """
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir,
                                   'rom-fetcher.json')

    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else: # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
        print('Storing credentials to ' + credential_path)
    return credentials


def _DeleteGame(rom_dir, filename):
    file_path = os.path.join(rom_dir, filename)
    if os.path.exists(file_path) and not os.path.isdir(file_path):
        os.remove(file_path)
        print('{0} successfully deleted'.format(file_path))

def _PathExists(path):
    return os.path.exists(path) and os.path.isdir(path)

def _BuildService(home_dir):
    credentials = _GetCredentials(home_dir)
    http = credentials.authorize(httplib2.Http())
    return discovery.build('drive', 'v3', http=http)
    

class FetchService():
    def __init__(self):
        self.home_dir = os.path.expanduser('~')
        self.roms = dict()
        self.roms_dir = os.path.join(self.home_dir, 'RetroPie/roms')
        self.service = _BuildService(self.home_dir)
        self.drive_folders = self._GetDriveFolders()
        print("Fetch Service initialized.")

    def _GetDriveFolders(self):
        return self.service.files().list(
            pageSize=100,
            q="mimeType = 'application/vnd.google-apps.folder' and starred = true"
        ).execute().get('files', [])

    def _GetFileByDir(self, dir_id):
        results = self.service.files().list(
            pageSize=100,
            q="'{0}' in parents".format(dir_id)
        ).execute()

        for item in results.get('files', []):
            self.roms[item['name']] = item['id']

    def _DownloadGames(self, local_game_folder):
        for filename, file_id in self.roms.iteritems():
            request = self.service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                print("Downloaded {0}%".format(int(status.progress() * 100)))

            # Write byte stream to file.
            with open(os.path.join(local_game_folder, filename), 'w+') as out:
                out.write(fh.getvalue())
                print('Successfully downloaded {0} to {1}'.format(filename, local_game_folder))

        # Empty dict after downloading all remaining items.
        self.roms.clear()


    def PerformSync(self):
        for item in self.drive_folders:
            if item['name'] in FOLDERS:
                local_game_folder = os.path.join(self.roms_dir, FOLDERS[item['name']])
                if _PathExists(local_game_folder):
                    self._GetFileByDir(item['id'])
                    for filename in os.listdir(local_game_folder):
                        if filename not in self.roms:
                            print('Deleting {0} from {1}'.format(filename, local_game_folder))
                            _DeleteGame(local_game_folder, filename)
                        self.roms.pop(filename, None)

                    self._DownloadGames(local_game_folder)

def main():
    fs = FetchService()
    fs.PerformSync()

    print('Sync Complete -- Starting Emulation Station')


if __name__ == '__main__':
    main()
