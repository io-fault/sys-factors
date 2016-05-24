"""
Update a project's factors and perform its tests.
"""
import sys
import functools
from . import prepare
from . import test

def main(*args):
	return
	prepcmd = '.'.join((__package__, 'prepare'))
	testcmd = '.'.join((__package__, 'test'))

if __name__ == '__main__':
	import sys
	from ...system import libcore
	from ...system import library as libsys

	with libcore.constraint(None):
		libsys.control(functools.partial(main, *sys.argv[1:]))
