/*-
 * #%L
 * This project performs Continuous Integration tasks on java software based on JDLL
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
	
	private static String version;
	
	private static String software;
	private static final String TEST_NAME = "reproduce test outputs from test inputs";
	
	public static void main(String[] args) throws IOException {
		if (args.length != 0) {
			software = args[0];
			version = args[1];
		} else {
			software = "default";
			version = "default";
		}
        
        Path currentDir = Paths.get(ContinuousIntegration.class.getProtectionDomain().getCodeSource().getLocation().getPath()).getParent();
        Path rdfDir = currentDir.resolve("../../../bioimageio-gh-pages/rdfs").normalize();

        // Create a matcher for the pattern 'rdf.yaml'
        runTests(rdfDir, "**", "**", Paths.get("test_summaries_" + software + "_" + version));
    }

	
	public static void runTests(Path rdfDir, String resourceID, String versionID, Path summariesDir) throws IOException {
		
		PathMatcher matcher = FileSystems.getDefault().getPathMatcher("glob:" + resourceID + File.separator + versionID + File.separator + Constants.RDF_FNAME);

        List<Path> rdfFiles = Files.walk(rdfDir).filter(matcher::matches).collect(Collectors.toList());
        EngineInstall installer = EngineInstall.createInstaller();
		installer.basicEngineInstallation();
		
		for (Path rdfPath : rdfFiles) {
			System.out.println("");
			System.out.println("");
			System.out.println(rdfPath);
			
			Map<String, Object> rdf = new LinkedHashMap<String, Object>();
			try {
				rdf = YAMLUtils.load(rdfPath.toAbsolutePath().toString());
			} catch (Exception ex) {
				ex.printStackTrace();
				continue;
			}

			Object rdID = rdf.get("id");
			String summariesPath = summariesDir.toAbsolutePath() + File.separator
					+ (rdID != null ? rdID : "") + File.separator + "test_summary" + ".yaml";
			Object type = rdf.get("type");
			Object weightFormats = rdf.get("weights");
			if (rdID == null || !(rdID instanceof String)) {
				new Exception(rdfPath.toAbsolutePath().toString() + " is missing ID field").printStackTrace();
				continue;
			} else if (type == null || !(type instanceof String) || !((String) type).equals("model")) {
				Map<String, String> summary = create(rdfPath, "not-applicable", null,  null, "not a model");
				writeSummary(summariesPath, summary);
				continue;
			} else if (weightFormats == null || !(weightFormats instanceof Map)) {
				Map<String, String> summary = create(rdfPath, 
						"failed", "Missing weights dictionary for " + rdID,  null, weightFormats.toString());
				writeSummary(summariesPath, summary);
				continue;
			}
			ModelWeight weights = null;
			try {
				weights = ModelWeight.build((Map<String, Object>) weightFormats);
			} catch (Exception ex) {
				Map<String, String> summary = create(rdfPath,
						"failed", "Missing/Invalid weight formats for " + rdID,  stackTrace(ex), "Unable to read weight formats");
				writeSummary(summariesPath, summary);
				continue;
			}
			
			if (weights != null && weights.gettAllSupportedWeightObjects().size() == 0) {
				Map<String, String> summary = create(rdfPath,
						"failed", "Unsupported model weights",  null, "The model weights belong to a Deep Learning "
								+ "framework not supported by " + software + "_" + version + ".");
				writeSummary(summariesPath, summary);
				continue;
			}
			
						
			for (WeightFormat ww : weights.gettAllSupportedWeightObjects()) {
				Map<String, String> summaryWeightFormat = new LinkedHashMap<String, String>();
				try {
					summaryWeightFormat = testResource(rdfPath.toAbsolutePath().toString(), ww, 4, "model");
				} catch (Exception ex) {
					ex.printStackTrace();
					summaryWeightFormat = create(rdfPath, "failed", "exception thrown during testing",
					stackTrace(ex), "test was interrupted by an exception while testing" + ww.getFramework() + " weigths");
				}
				summariesPath = summariesDir.toAbsolutePath() + File.separator
						+ rdID + File.separator + "test_summary_" + ww.getFramework() + ".yaml";
				writeSummary(summariesPath, summaryWeightFormat);
			}
			
		}
	}
	
	private static Map<String, String> create(Path rdfPath, String status, String error, 
												String tb, String details) {
		Map<String, String> summaryMap = new LinkedHashMap<String, String>();
		summaryMap.put("name", TEST_NAME);
		summaryMap.put("status", status);
		summaryMap.put("error", error);
		summaryMap.put("source_name", rdfPath.toAbsolutePath().toString());
		summaryMap.put("traceback", tb);
		summaryMap.put("details", details);
		summaryMap.put(software, version);;
		return summaryMap;
	}
	
	private static void writeSummaries(String summariesPath, List<Object> summaries) throws IOException {
		Path path = Paths.get(summariesPath).getParent();
		if (path != null && !Files.exists(path))
            Files.createDirectories(path);
		YAMLUtils.writeYamlFile(summariesPath, summaries);
	}
	
	private static void writeSummary(String summariesPath, Map<String, String> summary) throws IOException {
		List<Object> summaries = new ArrayList<Object>();
		summaries.add(summary);
		Path path = Paths.get(summariesPath).getParent();
		if (path != null && !Files.exists(path))
            Files.createDirectories(path);
		YAMLUtils.writeYamlFile(summariesPath, summaries);
	}
	
	private static Map<String, String>  testResource(String rdf, WeightFormat weightFormat, int decimal, String expectedType) {
		ModelDescriptor rd = null;
		try {
			rd = ModelDescriptor.readFromLocalFile(rdf, false);
		} catch (ModelSpecsException e) {
			Map<String, String> summary = create(Paths.get(rdf),
					"failed", "Unable to parse specs from rdf.yaml file",  stackTrace(e), 
					software + "_" + version + " is unable to read the specs from the rdf.yaml file. Spec version"
							+ " might not be compatible with the software version.");
			return summary;
		}
		
		Map<String, String> test1 = testExpectedResourceType(rd, expectedType);
		if (test1.get("status").equals("failed")) return test1;
		
		Map<String, String> test2 = testModelDownload(rd);
		if (test2.get("status").equals("failed")) return test2;
		
		return testModelInference(rd, weightFormat, decimal);
	}
	
	private static Map<String, String> testExpectedResourceType(ModelDescriptor rd,  String type) {
		boolean yes = rd.getType().equals(type);
		Path path = Paths.get(rd.getModelPath() + File.separator + Constants.RDF_FNAME);
		return create(path, yes ? "passed" : "failed", 
				yes ? null : "expected type was " + type + " but found " + rd.getType(), null, null);
	}
	
	private static Map<String, String> testModelDownload(ModelDescriptor rd) {
		Path path = Paths.get(rd.getModelPath() + File.separator + Constants.RDF_FNAME);
		String error = null;
		if (downloadedModelsCorrectly.keySet().contains(rd.getName())) {
			rd.addModelPath(Paths.get(downloadedModelsCorrectly.get(rd.getName())));
		} else if (downloadedModelsIncorrectly.keySet().contains(rd.getName())) {
			error = downloadedModelsIncorrectly.get(rd.getName());
		} else {
			error = downloadModel(rd);
		}
		String details = null;
		if (error != null && error.contains("The provided name does not correspond to"))
			details = "Model does not exist on the Bioimage.io repo";
		else if (error != null)
			details = error;
		
		return create(path, error == null ? "passed" : "failed", 
				error == null ? null : software + " unable to download model",
				error, details);
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
		inferTest.put(software, version);
		if (rd.getModelPath() == null) {
			return create(null, "failed", 
					"model was not correctly downloaded", null, null);
		}
		if (software.equals(Tags.DEEPIMAGEJ) && rd.getInputTensors().size() != 1) {
			return create(null, "failed", 
					software + " only supports models with 1 (one) input", null, software + " only supports models "
							+ "with 1 input and this model has " + rd.getInputTensors().size());
		} else if (rd.getInputTensors().size() != rd.getTestInputs().size()) {
			return create(null, "failed", 
					"the number of test inputs should be the same as the number of model inputs", null, 
					"the number of test inputs should be the same as the number of model inputs,"
							+ rd.getInputTensors().size() + " vs " + rd.getTestInputs().size());
		} else if (rd.getOutputTensors().size() != rd.getTestOutputs().size()) {
			return create(null, "failed", 
					"the number of test outputs should be the same as the number of model outputs", null, 
					"the number of test outputs should be the same as the number of model outputs,"
							+ rd.getInputTensors().size() + " vs " + rd.getTestInputs().size());
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
					return failInferenceTest(rd.getName(), "pre-processing transformation not supported by " + software + ": " + transform.getName(), stackTrace(e));
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
			return failInferenceTest(rd.getName(), "selected weights not supported by " + software + ": " + ww.getFramework(), stackTrace(e));
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
					return failInferenceTest(rd.getName(), "post-processing transformation not supported by " + software + ": " + transform.getName(), stackTrace(e));
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
						+ "the max difference is " + diff +", bigger than max alllowed " + Math.pow(10, -decimal), null);
			maxDif.add(computeMaxDiff(rai));
		}
		
		return create(null, "passed", null, null, null);
	}
	
	private static Map<String, String> failInferenceTest(String sourceName, String error, String tb) {
		return create(Paths.get(sourceName), "failed", error, tb, tb);
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
