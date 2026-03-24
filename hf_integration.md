# HF integration

- Our metadata schema defining/validating python library bioimageio.spec >=0.5.7.3 has a (for now private) push_to_hub() function and is capable of resolving compatible models from Huggingface, e.g. as "huggingface/thefynnbe/ambitious-sloth"
  - uploads have the library=bioimageio metadata set
- As a first example I uploaded [ambitious-sloth](https://bioimage.io/#/artifacts/ambitious-sloth) to HuggingFace at <https://huggingface.co/thefynnbe/ambitious-sloth>
- There is a preliminary bioImage-io organization on HF
  - It has a HF collection "collection" of bioimageio compatible models (currently just the 'ambitious-sloth'):  <https://huggingface.co/collections/bioimage-io/collection>

Open questions are:

- Is there a similar search functionality within a collection as there is in the regular model browser interface (<https://huggingface.co/models?library=bioimageio&sort=trending>)?
- How could we support access to inference providers?
  - most generic case: >=1 nd tensors in; >=1 nd tensors out; custom Python dependencies
  - many cases so far: 1 2d/3d tensor in; 1 2d/3d tensor out; pure torchscript (or onnx) weights available
  - (HF task image-2-image or image-segmentation seems to be limited to 2d and not natively support numpy arrays (PIL images only?))
- What is the best way forward to host more of the bioimage.io collection on HF?
  - A curated collection?
  - querying for 'bioimageio' tag (as 'tag' or 'library') (no curation)
  - forking/cloning models under the bioimage-io organization (does not seem to scale well)
- How to link back and forth between huggingface.com and BioImage.io?
