"""
"""
from .. import library
from ...routes import library as libroutes
from .. import test as testpkg

def test_Factor(test):
	f = library.Factor.from_fullname(__package__)
	test/f.name == 'fault.development.test'
	test/f.type == 'python-module'
	test/f.sources() == [libroutes.File.from_absolute(testpkg.__file__)]

if __name__ == '__main__':
	from .. import libtest; import sys
	libtest.execute(sys.modules[__name__])
