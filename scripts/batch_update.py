from io import BytesIO

from ruyaml import YAML

from bioimageio_collection_backoffice.remote_collection import RemoteCollection
from bioimageio_collection_backoffice.s3_client import Client

yaml = YAML(typ="safe")


def remove_colab_badges():
    rc = RemoteCollection(Client())
    for r in rc.get_published_versions():
        rdf = r.get_rdf()
        for badge in rdf.get("badges", []):
            if badge.get("icon") == "colab-badge.svg":
                badge["icon"] = (
                    "https://colab.research.google.com/assets/colab-badge.svg"
                )

        stream = BytesIO()
        yaml.dump(rdf, stream)
        data = stream.getvalue()
        assert data
        r.client.put(r.rdf_path, BytesIO(data), len(data))

        path = f"{r.folder}files/colab-badge.svg"
        if list(r.client.ls(path)):
            r.client.rm(path)


def add_info_json():
    rc = RemoteCollection(Client())
    for r in rc.get_published_versions():
        if not list(r.client.ls(r.folder + "info.json")):
            info = r.info
            r.update_info(info)

    for r in rc.get_drafts():
        if not list(r.client.ls(r.folder + "info.json")):
            info = r.info
            r.update_info(info)


if __name__ == "__main__":
    # remove_colab_badges()  # June 5, 2024
    # add_info_json()  # June 5, 2024
    pass
