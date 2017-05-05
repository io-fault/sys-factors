"""
# Python extension environment probe module.

# libpython provides the necessary imaginary factors for building an extension depending on Python.
# Enables special cases for Python extension modules for relocatable targets; this is only
# used given that the corresponding includes are properly used.
"""
__factor_domain__ = 'system'
__factor_type__ = 'probe'

import sys
import sysconfig

from .. import library as libdev
from ...system import libfactor

# Marker used by libconstruct to identify that
# it is an extension module for *this* Python.
context_extension_probe = True
reflective = True

python_version_string = '.'.join(map(str, sys.version_info[:2]))
python_abi_flags = sys.abiflags
python_triplet = \
	sys.implementation.name + \
	'-' + python_version_string.replace('.', '') + python_abi_flags + \
	'-' + sys.platform

python_library_suffix = python_version_string + python_abi_flags
python_library = 'python' + python_library_suffix

python_include_directory = sysconfig.get_config_var('INCLUDEPY')
python_library_directory = sysconfig.get_config_var('LIBDIR')

ipython = libdev.iFactor(
	domain = 'source',
	type = 'library',
	integral = python_include_directory,
	name = 'python-includes',
)

lpython = libdev.iFactor(
	domain = 'system',
	type = 'library',
	integral = python_library_directory,
	name = python_library,
)

def defines(module_fullname, target_fullname):
	"""
	# Generate a set of defines for the construction of Python extension modules
	# located inside a `extensions` package.

	# The distinction from &factor_defines is necessary as there are additional
	# defines to manage the actual target. The factor addressing is maintained
	# for the `'FACTOR_'` prefixed defines, but `'MODULE_'` specifies the destination
	# so that the &.include/fault/python/module.INIT macro can construct the appropriate
	# entry point name, and &.include/fault/python/environ.QPATH can generate
	# proper paths for type names.
	"""

	mp = module_fullname.rfind('.')
	tp = target_fullname.rfind('.')

	return [
		('MODULE_QNAME', target_fullname),
		('MODULE_PACKAGE', target_fullname[:tp]),
	] + libdev.initial_factor_defines(module_fullname)

def report(probe, context, mechanism, factor):
	srcparams = []
	if factor.type == 'extension':
		fm_name = factor.module.__name__
		ean = libfactor.extension_access_name(fm_name)
		srcparams.extend(defines(fm_name, ean))

	build_params = {'python_implementation': python_triplet}
	return build_params, srcparams, (ipython, lpython)
