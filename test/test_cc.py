"""
# Construction Context tests.
"""
from fault.system import files
from fault.system import python

from .. import cc as module

def test_Factor(test):
	"""
	# Check the Construction Factor features.
	"""
	f = module.Factor.from_fullname(__name__)
	test.isinstance(f.module, types.ModuleType)
	test.isinstance(f.route, python.Import)
	test.isinstance(f.module_file, files.Path)

	# Check cache directory.
	pkgdir = os.path.dirname(__file__)
	pkgcache = os.path.join(pkgdir, '__pycache__')
	test/str(f.cache_directory) == pkgcache

	# Defaults.
	test/f.domain == 'python'
	test/f.type == 'library'
	test/str(f.source_directory) == str(pkgdir)

	fpir = os.path.join(pkgcache, module.Factor.default_fpi_name)
	test/str(f.fpi_root) == str(fpir)

def test_updated(test):
	tr = test.exits.enter_context(files.Path.temporary())

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
