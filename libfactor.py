"""
Factor support for Python extensions, archive files, shared objects, and executables.

[ Properties ]

/selections
	A mapping providing the selected role to use for the factor module.

/import_role
	The default role to import modules with.

[ Environment ]

/FAULT_CONSTRUCT_ROLE
	Role to construct targets with.
"""
import sys
import imp
import types

from . import core
from . import library as libdev
from ..computation import libmatch

selections = None

_factor_role_patterns = None
_factor_roles = None # exact matches

def select(module, role):
	"""
	Designate that the given role should be used for the identified &package and its content.

	&select should only be used during development or development related operations. Notably,
	selecting the role for a given package during the testing or surveyence of a project.

	It can also be used for one-off debugging purposes where a particular target is of interest.
	"""
	global _factor_roles, _factor_role_patterns
	if _factor_roles is None:
		_factor_roles = {}

	if module.endswith('.'):
		path = tuple(module.split('.')[:-1])

		if _factor_role_patterns is None:
			_factor_role_patterns = libmatch.SubsequenceScan([path])
		else:
			x = list(_factor_role_patterns.sequences)
			x.append(path)
			_factor_role_patterns = libmatch.SubsequenceScan(x)

		_factor_roles[module[:-1]] = role
	else:
		# exact
		_factor_roles[module] = role

def role(module, default_role='factor'):
	"""
	Get the configured role for the given module path.
	"""
	global _factor_roles, _factor_role_patterns

	path = str(module)

	if _factor_roles is None:
		return default_role

	if path in _factor_roles:
		return _factor_roles[path]

	if _factor_role_patterns is not None:
		# check for pattern
		path = _factor_role_patterns.get(tuple(path.split('.')))
		return _factor_roles['.'.join(path)]

	return default_role

def cache_directory(module, context, role, subject):
	"""
	Get the relevant context-role directory inside the associated
	(fs-directory)`__pycache__` directory.
	"""
	# Get a route to a directory in __pycache__.
	return module.sources.container / '__pycache__' / context / role / subject

class ProbeModule(libdev.Sources):
	"""
	Module class representing a probe consisting of a series of sensors that provide
	reports used to compile and link depending targets. Probe modules provide structure
	for pre-compile time checks.

	Probes are packages like most factors and the sources directory is not directly compiled,
	but referenced by the module body itself as resources used to define or support sensors.
	"""

	@property
	def parameters(self):
		"""
		Attribute set by probe modules declaring parameters accepted by the probe.
		Probe parameters allow defaults to be overridden in a well-defined manner.
		"""
		return None

	def cache(self, context=None, role=None):
		"""
		Return the route to the probe's recorded report.
		"""
		return cache_directory(self, context, role, 'report')
	output=cache

	def record(self, report, context=None, role=None):
		"""
		Record the report for subsequent runs.
		"""
		rf = self.cache(context, role)
		rf.init('file')
		import pickle
		pickle.dump(data, str(rf))

	def retrieve(self, report, context=None, role=None):
		"""
		Retrieve the stored data collected by the sensor.
		"""
		import pickle
		return pickle.load(str(self.cache(context, role)))

	@staticmethod
	def report(probe, context):
		"""
		Return the report data of the probe for the given &context.

		This method is called whenever a dependency accesses the report for supporting
		the construction of a target. Probe modules can override this method in
		order to provide parameter sets that depend on the target that is requesting them.
		"""
		return {}

	@staticmethod
	def deploy(probe, context):
		"""
		Cause the probe to activate its sensors to collect information
		from the system that will be later fetched with &report.

		Probe modules usually define this as a function in the module body.
		"""
		pass

class IncludesModule(libdev.Sources):
	"""
	A collections of headers referenced by a system object.

	Headers factors are system object independent collections of resources
	that are meant to be installed into (fs-directory)`include` directories.

	When imported by &SystemModule packages, they are added to the preprocessor include
	directories that the compiler will use.
	"""

	def output(self, context=None, role=None):
		return None

	def objects(self, context=None, role=None):
		return None

class SystemModule(libdev.Sources):
	"""
	Module class representing a system object: executable, shared library, static library, and
	archive files.
	"""
	constructed = True

	def extension_name(self):
		"""
		The name that the extension module is bound to.
		Only used when constructing a Python extension module.
		"""
		return ''.join(self.__name__.split('.extensions'))

	def output(self, context=None, role=None):
		"""
		The target file of the construction.
		The file is relative to the Python cache directory of the package module
		identifying itself as a system module: (fs-path)`factor/{platform}/{role}`.
		"""
		return cache_directory(self, context, role, 'factor')

	def libraries(self, context=None, role=None):
		"""
		The route to the libraries that this target depends upon.
		Only used for linking against other targets.
		"""
		return cache_directory(self, context, role, 'lib')

	@property
	def includes(self):
		"""
		Public includes used by cofactors or unknown dependencies.
		"""
		return self.sources.container / 'include'

	def objects(self, context=None, role=None):
		"""
		The route to the objects directory inside the cache.
		"""
		return cache_directory(self, context, role, 'objects')

	def compilation_parameters(self, role, language):
		return {}

merge_operations = {
	set: set.update,
	dict: dict.update,
	list: list.extend,
	int: int.__add__,
	tuple: (lambda x, y: x + tuple(y)),
	str: (lambda x, y: y), # override strings
	tuple: (lambda x, y: y), # override tuple sequences
	None.__class__: (lambda x, y: y),
}

def merge(parameters, source, operations = merge_operations):
	"""
	Merge the given &source into &self applying merge operations
	defined for keys or the classes of the destinations' keys.
	"""
	for key in source:
		if key in parameters:
			if key in operations:
				# merge operation overloaded by key
				mokey = key
			else:
				# merge parameters by class
				mokey = parameters[key].__class__

			merge_op = operations[mokey]

			# DEFECT: The manipulation methods often return None.
			r = merge_op(parameters[key], source[key])
			if r is not parameters[key] and r is not None:
				parameters[key] = r
		else:
			parameters[key] = source[key]

def load(typ):
	"""
	Load a development factor performing a build when needed.
	"""
	global ProbeModule, IncludesModule, SystemModule

	# package modules defining a target don't have to define themselves.
	ctx = core.outerlocals()
	module = sys.modules[ctx['__name__']]

	if typ == 'system.probe':
		module.__class__ = ProbeModule
		module.system_object_type = 'probe'
	elif typ == 'system.includes':
		module.__class__ = IncludesModule
		module.system_object_type = 'includes'
	else:
		module.__class__ = SystemModule
		if typ == 'system.extension':
			for x in module.__dict__.values():
				if isinstance(x, libdev.Sources):
					# context_extension_probe is a name set in
					# the libpython probe in order to identify a
					# given system extension as being intended for
					# the Python that is currently running the software.
					if getattr(x, 'context_extension_probe', None):
						module.execution_context_extension = True
						break
			else:
				module.execution_context_extension = False
		module.system_object_type = typ[typ.find('.')+1:]

	module._init()
