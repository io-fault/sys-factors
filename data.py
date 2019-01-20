"""
# Context data utilities.

# Many parts of the Construction Context's functionality is derived from layers of
# data; a simple merge is implemented here for combining those layers.
"""
import pickle

def load(route, _load=pickle.loads):
	return _load(route.load())

def store(route, data, _dump=pickle.dumps):
	return route.store(_dump(data))

def update_named_mechanism(route:File, name:str, mechanism):
	"""
	# Given a route to a mechanism file in a construction context,
	# overwrite the file's mechanism entry with the given &mechanism.

	# [ Parameters ]
	# /route/
		# The route to the file that is to be modified.
	# /name/
		# The component in the mechanism file to replace.
	# /mechanism/
		# The dictionary to set as the mechanism's content.
	"""

	if route.exists():
		stored = load(route)
	else:
		stored = {}

	stored[name] = mechanism
	store(route, stored)

def load_named_mechanism(route:File, name:str):
	"""
	# Given a route to a mechanism file in a construction context,
	# load the file's mechanism entry.

	# [ Parameters ]
	# /route/
		# The route to the mechanisms
	"""
	return load(route)[name]

merge_operations = {
	set: set.update,
	list: list.extend,
	int: int.__add__,
	tuple: (lambda x, y: x + tuple(y)),
	str: (lambda x, y: y), # override strings
	tuple: (lambda x, y: y), # override tuple sequences
	None.__class__: (lambda x, y: y),
}

def merge(parameters, source, operations = merge_operations):
	"""
	# Merge the given &source into &parameters applying merge functions
	# defined in &operations. Dictionaries are merged using recursion.
	"""
	for key in source:
		if key in parameters:
			# merge parameters by class
			cls = parameters[key].__class__
			if cls is dict:
				merge_op = merge
			else:
				merge_op = operations[cls]

			# DEFECT: The manipulation methods often return None.
			r = merge_op(parameters[key], source[key])
			if r is not None and r is not parameters[key]:
				parameters[key] = r
		else:
			parameters[key] = source[key]
