"""Deprecated script to update a HuggingFace collection.

HF collections are not suitable for the bioimage.io collection, as they are designed to be a small set of hand-curated items.
"""

from bioimageio.spec import InvalidDescr, load_description
from bioimageio.spec._hf import get_huggingface_api

if __name__ == "__main__":
    api = get_huggingface_api()
    coll = api.get_collection("bioimage-io/collection")
    print(f"collection has {len(coll.items)} items")
    for item in coll.items:
        if item.note:
            print(f"found existing note '{item.note}' for item {item.item_id}")
            continue

        descr = load_description(f"huggingface/{item.item_id}", perform_io_checks=False)
        if isinstance(descr, InvalidDescr):
            print(f"skipping invalid item {item.item_id}")
            continue

        note = f"{descr.name}\n{descr.description}"
        print(f"updating {coll.slug} item {item.item_id} with note '{note}'")
        api.update_collection_item(coll.slug, item.item_object_id, note=note)

    print("done")
