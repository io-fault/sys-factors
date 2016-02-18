from ...system import libcore
from .. import libcore as library

def test_location(test):
	"""
	Test &.libcore's capacity to identify the location of a core image.
	"""
	test.explicit()
	with test/None.__class__ as exc, libcore.constraint(None):
		import os
		os.abort()

if __name__ == '__main__':
	import sys; from .. import libtest
	libtest.execute(sys.modules[__name__])
