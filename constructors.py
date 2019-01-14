"""
# Builtin command constructors.
"""

def disabled(*args, **kw):
	"""
	# A transformation that can be assigned to a subject's mechanism
	# in order to describe it as being disabled.
	"""
	return ()

def transparent(build, adapter, o_type, output, i_type, inputs, verbose=True):
	"""
	# Create links from the input to the output; used for zero transformations.
	"""

	input, = inputs # Rely on exception from unpacking; expecting one input.
	return [None, '-f', input, output]

def void(build, adapter, o_type, output, i_type, inputs, verbose=True):
	"""
	# Command constructor executing &.bin.void with the intent of emitting
	# an error designating that the factor could not be processed.
	"""
	return [None, output] + list(inputs)

def standard_io(build, adapter, o_type, output, i_type, inputs, verbose=True):
	"""
	# Interface returning a command with no arguments.
	# Used by transformation mechanisms that operate using standard I/O.
	"""
	return [None]

def standard_out(build, adapter, o_type, output, i_type, inputs, verbose=True, root=False):
	"""
	# Takes the set of files as the initial parameters and emits
	# the processed result to standard output.
	"""

	return [None] + list(inputs)

def concatenation(build, adapter, o_type, output, i_type, inputs,
		partials, libraries,
		verbose=True,
		filepath=str,
	):
	"""
	# Create the factor by concatenating the files. Only used in cases
	# where the order of concatentation is already managed or irrelevant.

	# Requires 'execute-redirect'.
	"""
	return ['cat'] + list(inputs)

def empty(context, mechanism, factor, output, inputs,
		language=None,
		format=None,
		verbose=True,
	):
	"""
	# Create the factor by executing a command without arguments.
	# Used to create constant outputs for reduction.
	"""
	return ['empty']
