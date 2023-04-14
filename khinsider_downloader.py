# This script will mass download soundtracks of an album from downloads.khinsider.com
# Built-in dependencies
from os.path import isfile
from os import mkdir
from pathlib import Path
from typing import Tuple, Sequence
from urllib.parse import unquote

# External dependencies
from requests import get
from requests.exceptions import RequestException
from bs4 import BeautifulSoup
from tqdm import tqdm

# URL to album
BASE_URL = 'https://downloads.khinsider.com'
BASE_ALBUM_URL = f'{BASE_URL}/game-soundtracks/album'


def get_input(prompt: str, default: str = None) -> str:
    """
    Prompts the user for input with the given prompt message and returns the user's response.
    If the user enters nothing and a default value is provided, returns the default value.

    Args:
        prompt (str): The message to display to the user when prompting for input.
        default (str, optional): The default value to return if the user enters nothing. Default is None.

    Returns:
        str: The user's input, or the default value if provided and the user entered nothing.
    """
    return input(prompt) or default


def choose_format(format_selections: Sequence[str]) -> int:
    """
    Prompts the user to choose an audio format from a sequence of selections and returns the index of the selected
    format.

    Args:
        format_selections (Sequence[str]): A sequence of strings representing the available format options.

    Returns:
        int: The index of the selected format.
    """
    selections_range = range(0, len(format_selections))

    # Display prompt
    print('Choose a format:')
    for i in selections_range:
        print(f'{i} - {format_selections[i]}')

    selections_display = ' or '.join(map(lambda t: str(t), selections_range))
    # Get the valid input
    while True:
        try:
            selection = get_input('')

            # Handles when input is empty OR
            # contains more than 1 character OR
            # contains other character than number
            if (not selection) or (len(selection) > 1) or (not selection.isnumeric()):
                raise ValueError(f"Invalid input: Please enter number {selections_display} only.")

            selection = int(selection)
            # Checks if number is in range
            if selection not in list(selections_range):
                raise ValueError(f"Invalid range: Only {selections_display} available.")

            return selection
        except (ValueError, TypeError) as err:
            print(err)


def choose_download_dir(dir_default: str):
    """
    Prompts the user to specify a download location and creates the directory if it does not exist.

    Args:
        dir_default (str): The default download location to use if the user enters nothing.

    Returns:
        str: The user's input as a string, or the default value if provided when the user entered nothing.
    """
    while True:
        out = str(get_input(f'Download location (Press Enter to use default: {dir_default} ):\n', default=dir_default))

        try:
            mkdir(out)
            return out
        except FileExistsError:
            return out
        except PermissionError as err:
            print(err)
            print('Invalid location: Please provide a valid download location or use default.\n')


def format_bytes(bytes_list):
    """
    Format a list of file sizes in bytes as human-readable strings based on the largest file size.

    Args:
        bytes_list: A list of integers representing file sizes in bytes.

    Returns:
        A list of formatted sizes in human-readable units (B, KB, MB, GB).
    """
    max_bytes = max(bytes_list)
    unit_dict = {
        0: 'B',
        1: 'KB',
        2: 'MB',
        3: 'GB'
    }
    index = 0
    while max_bytes >= 1000:
        index += 1
        max_bytes /= 1000
    unit = unit_dict.get(index)
    return [f'{b / (1024 ** index):.1f} {unit}' for b in bytes_list]


class KhinsiderAlbum:
    def __init__(self, album_id):
        """
        Initializes a new instance of the `KhinsiderAlbum` class with the given album ID.

        Args:
            album_id (str): The ID of the album to be retrieved.

        Raises:
            ConnectionRefusedError: If the given album ID does not exist.
        """
        self.album_url = f'{BASE_ALBUM_URL}/{album_id}'

        # Make a request to the album page URL and parse the HTML with BeautifulSoup.
        html = get(self.album_url)

        album_page = BeautifulSoup(html.text, 'html.parser')

        # Get the album title.
        album_title = album_page.find('h2').text

        if album_title == 'Ooops!':
            raise ConnectionRefusedError(f"Invalid ID: Album ID '{album_id}' doesn't exist")

        # Get the soundtracks table
        soundtracks_table = album_page.find_all('table')[1]
        th_list = soundtracks_table.find_all('th')

        # Finds the index of the MP3 format in the th element
        mp3_index = next(i for i, th in enumerate(th_list) if th.text == 'MP3')
        album_formats = []

        # Finds all available audio format starting from MP3...
        for i in range(mp3_index, len(th_list)):
            # If content of current th element is not empty,
            # it means the content talks about the audio format available.
            # Otherwise, it means the talk about audio format(s) has ended,
            # thus stop looping other elements to enhance performance.
            if f := th_list[i].text.strip():
                album_formats.append(f)
            else:
                break

        # Extract the duration of the album and the spaces requirements for each format
        # This is obtained from th elements at the endmost of the soundtracks table
        album_duration, *sizes = tuple(map(lambda th: th.text, th_list[-(len(album_formats) + 2):-1]))

        # Parse the amount of size from its unit (MB) and convert it to bytes (1 MB = 1,000,000 B)
        # Example: "10 MB" (str) -> 10_000_000 (int)
        sizes = list(map(lambda s: int(s.split(' ')[0].replace(',', '')) * 1_000_000, sizes))
        sizes = format_bytes(sizes)

        album_formats_and_sizes = tuple(zip(album_formats, sizes))

        # Get the URLs to each soundtrack's source page
        urls = [td for i, td in enumerate(soundtracks_table.find_all_next('td', class_='clickable-row')) if i % 4 == 0]
        soundtrack_urls = list(map(lambda td: f"{BASE_URL}{td.next_element['href']}", urls))

        self.title = album_title
        self.duration = album_duration
        self.formats_and_sizes = album_formats_and_sizes
        self.soundtrack_urls = soundtrack_urls

    def __str__(self):
        """
        Return a formatted string representation of the KhinsiderAlbum object.

        Returns:
            str: A string composed of the album's title, duration, and available formats with their sizes.
        """
        f = '\n'.join([f'✓ {f} ({s})' for (f, s) in self.formats_and_sizes])
        return '\n'.join([f'ALBUM Title: {self.title}', f'Total Duration: {self.duration}', 'Available format:', f])

    def get_available_formats(self) -> Tuple[str, ...]:
        """
        Returns a tuple of available audio formats for the album.

        Returns:
            Tuple[str, ...]: A tuple of available audio formats.
        """
        return tuple(f for (f, _) in self.formats_and_sizes)

    @staticmethod
    def parse_id(url_to_album: str) -> str:
        """
        Parse the album ID from a given album URL. If album ID is provided instead of URL, the album ID is returned
        without parsing.

        Args:
            url_to_album (str): The URL to the album.

        Returns:
            str: The ID of the album.

        Examples:
            >>> url = 'https://downloads.khinsider.com/game-soundtracks/album/kingdom-hearts-original-soundtrack'
            >>> KhinsiderAlbum.parse_id(url)
            'kingdom-hearts-original-soundtrack'
        """
        if BASE_ALBUM_URL in url_to_album:
            return url_to_album.rsplit('/', 1)[1]
        return url_to_album

    @staticmethod
    def _scrape_download_url(soundtrack_url: str, audio_select: int = 0) -> str:
        """
        Scrape the download URL of an audio file from a soundtrack webpage.

        Parameters:
            soundtrack_url (str): The URL of the soundtrack webpage.
            audio_select (int, optional): The index of the audio file to download if there are multiple files available.
                Defaults to 0 (i.e., the first audio file in the list).

        Returns:
            str: The URL of the audio file to download.

        Raises:
            requests.exceptions.RequestException: If there is an error with the HTTP request.
            ValueError: If the audio_format_selection parameter is out of range.

        """
        # Open source page
        html = get(soundtrack_url)
        soundtrack_page = BeautifulSoup(html.text, 'html.parser')

        # Scrape the link to download resource
        download_url = soundtrack_page.find_all(class_='songDownloadLink')[audio_select].parent['href']

        # The website's url already formatted some characters to their corresponding code (%XX)
        # Unquote will reformat it from code back to its original character
        # Refer https://docs.python.org/3.10/library/urllib.parse.html#urllib.parse.unquote
        # The '#' special character is used in certain URLs (in the filename), replace for URL purpose
        download_url = unquote(download_url).replace('#', '%23')
        return download_url

    @staticmethod
    def _parse_filename(download_url: str) -> str:
        """
        Parse the filename from a given download URL.

        Args:
            download_url (str): The URL of the file to parse the filename from.

        Returns:
            str: The filename, extracted from the URL.

        Example:
            >>> url = 'https://example.com/soundtrack/%231 Track 1.mp3'
            >>> KhinsiderAlbum._parse_filename(url)
            '#1 Track 1.mp3'
        """
        return download_url.rsplit('/', 1)[1].replace('%23', '#')

    @staticmethod
    def _download_soundtrack(download_url, filepath):
        # Make a GET request to the URL, but don't download the entire response at once
        response = get(download_url, stream=True)

        total_size_in_bytes = int(response.headers.get('content-length', 0))
        block_size = 500_000  # 0.5 MB

        progress_bar = tqdm(total=total_size_in_bytes, unit='it', unit_scale=True, colour='green')

        # Open a file to write the downloaded data to
        with open(filepath, 'wb') as file:
            for data in response.iter_content(block_size):
                progress_bar.update(len(data))
                file.write(data)

        progress_bar.close()

    @staticmethod
    def _create_output_directory(directory):
        """
        Creates a new directory with the specified path.

        Args:
            directory (str): The path of the directory to create.

        Returns:
            None.
        """
        try:
            mkdir(directory)
            print(f'Directory {directory} created...')
        except FileExistsError:
            pass

    def download(self, out_dir: str, audio_format_selection: int) -> None:
        """
        Downloads the soundtrack files for the album to a specified directory.

        :param out_dir: The path to the directory where the soundtrack files will be saved.
        :type out_dir: str

        :param audio_format_selection: An integer representing the index of the desired audio format and quality
            from the available formats and sizes list for each soundtrack file. Default is 0 (the first format).
        :type audio_format_selection: int

        :return: None
        """
        self._create_output_directory(out_dir)
        download_count = 0
        skip_count = 0
        for url in self.soundtrack_urls:
            download_url = self._scrape_download_url(url, audio_format_selection)
            filename = self._parse_filename(download_url)
            filepath = f'{out_dir}/{filename}'

            # Checks if file already exists
            if isfile(filepath):
                print(f'Skipping {filename}, it already exists...')
                skip_count += 1
                continue

            print(f'Downloading {filename}...')

            self._download_soundtrack(download_url, filepath)

            download_count += 1
        print(f'Downloads finished! {download_count} files have been downloaded, {skip_count} files has been skipped.')

    def get_download_length(self):
        """
        Returns the number of soundtracks to be downloaded
        :return:
        """
        return len(self.soundtrack_urls)


# Interface
if __name__ == '__main__':
    welcome = '''
╔═══╗ ♪  Welcome to,
║███║ ♫  KHINSIDER DOWNLOADER.
║(●)║ ♫  Download your favorite video game soundtracks with ease!
╚═══╝♪♪  ▁▇▅▂▃▂▇▅▇▃▄▁▇█▅█▃▄▁▇█▅▄▁▅▃▄▁▄▃▄█▅▇▃▄▁▄▇█▂▃▁▅▄▅█▁▅█▃▄▃▇▂▁
    '''
    print(welcome)
    text_prompt = "▶ Please enter an album id OR a link to the album's page (from downloads.khinsider.com):\n"
    while True:
        # Prompt the user to enter the URL or ID of the album
        url_or_id = str(get_input(text_prompt, default=''))
        id_ = KhinsiderAlbum.parse_id(url_or_id)

        try:
            if not id_:
                raise ConnectionRefusedError(f"Invalid ID: Album ID can't be empty")

            # Get soundtrack information
            khin_album = KhinsiderAlbum(id_)
            print('')

            # Display album information
            print(khin_album)
            print('')

            # Choose an audio format if there are more than one format available
            f_selected = choose_format(khin_album.get_available_formats())
            print('')

            # Preset the output directory of audio file
            dir_out = choose_download_dir(f'{str(Path.home())}/Music/{khin_album.title}')

            # Inform the user that the download is being prepared
            print('\nPreparing download...')

            # Download the soundtrack
            khin_album.download(dir_out, f_selected)
            print('')

            while True:
                # Ask the user if they want to continue
                continue_ = get_input('▶ Do you want to continue? [Y/n]\n', default='y')

                match continue_.lower():
                    case 'y' | 'yes' | 'ok' | 'continue':
                        break
                    case 'n' | 'no' | 'nope' | 'exit':
                        # Exit the program if the user chooses not to continue
                        exit(0)
                    case _:
                        continue
        except (ConnectionRefusedError, RequestException) as an_err:
            # Handle exceptions related to network requests
            print(an_err)
        finally:
            print('')
