"""
"""
from .. import library
from .. import test as testpkg
from ...routes import library as libroutes

if __name__ == '__main__':
	from .. import libtest; import sys
	libtest.execute(sys.modules[__name__])
