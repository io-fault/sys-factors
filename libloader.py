"""
Compilation and linkage basics.
"""
import imp

if hasattr(imp, 'cache_from_source'):
	def cache_path(path):
		"""
		Given a module path, retrieve the basename of the bytecode file.
		"""
		return imp.cache_from_source(path)[:-len('.pyc')]
else:
	def cache_path(path):
		return path[:path.rfind('.py.')]

# Override all suffixes
import importlib.machinery

# Suffixes used to identify modules.
module_suffixes = set(importlib.machinery.all_suffixes() + [
	'.py.c', '.py.cxx', '.py.m', '.py.hs'
])

from .abstract import ToolError

#: Default Role used by the loader.
#: The loader will use ``'debug' if __debug__`` when nothing is specified here.
role = None

#: Target DLL Roles for compilation.
known_roles = set([
	'test',
	'debug',
	'profile',
	'coverage',
	'factor',
])

role_options = []
