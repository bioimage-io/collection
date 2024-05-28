![internal tests](https://github.com/bioimage-io/collection/actions/workflows/build.yaml/badge.svg) ![generate collection overview](https://github.com/bioimage-io/collection/actions/workflows/generate_collection_json.yaml/badge.svg)

# collection

This repository is used to manage the resources displayed on [bioimage.io](http://bioimage.io).

Most users will not directly dispatch the workflows defined in this reporitory, but should instead login on [bioimage.io](http://bioimage.io) and use the front-end to interact with the bioimage.io collection.

We currently do not have a workflow for direct upload, but publicly available resource packages may be staged with a stage workflow dispatch.

## Lifecycle of a draft

1. unpacking: Uploaded resource packages are unpacked and their individuell files uploaded to our public S3 storage.
2. testing: Staged resource drafts are automatically tested: Is their metadata valid? Can test outputs be reproduced from test inputs? Are linked URLs available?
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
