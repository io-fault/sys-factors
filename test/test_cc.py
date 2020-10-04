"""
# Construction Context tests.
"""
from fault.system import files
from .. import cc as module

def test_updated(test):
	tr = test.exits.enter_context(files.Path.fs_tmpdir())

	of = tr / 'obj'
	sf = tr / 'src'
	test/module.updated([of], [sf], None) == False

	# object older than source
	of.fs_init()
	sf.fs_init()
	of.set_last_modified(sf.get_last_modified().rollback(second=10))
	test/module.updated([of], [sf], None) == False

	of.fs_void()
	of.fs_init()
	of.set_last_modified(sf.get_last_modified().elapse(second=10))
	test/module.updated([of], [sf], None) == True

if __name__ == '__main__':
	from fault.test import library as libtest; import sys
	libtest.execute(sys.modules[__name__])
