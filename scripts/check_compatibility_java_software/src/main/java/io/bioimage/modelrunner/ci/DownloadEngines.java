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

import io.bioimage.modelrunner.engine.installation.EngineInstall;
import io.bioimage.modelrunner.versionmanagement.InstalledEngines;

/**
 * Class to install the engines that a DIJ or Icy distribution would install
 * 
 * @author Carlos Javier GArcia Lopez de Haro
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
			engineManager.basicEngineInstallation();
			//InstalledEngines.buildEnginesFinder(ENGINES_DIR).getDownloadedForOS().stream().map(i -> i.toString())
			System.out.println(InstalledEngines.buildEnginesFinder(ENGINES_DIR).getDownloadedForOS());
		}
    }
}
