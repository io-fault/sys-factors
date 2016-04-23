"""
Python eXtension Environment probe module.

libpxe provides the necessary compile time and link time parameters for building a Python
extension module.

Enables special cases for Python extension modules for relocatable targets.
(python:string)`'system.extension'` factors that import this probe will be identified as
Python extensions.
"""
import sys
import sysconfig

from . import libfactor
from . import libprobe

python_version_string = '.'.join(map(str, sys.version_info[:2]))
python_abi_flags = sys.abiflags

python_library_suffix = python_version_string + python_abi_flags

python_library = 'python' + python_library_suffix

python_include_directory = sysconfig.get_config_var('INCLUDEPY')
python_library_directory = sysconfig.get_config_var('LIBDIR')

libraries = [
	python_library
]

library_directories = [
	python_library_directory
]

if not libfactor.load('probe'):
	# Probe does not have cache for the combination.
	pass
