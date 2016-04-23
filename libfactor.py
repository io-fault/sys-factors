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

import platform
platform = platform.system().lower() + '.' + platform.machine().lower()
del sys.modules['platform']

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

def cache_directory(module, role, subject, platform=platform):
	# Get a route to a directory in __pycache__.
	return module.factor.route.cache() / subject / platform / role

class ProbeModule(libdev.Sources):
	"""
	Module class representing a probe consisting of a series of sensors that provide
	reports used to compile and link depending targets. Probe modules provide structure
	for pre-compile time checks.

	Probes are packages like most factors and the sources directory is not directly compiled,
	but referenced by the module body itself as resources used to define or support sensors.
	"""

	@property
	def system_object_type(self):
		return None

	def reports(self, role=None):
		"""
		Return the route to the probe's report.
		"""
		return cache_directory(self, role, 'reports')

	def record(self, report, role=None):
		"""
		Record the report for subsequent runs.
		"""
		rf = self.reports(role)
		import pickle
		pickle.dump(data, str(rf))

	def compilation_parameters(self, role, language):
		import sys, os.path
		exe = sys.executable

		return {
			'includes': [],
			'system.include.directories': [
				self.python_include_directory
			]
		}

	def link_parameters(self, role, type):
		import sys, os.path
		exe = sys.executable

		return {
			'system.libraries': self.libraries,
			'system.library.directories': self.library_directories,
		}

class HeadersModule(libdev.Sources):
	"""
	A collections of headers referenced by a system object.

	Headers factors are system object independent collections of resources
	that are meant to be installed into (fs-directory)`include` directories.

	When imported by &SystemModule packages, they are added to the preprocessor include
	directories that the compiler will use.
	"""

class SystemModule(libdev.Sources):
	"""
	Module class representing a system object: executable, shared library, static library, and
	archive files.
	"""

	def dependencies(self):
		"""
		Collect and yield a sequence of dependencies identified by
		the dependent's presence in the module's globals.

		&SystemModule, &ProbeModule, and &IncludeModule can be dependencies.
		"""
		types = (SystemModule, ProbeModule)

		for k, v in self.__dict__.items():
			if isinstance(v, types):
				yield v

	def output(self, role=None):
		"""
		The target file of the construction.
		The file is relative to the Python cache directory of the package module
		identifying itself as a system module: (fs-path)`factor/{platform}/{role}`.
		"""
		return cache_directory(self, role, 'factor')

	def libraries(self, role=None):
		"""
		The route to the libraries that this target depends upon.
		Only used for linking against other targets.
		"""
		return cache_directory(self, role, 'lib')

	@property
	def includes(self):
		"""
		Public includes used by cofactors or unknown dependencies.
		"""
		return self.sources.container / 'include'

	def objects(self, role=None):
		"""
		The route to the objects directory inside the cache.
		"""
		return cache_directory(self, role, 'objects')

	def imported(self, role=None):
		"""
		Executed by &load when any necessary construction is complete and the module
		has finished importing.
		"""
		pass

	def compilation_parameters(self, role, language):
		return {}

class Extension(SystemModule):
	"""
	A Python extension module constructed from a set of sources.
	An &Extension is a &SystemModule whose target is a runtime-loaded library.
	"""

	def imported(self, role=None):
		global imp
		mod = imp.internal_load_dynamic(module.__name__, self.output(role))

		# rewrite the package module contents with that of the extension module
		for k, v in mod.__dict__.items():
			if k.startswith('__'):
				continue
			module.__dict__[k] = v
		module.__dict__['__shared_object__'] = mod
		mod.__path__ = module.__path__ = None
		mod.__type__ = 'extension'
		module__origin__ = mod.__origin__ = module.__file__

class ResourceModule(types.ModuleType):
	"""
	"""

def find_parameters(module_dict, sys_types=(SystemModule, ResourceModule, ProbeModule)):
	"""
	Used by &load to identify modules that are to be used as parameters to the construction
	process.
	"""

	return [
		(name, obj) for name, obj in module_dict.items()
		if isinstance(obj, type) and issubclass(obj, sys_types)
	]

def probe(module):
	# Probe don't inherit based on imports like system objects do.
	import pickle
	route = module.reports(role(module))

	if route.exists():
		with open(str(route)) as f:
			report = pickle.load(f)
			module.__dict__.update(report)

def load(typ):
	"""
	Load a development factor performing a build when needed.
	"""

	# package modules defining a target don't have to define themselves.
	ctx = core.outerlocals()
	module = sys.modules[ctx['__name__']]
	if typ == 'probe':
		module.__class__ = ProbeModule
		module._init()
		return probe(module)

	module.__class__ = SystemModule
	module._init()
	module.system_object_type = typ

	build = None
	module_role = role(module.__name__)
	output = module.output(module_role) # XXX: select factor as needed

	if output.exists():
		srcdir = module.sources
		for x in srcdir.since(output.last_modified()):
			build = True
			break
		else:
			build = False
	else:
		build = True

	try:
		if build:
			from . import libconstruct
			libconstruct.construct(module, (module_role,))
		else:
			module.imported()
	except Exception:
		raise ImportError(module.__name__)

	module.__dict__.pop('libfactor', None)
