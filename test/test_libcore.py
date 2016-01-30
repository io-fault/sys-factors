from .. import libcore

def test_dumping(test):
	test.explicit()
	with test/None.__class__ as exc, libcore.dumping() as none:
		import os
		os.abort()

if __name__ == '__main__':
	import sys; from .. import libtest
	libtest.execute(sys.modules[__name__])
