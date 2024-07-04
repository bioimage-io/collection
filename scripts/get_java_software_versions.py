import requests
from bs4 import BeautifulSoup
import re
import datetime
from typing import Dict, Any
from packaging.version import Version

DEEPIMAGEJ_UPDATE_SITE_URL = "https://sites.imagej.net/DeepImageJ/plugins/"
DEEPIMAGEJ_PATTERN = r"DeepImageJ-(\d+\.\d+\.\d+)\.jar-(\d{14})"
MINIMUM_DIJ_VERSION = Version("3.0.0")


def download_file(url: str, local_filename: str):
    with requests.get(url, stream=True) as response:
        response.raise_for_status()
        with open(local_filename, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                _ = file.write(chunk)

def find_associated_jdll_version():
    return None


def get_deepimagej_versions():
    response = requests.get(DEEPIMAGEJ_UPDATE_SITE_URL)
    soup = BeautifulSoup(response.content, 'html.parser')
    links = soup.find_all('a')
    v_dic: Dict[str, Any] = {}
    v_dic_rev: Dict[str, str] = {}
    for link in links:
        href = link.get('href')
        if '.jar' in href and 'deepimagej' in href.lower():
            tmp_dic = get_dij_version_and_date(href)
            if Version(tmp_dic["vv"]) < MINIMUM_DIJ_VERSION:
                continue
            if tmp_dic["vv"] not in v_dic_rev.keys():
                v_dic_rev[tmp_dic["vv"]] = tmp_dic["ts"]
                v_dic[href] = tmp_dic
            elif tmp_dic["ts"] > v_dic_rev[tmp_dic["vv"]]:
                v_dic[href] = tmp_dic
                v_dic_rev[tmp_dic["vv"]] = tmp_dic["ts"]
    find_associated_jdll_version()
    


def get_dij_version_and_date(filename: str) -> Dict[str, Any]:
    match = re.search(DEEPIMAGEJ_PATTERN, filename)

    version_dic: Dict[str, Any] = {}
    if match:
        version = match.group(1)
        date = match.group(2)
        version_dic["vv"] = version
        version_dic["ts"] = datetime.datetime(int(date[:4]), int(date[4:6]), int(date[6:8])).timestamp()
    else:
        version_dic["vv"] = None
        version_dic["ts"] = None
    return version_dic

    




# Parse the HTML content


get_deepimagej_versions()