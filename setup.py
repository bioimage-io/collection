import json
import sys
from pathlib import Path

from setuptools import find_packages, setup

# Get the long description from the README file
ROOT_DIR = Path(__file__).parent.resolve()
long_description = (ROOT_DIR / "README.md").read_text(encoding="utf-8")
VERSION_FILE = ROOT_DIR / "bioimageio_collection_backoffice" / "VERSION"
VERSION = json.loads(VERSION_FILE.read_text(encoding="utf-8"))["version"]

if sys.version_info < (3, 8):
    sys.exit("backoffice requires Python >= 3.8")

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
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    packages=find_packages(exclude=["tests"]),
    install_requires=[
        "bioimageio.core @ git+https://github.com/bioimage-io/core-bioimage-io-python@b84d33b321b1f4e755aebe900f0bd74ed74eb012",  # TODO: change to released version
        "bioimageio.spec @ git+https://github.com/bioimage-io/spec-bioimage-io@68479898acdb4a7e4b53a04d86ad6fc014c69ed9",
        "fire",
        "loguru",
        "markdown",
        "minio==7.2.4",
        "pillow",
        "pydantic-settings",
        "pydantic==2.6.3",
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
