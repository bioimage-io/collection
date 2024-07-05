import argparse
from typing import List, Dict, Any
import os

import requests

from loguru import logger
from ruyaml import YAML, YAMLError

from bioimageio_collection_backoffice.db_structure.compatibility import (
    CompatiblityReport,
)
from bioimageio_collection_backoffice.remote_collection import Record, RemoteCollection
from bioimageio_collection_backoffice.s3_client import Client



def find_java_summaries(directory: str) -> List[str]:
    """Walks through a directory and its subdirectories to find all YAML files."""
    yaml_files: List[str] = []
    # Walk through all directories and files in the specified directory
    for root, _, files in os.walk(directory):
        for file in files:
            # Check if the file ends with .yaml or .yml
            if file.endswith('.yaml') or file.endswith('.yml'):
                # Create the full path to the file
                full_path = os.path.join(root, file)
                # Append the full path to the list of YAML files
                yaml_files.append(full_path)
    return yaml_files



def read_yaml_from_url(url: str):
    """Fetch and parse a YAML file from a specified URL.

    Args:
        url (str): The URL of the YAML file.

    Returns:
        dict: Parsed YAML data as a dictionary.
    """
    response = requests.get(url)
    response.raise_for_status()
    
    yaml=YAML(typ="safe")
    data = yaml.load(response.text)
    return data


def get_tests_from_summaries(rdf: str, path_to_summaries: str) -> Dict[str, str]:
    summary = {}
    try:
        rdf_yaml = read_yaml_from_url(rdf)
    except requests.RequestException as e:
        summary["status"] = "failed"
        summary["error"] = "Unable to access rdf.yaml file"
        summary["details"] = str(e)
        return summary
    except YAMLError as e:
        summary["status"] = "failed"
        summary["error"] = "Unable to read rdf.yaml file"
        summary["details"] = str(e)
        return summary
    
    id = rdf_yaml["id"]
    rdf_path = os.path.join(path_to_summaries, id)
    test_files = os.listdir(rdf_path)
    
    if len(test_files) == 0:
        summary["status"] = "failed"
        summary["error"] = "No tests executed"
        summary["details"] = "The model tests were not executed or the test files could not be located"
        return summary
    
    summaries_yaml = None
    error: str = ""
    for test_file in test_files:
        try:
            summaries_yaml=YAML(typ='safe')  # default, if not specfied, is 'rt' (round-trip)
            summaries_yaml.load(test_file)
            summary = find_passed_test(summaries_yaml)
            if summary["status"] == "passed":
                return summary
        except YAMLError as e:
            error += str(e) + os.linesep
            continue
    
    if summary["status"] is not None:
        return summary

    summary["status"] = "failed"
    summary["error"] = "Unable to read the test results yaml file"
    summary["details"] = str(error)

    return summary


def find_passed_test(summaries_yaml: List[Dict[Any, Any]]) -> Dict[Any, Any]:
    summary = {}
    for elem in summaries_yaml:
        if not isinstance(elem, dict):
            summary["status"] = "failed"
            summary["error"] = "Invalid test output format"
            summary["details"] = "Expected a list of dictionaries, but received an improperly formatted element."
            return summary
        elif elem.get("status") is not None:
            return elem
    
    summary["status"] = "failed"
    summary["error"] = "No test contents found"
    summary["details"] = "test file was empty."
    return summary



def check_compatibility_java_software_impl(
    record: Record,
    software_name: str,
    version: str,
    summaries_dir: str = "test_summaries/artifact",
):
    tool = f"{software_name}{version}"
    report_path = record.get_compatibility_report_path(tool)
    if list(record.client.ls(report_path)):
        return

    rdf_data = record.client.load_file(record.rdf_path)
    assert rdf_data is not None
    rdf = yaml.load(rdf_data)
    assert isinstance(rdf, dict)
    if rdf.get("type") != "model":
        return CompatiblityReport(
            tool=tool,
            status="not-applicable",
            error=None,
            details="only 'model' resources can be used in icy.",
        )
    
    #summaries = find_java_summaries(summaries_dir)
    summary = get_tests_from_summaries(record.client.get_file_url(record.rdf_path), summaries_dir)
    # produce test summaries for each weight format
    # TODO check what it produces summary = test_model(record.client.get_file_url(record.rdf_path))

    return CompatiblityReport(
        tool=tool,
        status=summary["status"],
        error=None if summary["status"] == "passed" else summary["error"],
        details=summary["details"],
        links=["{software_name}/{software_name}"],
    )


def check_compatibility_java_software(
    software_name: str,
    version: str,
    summaries_dir: str = "test_summaries",
):
    """preliminary icy check

    only checks if test outputs are reproduced for onnx, torchscript, or pytorch_state_dict weights.

    """
    collection = RemoteCollection(Client())
    for record in collection.get_published_versions():
        try:
            report = check_compatibility_java_software_impl(
                record, software_name, version, summaries_dir
            )
        except Exception as e:
            logger.error(f"failed to check '{record.id}': {e}")
        else:
            print(report)
            if report is not None:
                record.set_compatibility_report(report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("software_name")
    _ = parser.add_argument("version")
    _ = parser.add_argument("--summaries_dir", default="test_summaries/artifact", help="Directory path where summaries are stored.")

    check_compatibility_java_software(parser.parse_args().software_name, parser.parse_args().version, parser.parse_args().summaries_dir)
