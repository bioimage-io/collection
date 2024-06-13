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
import io.bioimage.modelrunner.engine.EngineInfo;
import io.bioimage.modelrunner.engine.installation.EngineInstall;
import io.bioimage.modelrunner.model.Model;
import io.bioimage.modelrunner.numpy.DecodeNumpy;
import io.bioimage.modelrunner.tensor.Tensor;
import io.bioimage.modelrunner.utils.Constants;
import io.bioimage.modelrunner.utils.YAMLUtils;
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
public class ContinuousIntegration {

	private static Map<String, String> downloadedModelsCorrectly = new HashMap<String, String>();
	private static Map<String, String> downloadedModelsIncorrectly = new HashMap<String, String>();
	
	public static void main(String[] args) throws IOException {
		
		//String pendingMatrix = args[1];
        
        Path currentDir = Paths.get(ContinuousIntegration.class.getProtectionDomain().getCodeSource().getLocation().getPath()).getParent();
        Path rdfDir = currentDir.resolve("../bioimageio-gh-pages/rdfs").normalize();

        // Create a matcher for the pattern 'rdf.yaml'
        runTests(rdfDir, "**", "**", Paths.get("test_summaries"), null);
    }

	
	public static void runTests(Path rdfDir, String resourceID, String versionID, Path summariesDir, String postfix) throws IOException {
		LinkedHashMap<String, String> summaryDefaults = new LinkedHashMap<String, String>();
		postfix = getJDLLVersion();
		summaryDefaults.put("JDLL_VERSION", postfix);
		
		PathMatcher matcher = FileSystems.getDefault().getPathMatcher("glob:" + resourceID + File.separator + versionID + File.separator + Constants.RDF_FNAME);

        List<Path> rdfFiles = Files.walk(rdfDir).filter(matcher::matches).collect(Collectors.toList());
        EngineInstall installer = EngineInstall.createInstaller();
		installer.basicEngineInstallation();
		
		for (Path rdfPath : rdfFiles) {
			String testName = "Reproduce ouptuts with JDLL " + postfix;
			String error = null;
			String status = null;
			String traceback = null;
			
			Map<String, Object> rdf = new LinkedHashMap<String, Object>();
			try {
				rdf = YAMLUtils.load(rdfPath.toAbsolutePath().toString());
			} catch (Exception ex) {
				error = "Unable to load " + Constants.RDF_FNAME + ": " + ex.toString();
				status = "failed";
				traceback = stackTrace(ex);
				ex.printStackTrace();
			}

			Object rdID = rdf.get("id");
			Object type = rdf.get("type");
			Object weightFormats = rdf.get("weights");
			if (rdID == null || !(rdID instanceof String)) {
				System.out.println("Invalid RDF. Missing/Invalid 'id' in rdf: " + rdfPath.toString());
			} else if (type == null || !(type instanceof String) || !((String) type).equals("model")) {
				status = "skipped";
				error = "not a model RDF";
			} else if (weightFormats == null || !(weightFormats instanceof Map)) {
				status = "failed";
				error = "Missing weights dictionary for " + rdID;
				traceback = weightFormats.toString();
			}
			ModelWeight weights = null;
			try {
				weights = ModelWeight.build((Map<String, Object>) weightFormats);
			} catch (Exception ex) {
				status = "failed";
				error = "Missing/Invalid weight formats for " + rdID;
				traceback = stackTrace(ex);
			}
			
			if (weights != null && weights.gettAllSupportedWeightObjects().size() == 0) {
				status = "failed";
				error = "Missing/Invalid weight formats. No supported weigths found for " + rdID;
			}
			
			if (status != null) {
				List<Object> summary = new ArrayList<Object>();
				Map<String, String> summaryMap = new LinkedHashMap<String, String>();
				summaryMap.put("name", testName);
				summaryMap.put("status", status);
				summaryMap.put("error", error);
				summaryMap.put("source_name", rdfPath.toAbsolutePath().toString());
				summaryMap.put("traceback", traceback);
				summaryMap.putAll(summaryDefaults);
				summary.add(summaryMap);
				
				writeSummaries(summariesDir.toAbsolutePath() + File.separator + rdID + File.separator + "test_summary_" + postfix + ".yaml", summary);
				continue;
			}
			
			Map<String, Object> summariesPerWeightFormat = new LinkedHashMap<String, Object>();
						
			for (WeightFormat ww : weights.gettAllSupportedWeightObjects()) {
				List<Object> summariesWeightFormat = new ArrayList<Object>();
				Map<String, String> summaryWeightFormat = new LinkedHashMap<String, String>();
				try {
					summariesWeightFormat = testResource(rdfPath.toAbsolutePath().toString(), ww, 4, "model");
				} catch (Exception ex) {
					ex.printStackTrace();
					summaryWeightFormat.put("name", testName);
					summaryWeightFormat.put("status", "failed");
					summaryWeightFormat.put("error", "unable to perform tests");
					summaryWeightFormat.put("traceback", stackTrace(ex));
					summaryWeightFormat.put("source_name", rdfPath.toAbsolutePath().toString());
					summaryWeightFormat.putAll(summaryDefaults);
					summariesWeightFormat.add(summaryWeightFormat);
				}
				summariesPerWeightFormat.put(ww.getFramework(), summariesWeightFormat);
			}

			List<Object> passedReproducedSummaries = new ArrayList<Object>();
			List<Object> failedReproducedSummaries = new ArrayList<Object>();
			List<Object> otherSummaries = new ArrayList<Object>();
			List<String> seenTests = new ArrayList<String>();
			
			for (Entry<String, Object> entry : summariesPerWeightFormat.entrySet()) {
				String wf = entry.getKey();
				List<Map<String, String>> s = (List<Map<String, String>>) entry.getValue();
				for (Map<String, String> ss : s) {
					boolean isOther = !ss.get("name").equals("reproduce test outputs from test inputs");
					if (isOther && seenTests.contains(ss.toString())) {
						continue;
					}
					ss.put("name", ss.get("name") + " (" + wf + ")");
					if (isOther) {
						seenTests.add(ss.toString());
	                    otherSummaries.add(ss);
	                    continue;
					}
					if (status != null && status.equals("passed")) passedReproducedSummaries.add(ss);
					else failedReproducedSummaries.add(ss);
				}
			}
			
			List<Object> chosenSummaries = new ArrayList<Object>();
			chosenSummaries.addAll(passedReproducedSummaries);
			chosenSummaries.addAll(failedReproducedSummaries);
			chosenSummaries.addAll(otherSummaries);
			
			writeSummaries(summariesDir.toAbsolutePath() + File.separator + rdID + File.separator + "test_summary_" + postfix + ".yaml", chosenSummaries);
		}
	}
	
	private static void writeSummaries(String summariesPath, List<Object> summaries) throws IOException {
		Path path = Paths.get(summariesPath).getParent();
		if (path != null && !Files.exists(path))
            Files.createDirectories(path);
		YAMLUtils.writeYamlFile(summariesPath, summaries);
	}
	
	/**
	 * Code to automatically get the version of JDLL being used
	 * @return the JDLL version being used
	 */
	public static String getJDLLVersion() {
		String version = "UNKNOWN";
        try (InputStream manifestStream = Tensor.class.getClassLoader().getResourceAsStream("META-INF/MANIFEST.MF")) {
            if (manifestStream != null) {
                Manifest manifest = new Manifest(manifestStream);
                java.util.jar.Attributes attrs = manifest.getMainAttributes();
                version = attrs.getValue("Implementation-Version");
            }
        } catch (Exception e) {
        }
        return version;
    }
	
	private static List<Object> testResource(String rdf, WeightFormat weightFormat, int decimal, String expectedType) {
		String error = null;
		String traceback = null;
		ModelDescriptor rd = null;
		try {
			rd = ModelDescriptor.readFromLocalFile(rdf, false);
		} catch (ModelSpecsException e) {
			error = "unable to read rdf.yaml file";
			traceback = stackTrace(e);
		}

		List<Object> tests = new ArrayList<Object>();
		Map<String, String> loadTest = new LinkedHashMap<String, String>();
		loadTest.put("name", "load resource description");
		loadTest.put("status", error == null ? "passed" : "failed");
		loadTest.put("error", error);
		loadTest.put("source_name", rdf);
		loadTest.put("traceback", traceback);
		loadTest.put("JDLL_VERSION", getJDLLVersion());
		
		tests.add(loadTest);
		
		if (rd != null) 
			tests.add(testExpectedResourceType(rd, expectedType));
		if (rd != null && rd.getType().equals("model")) {
			tests.add(testModelDownload(rd));
			tests.add(testModelInference(rd, weightFormat, decimal));
		}
		return tests;
	}
	
	private static Map<String, String> testExpectedResourceType(ModelDescriptor rd,  String type) {
		boolean yes = rd.getType().equals(type);
		Map<String, String> typeTest = new LinkedHashMap<String, String>();
		typeTest.put("name", "has expected resource type");
		typeTest.put("status", yes ? "passed" : "failed");
		typeTest.put("error", yes ? null : "expected type was " + type + " but found " + rd.getType());
		typeTest.put("source_name", rd.getName());
		typeTest.put("traceback", null);
		typeTest.put("JDLL_VERSION", getJDLLVersion());
		return typeTest;
	}
	
	private static Map<String, String> testModelDownload(ModelDescriptor rd) {
		String error = null;
		if (downloadedModelsCorrectly.keySet().contains(rd.getName())) {
			rd.addModelPath(Paths.get(downloadedModelsCorrectly.get(rd.getName())));
		} else if (downloadedModelsIncorrectly.keySet().contains(rd.getName())) {
			error = downloadedModelsIncorrectly.get(rd.getName());
		} else {
			error = downloadModel(rd);
		}
		Map<String, String> downloadTest = new LinkedHashMap<String, String>();
		downloadTest.put("name", "JDLL is able to download model");
		downloadTest.put("status", error == null ? "passed" : "failed");
		downloadTest.put("error", error == null ? null : "unable to download model");
		downloadTest.put("traceback", error);
		downloadTest.put("source_name", rd.getName());
		downloadTest.put("JDLL_VERSION", getJDLLVersion());
		return downloadTest;
	}
	
	private static String downloadModel(ModelDescriptor rd) {
		String error = null;
		try {
			BioimageioRepo br = BioimageioRepo.connect();
			String folder = br.downloadByName(rd.getName(), "models");
			rd.addModelPath(Paths.get(folder));
			downloadedModelsCorrectly.put(rd.getName(), folder);
		} catch (Exception ex) {
			error = stackTrace(ex);
			downloadedModelsIncorrectly.put(rd.getName(), error);
		}
		return error;
	}
	
	private static < T extends RealType< T > & NativeType< T > >
	Map<String, String> testModelInference(ModelDescriptor rd, WeightFormat ww, int decimal) {
		System.out.println(rd.getName());
		System.out.println(ww.getFramework());
		Map<String, String> inferTest = new LinkedHashMap<String, String>();
		inferTest.put("name", "reproduce test inputs from test outptus for " + ww.getFramework());
		inferTest.put("source_name", rd.getName());
		inferTest.put("JDLL_VERSION", getJDLLVersion());
		if (rd.getModelPath() == null) {
			inferTest.put("status", "failed");
			inferTest.put("error", "model was not correctly downloaded");
			return inferTest;
		}
		if (rd.getInputTensors().size() != rd.getTestInputs().size()) {
			inferTest.put("status", "failed");
			inferTest.put("error", "the number of test inputs should be the same as the number of inputs,"
					+ rd.getInputTensors().size() + " vs " + rd.getTestInputs().size());
			return inferTest;
		} else if (rd.getOutputTensors().size() != rd.getTestOutputs().size()) {
			inferTest.put("status", "failed");
			inferTest.put("error", "the number of test outputs should be the same as the number of outputs"
					+ rd.getOutputTensors().size() + " vs " + rd.getTestOutputs().size());
			return inferTest;
		} 

		List<Tensor<?>> inps = new ArrayList<Tensor<?>>();
		List<Tensor<?>> outs = new ArrayList<Tensor<?>>();
		for (int i = 0; i < rd.getInputTensors().size(); i ++) {
			RandomAccessibleInterval<T> rai;
			try {
				rai = DecodeNumpy.retrieveImgLib2FromNpy(rd.getTestInputs().get(i).getLocalPath().toAbsolutePath().toString());
			} catch (Exception e) {
				return failInferenceTest(rd.getName(), "unable to open test input: " + rd.getTestInputs().get(i).getString(), stackTrace(e));
			}
			Tensor<T> inputTensor = Tensor.build(rd.getInputTensors().get(i).getName(), rd.getInputTensors().get(i).getAxesOrder(), rai);
			if (rd.getInputTensors().get(i).getPreprocessing().size() > 0) {
				TransformSpec transform = rd.getInputTensors().get(i).getPreprocessing().get(0);
				JavaProcessing preproc;
				try {
					preproc = JavaProcessing.definePreprocessing(transform.getName(), transform.getKwargs());
				} catch (Exception e) {
					e.printStackTrace();
					return failInferenceTest(rd.getName(), "pre-processing transformation not supported by JDLL: " + transform.getName(), stackTrace(e));
				}
				inputTensor = preproc.execute(rd.getInputTensors().get(i), inputTensor);
			}
			inps.add(inputTensor);
		}
		for (int i = 0; i < rd.getOutputTensors().size(); i ++) {
			Tensor<T> outputTensor = Tensor.buildEmptyTensor(rd.getOutputTensors().get(i).getName(), rd.getOutputTensors().get(i).getAxesOrder());
			outs.add(outputTensor);
		}
		EngineInfo engineInfo;
		try {
			engineInfo = EngineInfo.defineCompatibleDLEngineWithRdfYamlWeights(ww);
		} catch (Exception e) {
			e.printStackTrace();
			return failInferenceTest(rd.getName(), "selected weights not supported by JDLL: " + ww.getFramework(), stackTrace(e));
		}
		Model model;
		try {
			model = Model.createDeepLearningModel(rd.getModelPath(), rd.getModelPath() + File.separator + ww.getSourceFileName(), engineInfo);
			model.loadModel();
		} catch (Exception e) {
			e.printStackTrace();
			return failInferenceTest(rd.getName(), "unable to instantiate/load model", stackTrace(e));
		}
		try {
			model.runModel(inps, outs);
		} catch (Exception e) {
			e.printStackTrace();
			return failInferenceTest(rd.getName(), "unable to run model", stackTrace(e));
		}

		List<Double> maxDif = new ArrayList<Double>();
		for (int i = 0; i < rd.getOutputTensors().size(); i ++) {
			Tensor<T> tt = (Tensor<T>) outs.get(i);
			if (rd.getOutputTensors().get(i).getPostprocessing().size() > 0) {
				TransformSpec transform = rd.getOutputTensors().get(i).getPostprocessing().get(0);
				if (transform.getName().equals("python")) continue;
				JavaProcessing preproc;
				try {
					preproc = JavaProcessing.definePreprocessing(transform.getName(), transform.getKwargs());
				} catch (Exception e) {
					e.printStackTrace();
					return failInferenceTest(rd.getName(), "post-processing transformation not supported by JDLL: " + transform.getName(), stackTrace(e));
				}
				tt = preproc.execute(rd.getInputTensors().get(i), tt);
			}
			RandomAccessibleInterval<T> rai;
			try {
				rai = DecodeNumpy.retrieveImgLib2FromNpy(rd.getTestOutputs().get(i).getLocalPath().toAbsolutePath().toString());
			} catch (Exception e) {
				e.printStackTrace();
				return failInferenceTest(rd.getName(), "unable to open test output: " + rd.getTestOutputs().get(i).getString(), stackTrace(e));
			}
			LoopBuilder.setImages( tt.getData(), rai )
			.multiThreaded().forEachPixel( ( j, o ) -> o.set( (T) new FloatType(o.getRealFloat() - j.getRealFloat())) );
			double diff = computeMaxDiff(rai);
			if (diff > Math.pow(10, -decimal))
				return failInferenceTest(rd.getName(), "output number " + i + " produces a very different result, "
						+ "the max difference is bigger than " + Math.pow(10, -decimal), null);
			maxDif.add(computeMaxDiff(rai));
		}
		
		
		Map<String, String> typeTest = new LinkedHashMap<String, String>();
		typeTest.put("name", "reproduce test outputs from test inputs");
		typeTest.put("status", "passed");
		typeTest.put("error", null);
		typeTest.put("source_name", rd.getName());
		typeTest.put("traceback", null);
		typeTest.put("JDLL_VERSION", getJDLLVersion());
		return typeTest;
	}
	
	private static Map<String, String> failInferenceTest(String sourceName, String error, String tb) {
		Map<String, String> typeTest = new LinkedHashMap<String, String>();
		typeTest.put("name", "reproduce test outputs from test inputs");
		typeTest.put("status", "failed");
		typeTest.put("error", error);
		typeTest.put("source_name", sourceName);
		typeTest.put("traceback", tb);
		typeTest.put("JDLL_VERSION", getJDLLVersion());
		return typeTest;
	}
	
	
	public static < T extends RealType< T > & NativeType< T > > double computeMaxDiff(final RandomAccessibleInterval< T > input) {
			Cursor<T> iterator = Views.iterable(input).cursor();
			T type = iterator.next();
			T min = type.copy();
			T max = type.copy();
			while ( iterator.hasNext() )
			{
				type = iterator.next();
				if ( type.compareTo( min ) < 0 )
					min.set( type );
				if ( type.compareTo( max ) > 0 )
					max.set( type );
			}
			return Math.max(-min.getRealDouble(), min.getRealDouble());
	}

	/** Dumps the given exception, including stack trace, to a string. 
	 * 
	 * @param t
	 * 	the given exception {@link Throwable}
	 * @return the String containing the whole exception trace
	 */
	public static String stackTrace(Throwable t) {
		StringWriter sw = new StringWriter();
		t.printStackTrace(new PrintWriter(sw));
		return sw.toString();
	}
}
