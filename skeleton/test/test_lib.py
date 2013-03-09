from .. import lib

def test_feature(test):
	test/'foo' == lib.bar()

if __name__ == '__main__':
	from dev import libtest; libtest.execmodule()
