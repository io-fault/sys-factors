from ...system import corefile
from .. import backtrace as module

def test_location(test):
	"""
	# Test &.corefile's capacity to identify the location of a core image.
	"""
	test.explicit()
	with test/None.__class__ as exc, corefile.constraint(None):
		import os
		os.abort()

if __name__ == '__main__':
	import sys; from .. import libtest
	libtest.execute(sys.modules[__name__])
