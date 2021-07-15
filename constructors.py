"""
# Common command constructors.
"""
import itertools

def disabled(*args, **kw):
	"""
	# A transformation that can be assigned to a subject's mechanism
	# in order to describe it as being disabled.
	"""
	return ()

def transparent(build, adapter, output, srcformat, inputs, verbose=True):
	"""
	# Create links from the input to the output; used for zero transformations.
	"""

	input, = inputs # Rely on exception from unpacking; expecting one input.
	return [None, '-sfh', input, output]

def copy(build, adapter, output, srcformat, inputs, verbose=True):
	"""
	# Create links from the input to the output; used for zero transformations.
	"""

	input, = inputs # Rely on exception from unpacking; expecting one input.
	return [None, '-f', input, output]

def clone(build, adapter, output, srcformat, inputs):
	"""
	# Duplicate the filesystem directory or file.
	"""
	return ['cp', '-R', '-f', str(inputs[0] ** 1) + '/', output]

def void(build, adapter, output, inputs, verbose=True):
	"""
	# Command constructor executing &.bin.void with the intent of emitting
	# an error designating that the factor could not be processed.
	"""
	return [None, output] + list(inputs)

def standard_io(build, adapter, output, inputs, verbose=True):
	"""
	# Interface returning a command with no arguments.
	# Used by transformation mechanisms that operate using standard I/O.
	"""
	return [None]

def standard_out(build, adapter, output, inputs, verbose=True, root=False):
	"""
	# Takes the set of files as the initial parameters and emits
	# the processed result to standard output.
	"""

	return [None] + list(inputs)

def concatenation(build, adapter, output, inputs,
		verbose=True,
		filepath=str,
	):
	"""
	# Create the factor by concatenating the files. Only used in cases
	# where the order of concatentation is already managed or irrelevant.

	# Requires 'execute-redirect'.
	"""
	return ['cat'] + list(inputs)

def empty(build, factor, output, inputs,
		language=None,
		format=None,
		verbose=True,
	):
	"""
	# Create the factor by executing a command without arguments.
	# Used to create constant outputs for reduction.
	"""
	return ['empty']

def delineation(build, adapter, output, inputs, verbose=True):
	"""
	# Standard delineation form.
	"""
	input, = inputs
	prefix = adapter.get('options', [])
	l = ['delineate'] + adapter['tool'] + prefix + [output, input]
	srcparams = ((k, v or '') for k, v in build.parameters)
	l.extend(itertools.chain.from_iterable(srcparams))
	return l

Projection = {
	'type': 'transparent',
	'interface': __name__ + '.transparent',
	'command': "/bin/ln",
}

# Single file duplication.
Duplication = {
	'type': 'clone',
	'interface': __name__ + '.transparent',
	'command': "/bin/cp",
}

# Tree duplication.
Clone = {
	'type': 'clone',
	'interface': __name__ + '.clone',
	'command': "/bin/cp",
}

def Catenation(type:str, command:str="/bin/cat"):
	"""
	# Template for integration commands that have a cat interface.
	"""
	return {
		'type': type,
		'interface': concatenation,
		'name': 'cat',
		'command': command,
	}

def Inherit(target:str):
	"""
	# Inheritance constructor.
	"""
	return {'inherit': target}
