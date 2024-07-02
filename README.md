![internal tests](https://github.com/bioimage-io/collection/actions/workflows/build.yaml/badge.svg) ![generate collection overview](https://github.com/bioimage-io/collection/actions/workflows/generate_collection_json.yaml/badge.svg)

# collection

This repository is used to manage the resources displayed on [bioimage.io][bioimageio].

Most users will not directly dispatch the workflows defined in this reporitory, but should instead login on [bioimage.io][bioimageio] and use the front-end to interact with the bioimage.io collection.

We currently do not have a workflow for direct upload, but publicly available resource packages may be staged with a stage workflow dispatch.

## Maintaining the bioimage.io Collection

In order to update or add new resources to the [bioimage.io][bioimageio] collection, they have to undergo review.
Current reviewers are listed in [`bioimageio_collection_config.json`][review-config], under section `reviewers`.

### Reviewer Onboarding

1. Open a pull request, adding a person to the [list of reviewers][review-config], see https://github.com/bioimage-io/collection/pull/75 for an example.
   * one public email address is required
   * github id can be found using `https://api.github.com/users/<github_username>`
1. Once the pull request has been merged, the new reviewer can
   * accept resource drafts
   * request changes on resource drafts
   * upload a new version for any resource

### Review Process

The review process technically starts after a user uploaded a _resource package_.
Such a _resource package_ could e.g. be a newly uploaded _model package_, or _notebook package_, or an updated version of any existing resource.
Typically, uploaders would go via [bioimage.io/upload][upload].
Alternatively, any direct link to a downloadable resource package (`.zip`-file) would work.
The latter option is reserved for members of this repository (or the bioimageio org).

#### Staging

Now the stage workflow needs to be dispatched.
If the resource package was uploaded via the bioimage.io website, this is initiated automatically.
In case of a url to a resource package, the `stage` workflow needs to be [dispatched manually, or via github api][staging-action] ("run workflow").
Staging unpacks the files from the zipped resource package to our public S3.
Once unpacked, the staged _resource draft_ is automatically tested ([test action][test-action] is triggerd automatically at the end of the stage action).

#### Testing

Staged resource drafts are automatically tested:
* Is their metadata valid?
* Can test outputs be reproduced from test inputs?
* Are linked URLs available?
* ...

Once the

3. awaiting reviewe: After the tests have concluded the bioimageio reviewers are notified.
4. The reviewer will result in
    a) changes requested: Please upload an updated draft (which overwrites the current draft).
    b) accepted: The resource will be published (and the draft deleted).

Additionally an 'error' status may be shown if an exception occured.
This also may be the case for invalid inputs.

```mermaid
graph TD;
    unpacking[1: unpacking]-->unpacked[unpacked]
    unpacked-->testing[2: testing]
    testing-->ar[3: awaiting review]
    ar--->cr[4a: changes requestd]
    cr-->unpacking
    ar--->accepted[4b: accepted]
    accepted-->published[published: (draft is deleted)]
```

[bioimageio]: https://bioimage.io
[review-config]: https://github.com/bioimage-io/collection/blob/main/bioimageio_collection_config.json
[staging-action]: https://github.com/bioimage-io/collection/actions/workflows/stage.yaml
[test-action]: https://github.com/bioimage-io/collection/actions/workflows/test.yaml
[upload]: https://bioimage.io/#/upload
