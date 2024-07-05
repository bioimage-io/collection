import argparse
import requests
from bs4 import BeautifulSoup
import re
import datetime
from typing import Dict, Any, List
from packaging.version import Version
from pathlib import Path
import os
import zipfile
import xml.etree.ElementTree as ET
import json

DEEPIMAGEJ_UPDATE_SITE_URL = "https://sites.imagej.net/DeepImageJ/plugins/"
DEEPIMAGEJ_PATTERN = r"DeepImageJ-(\d+\.\d+\.\d+)\.jar-(\d{14})"
DIJ_POM_FILE = 'META-INF/maven/io.github.deepimagej/DeepImageJ_/pom.xml'
MINIMUM_DIJ_VERSION = Version("3.0.4")
DEEPIMAGEJ_TAG = "deepimagej"


ICY_POM_FILE = ''
ICY_TAG = "icy"

TEMP_PATH = os.path.abspath("TEMP")

JDLL_GROUP_ID = "io.bioimage"

JDLL_ARTIFACT_ID = "dl-modelrunner"


def download_file(url: str, local_filename: str):
    with requests.get(url, stream=True) as response:
        response.raise_for_status()
        with open(local_filename, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                _ = file.write(chunk)


def get_version_from_pomxml(content: str) -> str:
    root = ET.fromstring(content)
    namespace = "{http://maven.apache.org/POM/4.0.0}"

    version = ""
    for dependency in root.findall(f".//{namespace}dependency"):
        group_id = dependency.find(f"{namespace}groupId")
        artifact_id = dependency.find(f"{namespace}artifactId")
        if group_id is not None and artifact_id is not None:
            if group_id.text == JDLL_GROUP_ID and artifact_id.text == JDLL_ARTIFACT_ID:
                version = dependency.find(f"{namespace}version").text
                break
        if version == "":
            raise FileNotFoundError("JDLL version not founf in pom.xml")

    return version


def read_file_in_jar(jar_file_path: str, file_name: str) -> str:
    with zipfile.ZipFile(jar_file_path, 'r') as jar:
        if file_name in jar.namelist():
            with jar.open(file_name) as file:
                content = file.read().decode('utf-8')
                return content
        else:
            raise FileNotFoundError(f"{file_name} not found in the JAR file")



def find_associated_jdll_version(link: str) -> str:
    Path(TEMP_PATH).mkdir(parents=True, exist_ok=True)
    fname = os.path.join(TEMP_PATH, link.split("/")[-1])
    download_file(link, fname)
    if "deepimagej" in link.lower():
        return get_version_from_pomxml(read_file_in_jar(fname, DIJ_POM_FILE))
    else:
        return get_version_from_pomxml(read_file_in_jar(fname, ICY_POM_FILE))


def parse_links() -> List[Any]:
    response = requests.get(DEEPIMAGEJ_UPDATE_SITE_URL)
    soup = BeautifulSoup(response.content, 'html.parser')
    links = soup.find_all('a')
    return links



def get_deepimagej_versions() -> Dict[str, str]:
    """
    Retrieves deepImageJ versions and their associated JDLL versions.

    This method parses available links, filters for relevant deepImageJ JAR files,
    and extracts their versions and timestamps. It then associates each unique deepImageJ 
    version with the corresponding JDLL version deom the deepImageJ pom.xml file.

    Returns:
        Dict[str, str]: A dictionary where each key is a deepImageJ version and the value 
        is the associated JDLL version.
    """
    links = parse_links()
    v_dic: Dict[str, Any] = {}
    v_dic_rev: Dict[str, str] = {}
    for link in links:
        href = link.get('href')
        if '.jar' in href and 'deepimagej' in href.lower() and 'deepimagej_' not in href.lower():
            tmp_dic = get_dij_version_and_date(href)
            if Version(tmp_dic["vv"]) < MINIMUM_DIJ_VERSION:
                continue
            if tmp_dic["vv"] not in v_dic_rev.keys():
                v_dic_rev[tmp_dic["vv"]] = tmp_dic["ts"]
                v_dic[href] = tmp_dic
            elif tmp_dic["ts"] > v_dic_rev[tmp_dic["vv"]]:
                v_dic[href] = tmp_dic
                v_dic_rev[tmp_dic["vv"]] = tmp_dic["ts"]
    assoc_dict: Dict[str, str] = {}
    for kk in v_dic.keys():
        jdll_v = find_associated_jdll_version(DEEPIMAGEJ_UPDATE_SITE_URL + kk)
        assoc_dict[v_dic[kk]["vv"]] = jdll_v
    return assoc_dict
    


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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("software_name")
    if parser.parse_args().software_name == DEEPIMAGEJ_TAG:
        matrix = get_deepimagej_versions()
        #print(json.dumps(matrix))
        #print(f"matrix={json.dumps({"0.0.1": "0.5.9"})}")
        matrix = [{"0.0.1": "0.5.9"}]
        print(f"matrix={json.dumps(matrix)}")
    elif parser.parse_args().software_name == ICY_TAG:
        #print(f"matrix={json.dumps({"0.0.1": "0.5.9"})}")
        matrix = [{"0.0.1": "0.5.9"}]
        print(f"matrix={json.dumps(matrix)}")
