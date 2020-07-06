"""
# Check environment and probe classes.
"""
import os
from .. import query as module

from fault.system import files

def test_executables(test):
	with files.Path.temporary() as td:
		b = td / 'bin'
		x = b / 'x'
		x.fs_init()

		p = os.environ['PATH']
		os.environ['PATH'] = str(b)

		# One found
		found, unavail = module.executables(['test', 'cat', 'x'])
		test/unavail == set(['test', 'cat'])
		test/found == {'x': x}

		# None found
		found, unavail = module.executables(['y'])
		test/unavail == set(['y'])
		test/found == {}

		# None queried
		found, unavail = module.executables([])
		test/unavail == set([])
		test/found == {}

if __name__ == '__main__':
	from .. import libtest; import sys
	libtest.execute(sys.modules[__name__])
