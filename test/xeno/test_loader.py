import importlib

# XXX: pain when dealing with other installed variants
from .. import loader
loader.install()

def test_good(test):
	from . import good
	test/good.return_true() == True
	test/good.__loader__.probename == __package__ + '.' + '.'.join(('c', 'good'))
	test/good.__loader__.probe_module == None
	# check the class bits
	test/good.Kind / type
	test/good.Kind.__name__ == 'Kind'
	test/repr(good.Kind) == "<class '{path}.{typname}'>".format(path=good.__name__, typname='Kind')
	# test the init doc parameters
	test/good.__doc__.strip() == 'good docs'

def test_bad(test):
	with test/ImportError:
		importlib.import_module(".bad", __package__)

def test_objcgood(test):
	from . import objc_good
	test/objc_good.foobarhash / int

def test_trace(test):
	'check the loader import tracing'
	endpoint = []
	class Records(object):
		def append(self, x):
			endpoint.append(x)
	r = Records()
	append = r.append
	stored = set(loader.CLoader.traceset)
	with loader.CLoader.tracing(append):
		test/loader.CLoader.traceset == stored.union({append})
	test/loader.CLoader.traceset == stored

	# now, actually run an import with a trace
	with loader.CLoader.tracing(append):
		from . import traced
	test/traced.__loader__ == endpoint[0]

def test_probing(test):
	from . import probed
	# validate that the render_stack() define made it.
	# well, it wouldn't compile otherwise, but check
	# the value for posterity.
	test/probed.return_foo() == 'bar'

	pmod = probed.__loader__.probe_module
	test/pmod != None
	test/pmod.data == 'expected'

if __name__ == '__main__':
	import sys; from ...development import libtest
	libtest.execute(sys.modules['__main__'])
