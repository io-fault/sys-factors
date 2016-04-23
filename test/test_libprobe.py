"""
Check environment and probe classes.
"""
from .. import libprobe as library

def test_executables(test):
	return
	found, unavail = p.executables(['test', 'cat', 'cc', 'clang', 'xxxx--yy..no_such_exe'])
	test/unavail == set(['xxxx--yy..no_such_exe'])

if __name__ == '__main__':
	from .. import libtest; import sys
	libtest.execute(sys.modules[__name__])
