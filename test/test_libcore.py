from .. import libcore

def test_dumping(test):
	with libcore.dumping():
		pass

if __name__ == '__main__':
	import dev.libtest; dev.libtest.execmodule()
