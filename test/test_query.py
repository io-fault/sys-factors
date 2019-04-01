"""
# Check environment and probe classes.
"""
import os
from .. import probe as module

from fault.routes import library as libroutes
from fault.kernel import library as libkernel

def test_executables(test):
	with libroutes.File.temporary() as td:
		b = td / 'bin'
		x = b / 'x'
		x.init('file')

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

def test_runtime(test):
	test.fail("depends on libkernel.parallel()")
	src = "#include <stdio.h>\nint main(int ac, char *av[]) {printf(\"test\\n\");return(0);}"
	test/b'test\n' == module.runtime([], 'c', src, libraries=['c'])

	syntax_error = "...int i = $\n"
	test/None == module.runtime([], 'c', syntax_error)

def test_includes(test):
	test.fail("depends on libkernel.parallel()")
	test/module.includes([], "c", ("fault/libc.h",)) == True
	test/module.includes([], "c", ("fault/nosuchfile.h",)) == False

if __name__ == '__main__':
	from .. import libtest; import sys
	libtest.execute(sys.modules[__name__])
