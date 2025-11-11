# Copyright (C) 2024 deepImageJ developers
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ============================================================================

"""
Jython script that downloads the wanted model(s) from the Bioimage.io repo and
creates a macro to run the model(s) downloaded on the sample input with deepimageJ
"""

from io.bioimage.modelrunner.bioimageio import BioimageioRepo
from io.bioimage.modelrunner.bioimageio.description import ModelDescriptorFactory
from io.bioimage.modelrunner.numpy import DecodeNumpy

from deepimagej.tools import ImPlusRaiManager

from ij import IJ

import os
import argparse
import json

MACRO_STR = 'run("DeepImageJ Run", "model_path={model_path} input_path={input_path} output_folder={output_folder} display_output=null")'
CREATED_INPUT_SAMPLE_NAME = "converted_sample_input_0.tif"
CREATED_OUTPUT_SAMPLE_NAME = "converted_sample_ouput_0.tif"


def convert_npy_to_tif(
    folder_path, test_name, axesOrder, name=CREATED_INPUT_SAMPLE_NAME
):
    rai = DecodeNumpy.loadNpy(os.path.join(folder_path, test_name))
    imp = ImPlusRaiManager.convert(rai, axesOrder)
    out_path = os.path.join(folder_path, name)
    IJ.saveAsTiff(imp, out_path)


# Create the argument parser
parser = argparse.ArgumentParser()

# Add the arguments
parser.add_argument(
    "-yaml_fpath",
    type=str,
    required=True,
    help="Path to the yaml file that contains the rdf.yaml file",
)
parser.add_argument(
    "-models_dir",
    type=str,
    required=True,
    help="Directory where models are going to be saved",
)


# Parse the arguments
args = parser.parse_args()
rdf_fname = args.yaml_fpath
models_dir = args.models_dir

descriptor = ModelDescriptorFactory.readFromLocalFile(rdf_fname)


if not os.path.exists(models_dir) or not os.path.isdir(models_dir):
    os.makedirs(models_dir)


br = BioimageioRepo.connect()
mfp = br.downloadModelByID(descriptor.getModelID(), models_dir)

macro_path = os.path.join(mfp, os.getenv("MACRO_NAME"))

outputs_json = []


with open(macro_path, "a") as file:
    sample_name = descriptor.getInputTensors().get(0).getSampleTensorName()
    if sample_name is None:
        test_name = descriptor.getInputTensors().get(0).getTestTensorName()
        print(descriptor.getName() + ": " + test_name)
        if test_name is None:
            raise Exception(
                "There are no test inputs for model: " + descriptor.getModelID()
            )
        convert_npy_to_tif(
            mfp, test_name, descriptor.getInputTensors().get(0).getAxesOrder()
        )
        sample_name = CREATED_INPUT_SAMPLE_NAME
    if " " in mfp:
        macro = MACRO_STR.format(
            model_path="[" + mfp + "]",
            input_path="[" + os.path.join(mfp, sample_name) + "]",
            output_folder="[" + os.path.join(mfp, "outputs") + "]",
        )
    else:
        macro = MACRO_STR.format(
            model_path=mfp,
            input_path=os.path.join(mfp, sample_name),
            output_folder=os.path.join(mfp, "outputs"),
        )
    macro = macro.replace(os.sep, os.sep + os.sep)
    file.write(macro + os.linesep)

for n in range(descriptor.getOutputTensors().size()):
    test_name = descriptor.getOutputTensors().get(n).getTestTensorName()
    if test_name is None:
        sample_name = descriptor.getOutputTensors().get(n).getSampleTensorName()
        if sample_name is None:
            raise Exception(
                "There are no test ouputs for model: " + descriptor.getModelID()
            )
    else:
        convert_npy_to_tif(
            mfp,
            test_name,
            descriptor.getOutputTensors().get(n).getAxesOrder(),
            name=CREATED_OUTPUT_SAMPLE_NAME,
        )
        sample_name = CREATED_OUTPUT_SAMPLE_NAME
    out_dict = {}
    out_dict["name"] = descriptor.getOutputTensors().get(n).getName()
    out_dict["dij"] = os.path.join(mfp, "outputs")
    out_dict["expected"] = os.path.join(mfp, CREATED_OUTPUT_SAMPLE_NAME)
    outputs_json.append(out_dict)

with open(os.path.join(mfp, os.getenv("JSON_OUTS_FNAME")), "w") as f:
    json.dump(outputs_json, f)

print(mfp)
