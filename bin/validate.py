"""
Validate a project as functioning by performing its tests against the `optimal` role.
For Python extensions located within a project, the prepared, &.bin.prepare, extension
modules are used.
"""
import sys
import functools

from ...system import library as libsys
from ...system import libcore
from . import test

if __name__ == '__main__':
	command, package, *modules = sys.argv
	with libcore.constraint(None):
		libsys.control(functools.partial(test.main, package, modules, role=None))
