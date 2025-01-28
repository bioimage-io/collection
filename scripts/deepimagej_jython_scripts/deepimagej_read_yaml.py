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
Jython script that checks if a yaml file corresponds to the bioimage.io format and is supported by deepimagej
"""

from io.bioimage.modelrunner.bioimageio.description import ModelDescriptorFactory



import argparse

import sys
print("ARGV:", sys.argv)
# Create the argument parser
parser = argparse.ArgumentParser()

# Add the arguments
parser.add_argument('-yaml_fpath', type=str, required=True, help='Path to the yaml file that contains the rdf.yaml file')


# Parse the arguments
args = parser.parse_args()
yaml_fpath = args.yaml_fpath

print(f"YAML_FILE: '{yaml_fpath}'")
#descriptor = ModelDescriptorFactory.readFromLocalFile(yaml_fpath)