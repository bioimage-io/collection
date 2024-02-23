import json
from pathlib import Path

from setuptools import find_packages, setup

# Get the long description from the README file
ROOT_DIR = Path(__file__).parent.resolve()
long_description = (ROOT_DIR / "README.md").read_text(encoding="utf-8")
VERSION_FILE = ROOT_DIR / "backoffice" / "VERSION"
VERSION = json.loads(VERSION_FILE.read_text(encoding="utf-8"))["version"]


setup(
    name="backoffice",
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
    ],
    packages=find_packages(exclude=["tests"]),
    install_requires=[
        "bioimageio.core @ git+https://github.com/bioimage-io/core-bioimage-io-python@3a7875b5debc2d52b2fc87f6579afe217e1c7280",  # TODO: change to released version
        "bioimageio.spec @ git+https://github.com/bioimage-io/spec-bioimage-io@19105665ad779014e03c7b311c0b4003ab08f752",  # TODO: change to released version
        "fire",
        "loguru",
        "minio==7.2.3",
        "python>=3.9",
        "ruyaml",
        "tqdm",
    ],
    extras_require={
        "dev": [
            "black",
            "pdoc",
            "pre-commit",
            "pyright",
            "pytest",
            "torchscript",
        ]
    },
    entry_points={"console_scripts": ["backoffice = backoffice.__main__:main"]},
    project_urls={
        "Bug Reports": "https://github.com/bioimage-io/collection/issues",
        "Source": "https://github.com/bioimage-io/collection",
    },
)
