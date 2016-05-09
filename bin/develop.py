"""
Update a project's factors and perform its tests.
"""
import functools
from . import prepare
from . import test

def main(*args):
	global prepare, test
	prepare.main(*args, role='test', mount_extensions=False)
	for pkg in args:
		test.main(pkg, ())

if __name__ == '__main__':
	import sys
	from ...system import libcore
	from ...system import library as libsys

	with libcore.constraint(None):
		libsys.control(functools.partial(main, *sys.argv[1:]))
