/*-
 * #%L
 * This project performs Continuous Integration tasks on the JDLL library
 * %%
 * Copyright (C) 2023 Institut Pasteur.
 * %%
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 * 
 *      http://www.apache.org/licenses/LICENSE-2.0
 * 
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * #L%
 */
package io.bioimage.modelrunner.ci;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.nio.file.FileSystems;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.PathMatcher;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Map.Entry;
import java.util.jar.Manifest;
import java.util.stream.Collectors;

import io.bioimage.modelrunner.bioimageio.BioimageioRepo;
import io.bioimage.modelrunner.bioimageio.description.ModelDescriptor;
import io.bioimage.modelrunner.bioimageio.description.TransformSpec;
import io.bioimage.modelrunner.bioimageio.description.exceptions.ModelSpecsException;
import io.bioimage.modelrunner.bioimageio.description.weights.ModelWeight;
import io.bioimage.modelrunner.bioimageio.description.weights.WeightFormat;
import io.bioimage.modelrunner.bioimageio.download.DownloadTracker;
import io.bioimage.modelrunner.bioimageio.download.DownloadTracker.TwoParameterConsumer;
import io.bioimage.modelrunner.engine.EngineInfo;
import io.bioimage.modelrunner.engine.installation.EngineInstall;
import io.bioimage.modelrunner.model.Model;
import io.bioimage.modelrunner.numpy.DecodeNumpy;
import io.bioimage.modelrunner.tensor.Tensor;
import io.bioimage.modelrunner.utils.Constants;
import io.bioimage.modelrunner.utils.YAMLUtils;
import io.bioimage.modelrunner.versionmanagement.InstalledEngines;
import net.imglib2.Cursor;
import net.imglib2.RandomAccessibleInterval;
import net.imglib2.loops.LoopBuilder;
import net.imglib2.type.NativeType;
import net.imglib2.type.numeric.RealType;
import net.imglib2.type.numeric.real.FloatType;
import net.imglib2.view.Views;

/**
 * 
 */
public class DownloadEngines {
	
	public static final String DEEPIMAGEJ_TAG = "deepimagej";
	
	public static final String ICY_TAG = "icy";
	/**
	 * Current directory
	 */
	private static final String CWD = new File("").getAbsolutePath();
	/**
	 * Directory where the engine will be downloaded, if you want to download it
	 * into another folder, please change it.
	 */
	private static final String ENGINES_DIR = new File(CWD, "engines").getAbsolutePath();
	
	public static void main(String[] args) throws IOException, InterruptedException {
		if (args[0].equals(DEEPIMAGEJ_TAG)) {
			EngineInstall engineManager = EngineInstall.createInstaller(ENGINES_DIR);
			Map<String, TwoParameterConsumer<String, Double>> consumers = 
					new LinkedHashMap<String, TwoParameterConsumer<String, Double>>();
			Thread checkAndInstallMissingEngines = new Thread(() -> {
				consumers.putAll(engineManager.getBasicEnginesProgress());
				engineManager.basicEngineInstallation();
	        });
			System.out.println("[DEBUG] Checking and installing missing engines");
			checkAndInstallMissingEngines.start();
			
			String backup = "";
			EngineInstallationProgress installerInfo = new EngineInstallationProgress();
			while (!engineManager.isInstallationFinished()) {
				Thread.sleep(300);
				if (consumers.keySet().size() != 0) {
					String progress = installerInfo.basicEnginesInstallationProgress(consumers);
					System.out.println(progress);
				}
			}
		}
    }
}
