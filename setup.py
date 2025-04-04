import json
import sys
from pathlib import Path

from setuptools import find_packages, setup

# Get the long description from the README file
ROOT_DIR = Path(__file__).parent.resolve()
long_description = (ROOT_DIR / "README.md").read_text(encoding="utf-8")
VERSION_FILE = ROOT_DIR / "bioimageio_collection_backoffice" / "VERSION"
VERSION = json.loads(VERSION_FILE.read_text(encoding="utf-8"))["version"]

if sys.version_info < (3, 9):
    sys.exit("backoffice requires Python >= 3.9")

_ = setup(
    name="bioimageio-collection-backoffice",
    version=VERSION,
    description="backoffice to control bioimage.io collection",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/bioimage-io/collection",
    author="bioimage.io Team",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
    packages=find_packages(exclude=["tests"]),
    install_requires=[
        "bioimageio.core>=0.8.0",
        "bioimageio.spec>=0.5.4.1",
        "fire",
        "loguru",
        "markdown",
        "minio==7.2.4",
        "pillow",
        "pydantic-settings",
        "PyGithub",
        "pydantic>=2.7.0,<2.10",  # TODO: update upper pin after pydantic 2.10 fix, see https://github.com/bioimage-io/spec-bioimage-io/pull/664
        "requests",
        "ruyaml",
        "tqdm",
    ],
    extras_require={
        "dev": [
            "black",
            "pdoc",
            "pre-commit",
            "pygithub",
            "pyright",
            "pytest",
            "torch",
        ]
    },
    entry_points={
        "console_scripts": [
            "backoffice = bioimageio_collection_backoffice.__main__:main"
        ]
    },
    project_urls={
        "Bug Reports": "https://github.com/bioimage-io/collection/issues",
        "Source": "https://github.com/bioimage-io/collection",
    },
)
