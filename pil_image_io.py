from io import BytesIO

import numpy as np
import tifffile
from PIL import Image, ImageSequence

data = np.random.random((2, 5, 6, 7)).astype(np.float32)

print(data.shape)

stream = BytesIO()

with tifffile.TiffWriter(stream, mode="w", bigtiff=False, shaped=True) as writer:
    # for t, d in enumerate(data):
    #     _ = writer.write(d, volumetric=False, description=f"frame {t}")

    _ = writer.write(data, volumetric=False, description=f"{data.shape}")

_ = stream.seek(0)
im = Image.open(stream)

# print(im.size)
print(im.format_description)

for m in ImageSequence.Iterator(im):
    print(len(m.get_flattened_data()))

# print(im.n_frames)
# for i, p in enumerate(ImageSequence.Iterator(im)):
#     print("page", i, p.size, p.mode, p.n_frames)
#     for ii, pp in enumerate(ImageSequence.Iterator(p)):
#         print("subpage", i, ii, pp.size, pp.mode)
