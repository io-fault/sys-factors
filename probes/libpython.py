"""
Python extension environment probe module.

libpython provides the necessary compile time and link time parameters for building a Python
extension module. Enables special cases for Python extension modules for relocatable targets.
(python:string)`'system.extension'` factors that import this probe will be identified as
Python extensions.
"""
__factor_type__ = 'system.probe'

import sys
import sysconfig

from .. import libprobe

# Marker used by libconstruct to identify that
# it is an extension module for *this* Python.
context_extension_probe = True

python_version_string = '.'.join(map(str, sys.version_info[:2]))
python_abi_flags = sys.abiflags

python_library_suffix = python_version_string + python_abi_flags
python_library = 'python' + python_library_suffix

python_include_directory = sysconfig.get_config_var('INCLUDEPY')
python_library_directory = sysconfig.get_config_var('LIBDIR')

report_dictionary = {
	'system': {
		'library.set': (python_library,),
		'library.directories': (python_library_directory,),
		'include.directories': (python_include_directory,),
	}
}

def deploy(*args):
	global report_dictionary
	return report_dictionary
