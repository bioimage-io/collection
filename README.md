[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

#### workflow status

|   | [![check compatibility](https://github.com/bioimage-io/collection/actions/workflows/check_compatibility.yaml/badge.svg)](https://github.com/bioimage-io/collection/actions/workflows/check_compatibility.yaml) |
| --- | --- |
| [![create bioimage.io index](https://github.com/bioimage-io/collection/actions/workflows/index.yaml/badge.svg)](https://github.com/bioimage-io/collection/actions/workflows/index.yaml) | [![BiaPy compatibility](https://github.com/bioimage-io/collection/actions/workflows/check_compatibility_biapy.yaml/badge.svg)](https://github.com/bioimage-io/collection/actions/workflows/check_compatibility_biapy.yaml)<br>[![bioimageio.core compatibility](https://github.com/bioimage-io/collection/actions/workflows/check_compatibility_bioimageio_core.yaml/badge.svg)](https://github.com/bioimage-io/collection/actions/workflows/check_compatibility_bioimageio_core.yaml)<br>[![CAREamics compatibility](https://github.com/bioimage-io/collection/actions/workflows/check_compatibility_careamics.yaml/badge.svg)](https://github.com/bioimage-io/collection/actions/workflows/check_compatibility_careamics.yaml)<br>[![ilastik compatibility](https://github.com/bioimage-io/collection/actions/workflows/check_compatibility_ilastik.yaml/badge.svg)](https://github.com/bioimage-io/collection/actions/workflows/check_compatibility_ilastik.yaml)

# collection

This repository is used to add information to the resources displayed on [bioimage.io][https://bioimage.io].
Primarily it adds information about software compatibility of bioimage.io community partners.

## Maintaining the bioimage.io Collection

Current reviewers are listed in [`bioimageio_collection_config.json`][review-config], under section `reviewers`.
Resource upload and review are handled by [bioimage.io](https://github.com/bioimage-io/bioimage.io).

### Reviewer Onboarding

1. Open a pull request, adding a person to the [list of reviewers][review-config], see <https://github.com/bioimage-io/collection/pull/75> for an example.
   * one public email address is required
   * github id can be found using `https://api.github.com/users/<github_username>`
2. For the changes to be applied, the service needs to be restarted manually. Reach out to the team or leave an issue.
3. Once the pull request has been merged and the respective Hypha service has been restarted, the new reviewer can
   * accept resource drafts
   * request changes on resource drafts
   * upload a new version for any resource

#### Software Compatibility Checks

Resource published on [bioimage.io](https://github.com/bioimage-io/bioimage.io) are automatically tested for compatibility with registered bioimage.io community partner tools.

# Add community partner

To link yourself as a community partner, please create a PR to insert relevant metadata into [bioimageio_collection_config.json](https://github.com/bioimage-io/collection/blob/4087336ad00bff0198f5de83c94aa13be357840d/bioimageio_collection_config.json) under `"partners"`.
Checkout [ilastik partner entry](https://github.com/bioimage-io/collection/blob/4087336ad00bff0198f5de83c94aa13be357840d/bioimageio_collection_config.json#L283-L301) for an example.

## Add community partner compatibility checks

Any community partner is invited to add a GitHub Actions workflow in this repo (please make a PR) that generates reports on its software compatibility with new and updated resources in the bioimage.io collection.
See [ilastik compatibility checks workflow](https://github.com/bioimage-io/collection/blob/main/.github/workflows/check_compatibility_ilastik.yaml) for an example.

If you are not familiar with GitHub Actions workflows, we can help you to set this up analog to our existing community partner compatibility checks.
Ideally you can provide a script to create a compatibility report (a relativley simple json file) for a given resource description. see [this Python script as an example](https://github.com/bioimage-io/collection/blob/main/scripts/check_compatibility_ilastik.py).
