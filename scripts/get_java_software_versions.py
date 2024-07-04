import requests
from bs4 import BeautifulSoup
import re
import datetime

DEEPIMAGEJ_UPDATE_SITE_URL = "https://sites.imagej.net/DeepImageJ/plugins/"
DEEPIMAGEJ_PATTERN = r"DeepImageJ-(\d+\.\d+\.\d+)\.jar-(\d{14})"

def get_deepimagej_versions():
    response = requests.get(DEEPIMAGEJ_UPDATE_SITE_URL)
    soup = BeautifulSoup(response.content, 'html.parser')
    links = soup.find_all('a')
    files = []
    for link in links:
        href = link.get('href')
        if href.contains('.jar') and href.lower().contains('deepimagej'):
            files.append(href)


def get_dij_version_and_date(filename: str):
    match = re.search(DEEPIMAGEJ_PATTERN, filename)

    version_dic = {}
    if match:
        version = match.group(1)
        date = match.group(2)
        version_dic["vv"] = version
        version_dic["ts"] = datetime.datetime(int(date[:4]), int(date[4:6]), int(date[6:8])).timestamp()
    else:
        version_dic["vv"] = None
        version_dic["ts"] = None
    return version

    




# Parse the HTML content


# Find all links on the page
links = soup.find_all('a')

# Extract file details
files = []
for link in links:
    href = link.get('href')
    if href.endswith('.jar'):  # Filter for jar files
        file_info = {
            'name': href,
            'url': url + href
        }
        files.append(file_info)

# Display the list of files
for file in files:
    print(f"Name: {file['name']}, URL: {file['url']}")