"""
programmatic staging of a new resource version (for advanced/internal use only)
"""

import github

from bioimageio_collection_backoffice._settings import settings


def bioimageio_upload(resource_id: str, package_url: str):
    g = github.Github(login_or_token=settings.github_pat.get_secret_value())

    repo = g.get_repo("bioimage-io/collection")

    workflow = repo.get_workflow("stage.yaml")

    ref = repo.get_branch("main")
    ok = workflow.create_dispatch(
        ref=ref,
        inputs={
            "resource_id": resource_id,
            "package_url": package_url,
        },
    )
    assert ok
