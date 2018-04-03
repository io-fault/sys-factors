"""
# Options parser implementation for compilation options common to compiler collections and link editors.
# Used by command line tools to construct Context reference parameters local to the command.
"""

def add_include(root, factors, libdir, param):
	factors['source']['library'][param] = {None}
	return libdir

def add_library(root, factors, libdir, param):
	factors['system']['library'][libdir].add(param)
	return libdir

def add_libdir(root, factors, libdir, param):
	factors['system']['library'][param] = set()
	return param

def add_source_parameter(root, factors, libdir, param):
	k, v = param.split('=')
	root['parameters'][k] = v
	return libdir

def add_source_parameter_void(root, factors, libdir, param):
	root['parameters'][param] = None
	return libdir

def note_executable(root, factors, libdir, param):
	root['executable'] = param
	return libdir

handlers = {
	'-X': note_executable,
	'-I': add_include,
	'-l': add_library,
	'-L': add_libdir,
	'-D': add_source_parameter,
	'-U': add_source_parameter_void,
}

def parse(arguments):
	"""
	# Parse the given arguments into a dictionary suitable for serialization into
	# a &..cc.Context parameters directory and use by &..cc.Parameters.
	"""
	libdir = None

	factors = {
		'source': {
			'library': {}
		},
		'system': {
			'library': {}
		},
	}

	root = {
		# System factors used by mechanisms to support transformation and integration.
		'factors': factors,
		# Source parameters used by transformations.
		'parameters': {},
	}

	for x in arguments:
		flag = x[:2]
		op = handlers[flag]
		libdir = op(root, factors, libdir, x[2:])

	for x in ('source', 'system'):
		if not factors[x]['library']:
			del factors[x]['library']
			if not factors[x]:
				del factors[x]

	if not root['parameters']:
		del root['parameters']

	return root
