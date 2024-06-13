package io.bioimage.modelrunner.ci;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Parameter;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import io.bioimage.modelrunner.bioimageio.description.TensorSpec;
import io.bioimage.modelrunner.tensor.Tensor;

import net.imglib2.RandomAccessibleInterval;
import net.imglib2.type.NativeType;
import net.imglib2.type.Type;
import net.imglib2.type.numeric.RealType;

/**
 * Class that handles the Java pre-processing transformations.
 * The transformations can be either custom designed by the developer or 
 * coming from the Bioimage.io Java library
 * and the tensors produced by them
 * 
 * @author Carlos Garcia Lopez de Haro
 *
 */
public class JavaProcessing {
	/**
	 * Transformation as specified in the rdf.yaml
	 */
	private String rdfSpec;
	/**
	 * String containing the name of the method that runs JAva pre-processing
	 */
	private String javaMethodName;
	/**
	 * String referring to the BioImage.io class that contains the specified transformations
	 */
	private String javaClassName;
	/**
	 * Class that contains the pre-processing
	 */
	private Class<?> transformationClass;
	/**
	 * Arguments used for the Java method
	 */
	private Map<String, Object> args;
	/**
	 * Name of the tensor that is going to be pre-processed
	 */
	private String tensorName;
	/**
	 * Specs of the tensor that is going to be pre-processed
	 */
	private TensorSpec tensorSpec;
	/**
	 * INDArray containing all the information of the input tensor to which this
	 * pre-processing transformation corresponds
	 */
	private Tensor tensor;
	/**
	 * Package where the BioImage.io transformations are.
	 */
	private static final String BIOIMAGEIO_TRANSFORMATIONS_PACKAGE = "io.bioimage.modelrunner.transformations.";
	/**
	 * Name of the standard method used by the BioImage.io transformations to call the 
	 * pre-processing routine
	 */
	private static String bioImageIoExecutionMethodName = "apply";
	
	/**
	 * Create pre-processing object that contains the path to a pre-processing protocol file
	 * @param javaMethod
	 * 	file that contains the Icy protocols to run pre-processing
	 * @param args
	 * 	args of the pre-processing specified in the rdf.yaml
	 * @throws ClassNotFoundException if the pre-processing transformation is not found in the classpath
	 */
	private JavaProcessing(String javaMethod, Map<String, Object> args) throws ClassNotFoundException {
		this.rdfSpec = javaMethod;
		this.args = args;
		checkMethodExists();
	}
	
	/**
	 * Create a Java pre-processing object
	 * @param methodName
	 * 	name of the Java method for pre-processing
	 * @param args
	 * 	arguments of the Java method
	* @return result of runnning Java pre-processing on the tensor
	 * @throws ClassNotFoundException if the pre-processing transformation is not found
	 */
	public static JavaProcessing definePreprocessing(String methodName, Map<String, Object> args) throws ClassNotFoundException {
		return new JavaProcessing(methodName, args);
	}
	
	/**
	 * Executes the Java pre-processing transformation specified
	 *  on the rdf.yaml on the input map with the corresponding tensor name
	 * @param tensorSpec
	 * 	specs of the tensor where pre-processing is going to be executed
	 * @param inputMap
	 * 	map containing the inputs of the model
	 * @return a Map with the results of pre-processing the input tensor containing 
	 * 	the inputs provided in the input map too.
	 * @throws IllegalArgumentException if the tensor that the pre-processing refers to is not found
	 */
	public Tensor execute(TensorSpec tensorSpec, Tensor input)
			 throws IllegalArgumentException {
		this.tensorSpec = tensorSpec;
		this.tensorName = tensorSpec.getName();
		this.tensor = input;;
		LinkedHashMap<String, Object> resultsMap = executeJavaTransformation();
		return (Tensor) resultsMap.get(tensor.getName());
	}
	
	/**
	 * Fill the args map with variables provided by the input map. 
	 * This is done to allow several pre- and post-processing that can be
	 * executed one after another
	 * @param inputsMap
	 * 	the provided map with different inputs
	 */
	private void fillArgs(Map<String, Object> inputsMap) {
		// TODO decide whether to use a key word when one of the inputs to pre
		// processing has to be given by the previous pre-processing or 
		// the arg should just be null
		for (String kk : this.args.keySet()) {
			if (this.args.get(kk) == null && inputsMap.get(kk) != null) {
				this.args.put(kk, inputsMap.get(kk));
			}
		}
	}
	
	/**
	 * Method that adds the tensor to the input dictionary as a NDArray.
	 * NDArrays are the objects used by Java pre-processings so they can
	 *  be shared among different Java softwares
	 * @param inputMap
	 * 	map of input tensors for the model
	 * @throws IllegalArgumentException if the tensor that the pre-processing refers to is not found
	 */
	private < T extends RealType< T > & NativeType< T > > void addTensorToInputs(Map<String, Object> inputMap) throws IllegalArgumentException {
		Object inputTensor = inputMap.get(this.tensorName);
		if (inputTensor == null) {
			throw new IllegalArgumentException("There should be an input tensor called '" +
					tensorName + "', but no object referring to it has been found.");
		}
		
		if (inputTensor instanceof RandomAccessibleInterval) {
			this.tensor = Tensor.build(tensorSpec.getName(), tensorSpec.getAxesOrder(), (RandomAccessibleInterval<T>) inputTensor);
		} else if (inputTensor instanceof Tensor) {
			this.tensor = ((Tensor) inputTensor);
		}
	}
	
	/**
	 * Method used to convert Strings in using snake case (snake_case) into camel
	 * case with the first letter as upper case (CamelCase)
	 * @param str
	 * 	the String to be converted
	 * @return String converted into camel case with first upper
	 */
	public static String snakeCaseToCamelCaseFirstCap(String str) {
		while(str.contains("_")) {
            str = str.replaceFirst("_[a-z]", String.valueOf(Character.toUpperCase(str.charAt(str.indexOf("_") + 1))));
        }
		str = str.substring(0, 1).toUpperCase() + str.substring(1);
		return str;
	}
	
	/**
	 * Method that checks if the pre-processing transformations specified in the 
	 * rdf,yaml exist in the classpath
	 * @throws ClassNotFoundException if the transformations are not found in the classpath
	 */
	private void checkMethodExists() throws ClassNotFoundException {
		if (rdfSpec.contains(".") && !rdfSpec.contains("::")) {
			javaClassName = rdfSpec;
			javaMethodName = bioImageIoExecutionMethodName;
			findClassInClassPath();
		} else if (rdfSpec.contains(".") && rdfSpec.contains("::")) {
			javaClassName = rdfSpec.substring(0, rdfSpec.indexOf("::"));
			javaMethodName = rdfSpec.substring(rdfSpec.indexOf("::") + 2);
			findClassInClassPath();
		} else {
			findMethodInBioImageIo();
		}
	}
	
	/**
	 * Tries to find a given class in the classpath
	 * @throws ClassNotFoundException if the class does not exist in the classpath
	 */
	private void findClassInClassPath() throws ClassNotFoundException {
		Class.forName(this.javaClassName, false, JavaProcessing.class.getClassLoader());
	}
	
	/**
	 * Find of the transformation exists in the BioImage.io Java Core
	 * @throws ClassNotFoundException if the BioImage.io transformation does not exist
	 */
	private void findMethodInBioImageIo() throws ClassNotFoundException {
		this.javaMethodName = snakeCaseToCamelCaseFirstCap(this.rdfSpec) + "Transformation";
		this.javaClassName = BIOIMAGEIO_TRANSFORMATIONS_PACKAGE + this.javaMethodName;
		findClassInClassPath();
		this.javaMethodName = bioImageIoExecutionMethodName;
	}
	
	/**
	 * Execute the transformation form the BioImage.io defined in the rdf.yaml
	 * @throws IllegalArgumentException if the transformation is not correctly defined,
	 * 	does not exist or is missing any argument
	 */
	private LinkedHashMap<String, Object> executeJavaTransformation() throws IllegalArgumentException {
		try {
			 return runJavaTransformationWithArgs();
			
		} catch (ClassNotFoundException e) {
			throw new IllegalArgumentException("Processing method '" + this.rdfSpec +"' not found"
					+ " in the BioImage.io Java Core Transformations or in the Java Classpath: "
					+ "https://github.com/bioimage-io/model-runner-java/tree/nd4j/src/main/java/org/bioimageanalysis/icy/deeplearning/transformations"
					+ ". " + System.lineSeparator() + e.getCause());
		} catch (InstantiationException e) {
			e.printStackTrace();
			throw new IllegalArgumentException("Processing method '" + this.rdfSpec +"' failed"
					+ " due to an error instantiating the class that defines the transformation ("
					+ this.javaClassName + "). Go to the following link to see valid transformations:"
					+ "https://github.com/bioimage-io/core-bioimage-io-java/tree/master/src/main/java/io/bioimage/specification/transformation"
					+ ". " + System.lineSeparator() + e.getCause());
		} catch (IllegalAccessException e) {
			e.printStackTrace();
			throw new IllegalArgumentException("Processing method '" + this.rdfSpec +"' failed"
					+ " throwing an IllegalAccessException."
					+ " Go to the following link to see valid transformations:"
					+ "https://github.com/bioimage-io/core-bioimage-io-java/tree/master/src/main/java/io/bioimage/specification/transformation"
					+ ". " + System.lineSeparator() + e.getCause());
		} catch (InvocationTargetException e) {
			e.printStackTrace();
			throw new IllegalArgumentException("Processing method '" + this.rdfSpec +"' failed"
					+ " throwing an InvocationTargetException."
					+ " Go to the following link to see valid transformations:"
					+ "https://github.com/bioimage-io/core-bioimage-io-java/tree/master/src/main/java/io/bioimage/specification/transformation"
					+ ". " + System.lineSeparator() + System.lineSeparator() + e.getCause());
		} catch (NoSuchMethodException e) {
			e.printStackTrace();
			throw new IllegalArgumentException("Processing method '" + this.rdfSpec +"' failed"
					+ " because the method needed to call the transformation (" + this.javaMethodName 
					+ ") was not found in the transformation class ("
					+ this.javaClassName + "). Go to the following link to see valid transformations:"
					+ "https://github.com/bioimage-io/core-bioimage-io-java/tree/master/src/main/java/io/bioimage/specification/transformation"
					+ ". " + System.lineSeparator() + e.getCause());
		} catch (SecurityException e) {
			e.printStackTrace();
			throw new IllegalArgumentException("Processing method '" + this.rdfSpec +"' failed"
					+ " throwing an SecurityException."
					+ " Go to the following link to see valid transformations:"
					+ "https://github.com/bioimage-io/core-bioimage-io-java/tree/master/src/main/java/io/bioimage/specification/transformation"
					+ ". " + System.lineSeparator() + e.getCause());
		}
	}
	
	/**
	 * Run the transformation from the Java transformation class
	 * @throws IllegalAccessException if the method or class cannot be accessed with reflection
	 * @throws InstantiationException if there is an error instantiating the transformation class
	 * @throws InvocationTargetException if there is any error invoking the methods
	 * @throws IllegalArgumentException if any of the arguments provided with reflection is illegal
	 * @throws SecurityException if there is any security breach
	 * @throws NoSuchMethodException if the method tried to run does not exist
	 * @throws ClassNotFoundException if the class referenced for the transformation does not exist
	 */
	private LinkedHashMap<String, Object> runJavaTransformationWithArgs() throws InstantiationException, IllegalAccessException, IllegalArgumentException, InvocationTargetException, NoSuchMethodException, SecurityException, ClassNotFoundException {
		this.transformationClass = getClass().getClassLoader().loadClass(this.javaClassName);
		Method[] publicMethods = this.transformationClass.getMethods();
		Method transformationMethod = null;
		for (Method mm : publicMethods) {
			if (mm.getName().equals(this.javaMethodName)) {
				transformationMethod = mm;
				break;
			}
		}
		if (transformationMethod == null)
			throw new IllegalArgumentException("The pre-processing transformation class does not contain"
					+ "the method '" + this.javaMethodName + "' needed to call the transformation.");
		// Check that the arguments specified in the rdf.yaml are of the corect type
		return executeMethodWithArgs(transformationMethod);
	}
	
	/**
	 * 
	 * @param mm
	 * @return
	 * @throws InstantiationException if there is any error instantiating the class
	 * @throws  if it is illegal to instantiate the class or to call the method
	 * @throws IllegalArgumentException if any of the arguments for the method is wrong
	 * @throws InvocationTargetException if the target of the method is incorrectly captured
	 * @throws SecurityException if there is any security violation
	 * @throws NoSuchMethodException if the constructor with the needed argument does not exist
	 */
	private <T extends Type<T>> LinkedHashMap<String, Object> executeMethodWithArgs(Method mm) throws InstantiationException, 
																	IllegalAccessException, 
																	IllegalArgumentException, 
																	InvocationTargetException, NoSuchMethodException, SecurityException {
		
		
		LinkedHashMap<String, Object> resultsMap = new LinkedHashMap<String, Object>();
		Object instance = createInstanceWitArgs();

		if (mm.getReturnType().equals(Void.TYPE)) {
			mm.invoke(instance, tensor);
			resultsMap.put(tensorName, tensor);
		} else {
			Object returnObject = mm.invoke(instance, tensor);
			// Depending on what the output is, do one thing or another
			if ((returnObject instanceof HashMap) || (returnObject instanceof HashMap)) {
				// If the output is a HashMap, assume the pre-processing already provides
				// the inputs map of the model
				resultsMap = (LinkedHashMap<String, Object>) returnObject;
			} else if (returnObject instanceof RandomAccessibleInterval) {
				resultsMap.put(tensorName, (RandomAccessibleInterval<T>) returnObject);
			} else if (returnObject instanceof Tensor) {
				resultsMap.put(tensorName, (Tensor) returnObject);
			} else {
				throw new IllegalArgumentException("The processing transformation '"
								+ rdfSpec + "' corresponding to tensor '" + tensorName
								+ "' outputs an object whose Type is not supported as"
								+ " an output for transformations in DeepIcy. The supported "
								+ " Types are Icy Sequences, Icy Tensors, NDArrays and Maps or"
								+ " HashMaps.");
			}
		}
		return resultsMap;
	}
	
	/**
	 * 
	 * @return
	 * @throws IllegalArgumentException
	 * @throws IllegalAccessException
	 * @throws InvocationTargetException
	 * @throws InstantiationException
	 * @throws NoSuchMethodException
	 * @throws SecurityException
	 */
	public Object createInstanceWitArgs() throws IllegalArgumentException, IllegalAccessException, InvocationTargetException, InstantiationException, NoSuchMethodException, SecurityException {
		// The instance of the pre-processing transformation should be initialized 
		// with the corresponding input tensor
		Object transformationObject = transformationClass.getConstructor().newInstance();
		for (String arg : this.args.keySet()) {
			setArg(transformationObject, arg);
		}
		return transformationObject;
	}
	
	/**
	 * Set the argument in the processing trasnformation instance
	 * @param instance
	 * 	instance of the processing trasnformation
	 * @param argName
	 * 	name of the argument
	 * @throws IllegalArgumentException if no method is found for the given argument
	 * @throws InvocationTargetExceptionif there is any error invoking the method
	 * @throws IllegalAccessException if it is illegal to access the method
	 */
	public void setArg(Object instance, String argName) throws IllegalArgumentException, IllegalAccessException, InvocationTargetException {
		String mName = getArgumentSetterName(argName);
		Method mm = checkArgType(argName, mName);
		mm.invoke(instance, args.get(argName));	
	}
	
	/**
	 * Get the setter that the Java transformation class uses to set the argument of the
	 * pre-processing. The setter has to be named as the argument but in CamelCase with the
	 * first letter in upper case and preceded by set. For example: min_distance -> setMinDistance
	 * @param argName
	 * 	the name of the argument
	 * @return the method name 
	 * @throws IllegalArgumentException if no method is found for the given argument
	 */
	public String getArgumentSetterName(String argName) throws IllegalArgumentException {
		String mName = "set" + snakeCaseToCamelCaseFirstCap(argName);
		// Check that the method exists
		Method[] methods = transformationClass.getMethods();
		for (Method mm : methods) {
			if (mm.getName().equals(mName))
				return mName;
		}
		throw new IllegalArgumentException("Setter for argument '" + argName + "' of the processing "
				+ "transformation '" + rdfSpec + "' of tensor '" + tensorName
				+ "' not found in the Java transformation class '" + this.javaClassName + "'. "
				+ "A method called '" + mName + "' should be present.");
	}
	
	/**
	 * Method that checks that the type of the arguments provided in the rdf.yaml is correct.
	 * It also returns the setter method to set the argument
	 * 
	 * @param mm
	 * 	the method that executes the pre-processing transformation
	 * @return the method used to provide the argument to the instance
	 * @throws IllegalArgumentException if any of the arguments' type is not correct
	 */
	private Method checkArgType(String argName, String mName) throws IllegalArgumentException {
		Object arg = this.args.get(argName);
		Method[] methods = this.transformationClass.getMethods();
		List<Method> possibleMethods = new ArrayList<Method>();
		for (Method mm : methods) {
			if (mm.getName().equals(mName)) 
				possibleMethods.add(mm);
		}
		if (possibleMethods.size() == 0)
			getArgumentSetterName(argName);
		for (Method mm : possibleMethods) {
			Parameter[] pps = mm.getParameters();
			if (pps.length != 1) {
				continue;
			}
			if (pps[0].getType() == Object.class)
				return mm;
		}
		throw new IllegalArgumentException("Setter '" + mName + "' should have only one input parameter with type Object.class.");
	}
}
