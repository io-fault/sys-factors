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
from ..routes import library as libroutes

selections = None

_factor_role_patterns = None
_factor_roles = None # exact matches

def select(module, role, context=None):
	"""
	Designate that the given role should be used for the identified &package and its content.

	&select should only be used during development or development related operations. Notably,
	selecting the role for a given package during the testing of a project.

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

def role(module, role='optimal', context=None):
	"""
	Get the configured role for the given module path.
	"""
	global _factor_roles, _factor_role_patterns

	path = str(module)

	if _factor_roles is None:
		return role

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
	return libroutes.File.from_absolute(module.__file__).container / '__pycache__' / context / role / subject

def extension_access_name(name:str):
	"""
	The name, Python module path, that the extension module will be available at.

	Python extension module targets that are to be mounted to canonical full names
	are placed in packages named (python:identifier)`extensions`. In order to resolve
	the full name, the first `'.extensions.'` substring is replaced with a single `'.'`.

	For instance, `'project.extensions.capi_module'` will become `'project.capi_module'`.
	"""
	return '.'.join(name.split('.extensions.', 1))

def package_directory(module:libroutes.Import):
	return module.file().container

def sources(factor:libroutes.Import, dirname='src'):
	"""
	Return the &libroutes.File instance to the set of sources.
	"""
	return package_directory(factor) / dirname

def work(module:libroutes.Import, context:str, role:str):
	"""
	Return the work directory of the factor &module for the given &context and &role.
	"""
	path = package_directory(module) / context / role
	return libroutes.File(None, path.absolute)

def composite(factor:libroutes.Import):
	"""
	Whether the given &factor reference is a composite.
	"""
	global sources
	if not factor.is_container():
		return False
	if factor.module().__dict__.get('__factor_type__') is None:
		return False
	if not sources(factor).exists():
		return False

	return True

def probe(module:types.ModuleType):
	return module.__factor_type__ == 'system.probe'

def reduction(composite:libroutes.Import, context=None, role=None):
	"""
	The reduction of the &composite.

	The file is relative to the Python cache directory of the package module
	identifying itself as a system module: (fs-path)`{context}/{role}/factor`.
	"""
	return composite.file().container / '__pycache__' / context / role / 'factor'

def dependencies(factor:types.ModuleType):
	"""
	Collect and yield a sequence of dependencies identified by
	the dependent's presence in the module's globals.

	This works on the factor's module object as the imports performed
	by the module body make up the analyzed data.
	"""
	ModuleType = types.ModuleType

	for k, v in factor.__dict__.items():
		if isinstance(v, ModuleType) and getattr(v, '__factor_type__', None) is not None:
			yield v

def python_extension(module, probe_id='.'.join((__package__, 'probes', 'libpython'))):
	for x in module.__dict__.values():
		if isinstance(x, types.ModuleType) and x.__name__ == probe_id:
			return True
	return False
