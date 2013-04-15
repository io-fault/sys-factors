from .. import libcore

def test_dumping(test):
	with test/None.__class__ as exc, libcore.dumping() as none:
		pass
