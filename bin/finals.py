"""
Run the package's tests as quickly as possible only emitting aggregate data,
and writing a detailed report.

Finals runs all tests.
"""
from .. import libloader as cxnlib
from .. import libtest

class Test(libtest.Test):
	def fork(self, *args):
		super().fork(*args, limit = 6)

def main(package):
	# promote to test, but iff the role was unchanged.
	# in cases where finals are ran, this will be 'factor'.
	if cxnlib.role is None:
		cxnlib.role = 'factor'
	libtest.execute(package, (), (contextlib.ExitStack, contextlib.ExitStack), Test = Test)

if __name__ == '__main__':
	import sys
	package, = sys.argv[1:]
	main(package)
