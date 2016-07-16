"""
Check environment and probe classes.
"""
import os
from .. import libprobe as library
from ...routes import library as libroutes

def test_executables(test):
	with libroutes.File.temporary() as td:
		b = td / 'bin'
		x = b / 'x'
		x.init('file')

		p = os.environ['PATH']
		os.environ['PATH'] = str(b)

		# One found
		found, unavail = library.executables(['test', 'cat', 'x'])
		test/unavail == set(['test', 'cat'])
		test/found == {'x': x}

		# None found
		found, unavail = library.executables(['y'])
		test/unavail == set(['y'])
		test/found == {}

		# None queried
		found, unavail = library.executables([])
		test/unavail == set([])
		test/found == {}

if __name__ == '__main__':
	from .. import libtest; import sys
	libtest.execute(sys.modules[__name__])
