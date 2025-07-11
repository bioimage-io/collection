"""run tests with bioimageio.core"""

import subprocess
from concurrent.futures import Future, ThreadPoolExecutor, as_completed

import bioimageio.core
from loguru import logger
from tqdm import tqdm

from backoffice.utils import get_log_file, get_tool_report_path

from .index import Item, ItemVersion, create_index


def run_core_on_collection():
    """Test the bioimage.io collection"""
    index = create_index()

    with ThreadPoolExecutor() as executor:
        futures: list[Future[tuple[Item, ItemVersion]]] = []
        for item in index.items:
            for v in item.versions:
                futures.append(executor.submit(run_core, item, v))
                break
            break

        for fut in tqdm(as_completed(futures), total=len(futures)):
            item, v = fut.result()
            _log_test(item, v)


def run_core(item: Item, v: ItemVersion):

    domain, *id_parts = item.id.split("/")
    item_id = "/".join(id_parts)
    source = f"https://hypha.aicell.io/{domain}/artifacts/{item_id}/files/rdf.yaml?version={v.version}"
    summary_path = get_tool_report_path(
        item.id, v.version, "bioimageio.core", bioimageio.core.__version__
    )
    cmd = [
        "bioimageio",
        "test",
        "--determinism=full",
        "--runtime-env=as-described",
        f"--summary={summary_path}",
        source,
    ]

    log_file = get_log_file(item.id, v.version)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("w") as f:
        _ = subprocess.run(
            cmd,
            check=False,
            stdout=f,
            stderr=f,
            encoding="utf-8",
        )

    return (item, v)


def _log_test(item: Item, v: ItemVersion):
    logger.opt(depth=1).info("{}/{} done", item.id, v.version)
