"""
A testing library that minimizes the distance between the test runner, and
the actual tests for the purpose of keeping the execution machinary as simple as possible.

libtest provides the very basics for testing in Python. Test runners are implemented else
where as they tend to be significant pieces of code. However, a trivial :py:func:`execute`
function is provided that, when given a module, will execute the tests therein. Exceptions
are allowed to raise normally.
"""
import gc
import operator
import functools

def get_test_index(tester):
	"""
	Returns the first line number of the underlying code object.
	"""
	try:
		return int(tester.__test_order__)
	except AttributeError:
		pass

	# no explicit order index
	if '__wrapped__' in tester.__dict__:
		# Resolve the innermost function.
		visited = set((tester,))
		tester = tester.__wrapped__
		while '__wrapped__' in tester.__dict__:
			visited.add(tester)
			tester = tester.__wrapped__
			if tester in visited:
				# XXX: recursive wrappers? warn?
				return None

	try:
		return int(tester.__code__.co_firstlineno)
	except AttributeError:
		return None

def test_order(kv):
	"""
	Key function used by :py:func:`gather` that uses :py:func:`get_test_index` in
	order to elevate a test's position given that it was explicitly listed.
	"""
	return get_test_index(kv[1])

def gather(container, prefix = 'test_'):
	"""
	:returns: Ordered dictionary of attribute names associated with a `Test` instance.
	:rtype: {k : Test(v, k) for k, v in container.items()}

	Collect the objects in the container whose name starts with "test_".
	The ordered is defined by the :py:func:`get_test_index` function.
	"""
	tests = [('.'.join((container.__name__, name)), getattr(container, name)) for name in dir(container) if name.startswith(prefix)]
	tests.sort(key = test_order)
	return tests

class Defect(Exception):
	"""
	Exception raised by :py:class:`.Contention` instances to describe a Failure inducing
	defect--assertion failure.
	"""
	pass

# Exposes an assert like interface to Test objects.
class Contention(object):
	"""
	Contention is an object used by :py:class:`Test` objects to provide assertions.
	"""
	__slots__ = ('test', 'object', 'storage', 'inverse')

	def __init__(self, test, object, inverse = False):
		self.test = test
		self.object = object
		self.inverse = inverse

	# Build operator methods based on operator.
	_override = {
		'__truediv__' : ('isinstance', isinstance),
		'__sub__' : ('issubclass', issubclass),
		'__mod__' : ('is', lambda x,y: x is y)
	}
	for k, v in operator.__dict__.items():
		if k.startswith('__get') or k.startswith('__set'):
			continue
		if k.strip('_') in operator.__dict__:
			if k in _override:
				opname, v = _override[k]
			else:
				opname = k

			def check(self, ob, opname = opname, operator = v):
				test, x, y = self.test, self.object, ob
				if self.inverse:
					if operator(x, y): raise self.test.Defect(opname)
				else:
					if not operator(x, y): raise self.test.Defect(opname)
			locals()[k] = check

	##
	# Special cases for context manager exception traps.

	def __enter__(self, partial = functools.partial):
		return partial(getattr, self, 'storage', None)

	def __exit__(self, typ, val, tb):
		test, x = self.test, self.object
		y = self.storage = val
		if isinstance(y, test.Fate):
			# Don't trap test Fates.
			# The failure has already been analyzed or some
			# other effect is desired.
			return

		if not isinstance(y, x): raise self.test.Defect("unexpected exception")
		return True # !!! Inhibiting raise.

	def __xor__(self, subject):
		"""
		Call the subject while trapping the configured exception::

			test/Exception ^ subject

		Reads: "Test that 'Exception' is raised by 'subject'".
		"""
		with self as exc:
			subject()
		return exc()
	__rxor__ = __xor__

##
# Fate exceptions are used to manage the exception
# and the completion state of a test. Fate is a Control exception (BaseException).
class Fate(BaseException):
	"""
	The Fate of a test. Sealed by :py:meth:`.Test.seal`.
	"""
	name = 'fate'
	content = None
	impact = None
	line = None
	color = 'white'

	def __init__(self, content):
		self.content = content

class Pass(Fate):
	abstract = 'the test was explicitly passed'
	impact = 1
	name = 'pass'
	code = 0
	color = 'green'

class Return(Pass):
	abstract = 'the test returned'
	impact = 1
	name = 'return'
	code = 1
	color = 'green'

class Explicit(Pass):
	abstract = 'the test cannot be implicitly invoked'
	impact = 0
	name = 'explicit'
	code = 2
	color = 'magenta'

class Skip(Pass):
	abstract = 'the test was skipped'
	impact = 0
	name = 'skip'
	code = 3
	color = 'cyan'

class Divide(Fate):
	abstract = 'the test consisted of a set of tests'
	impact = 0
	name = 'divide'
	code = 4
	color = 'blue'

	def __init__(self, container, limit = 1):
		self.content = container
		self.tests = []
		self.limit = limit

class Fail(Fate):
	abstract = 'the test raised an exception or contended an absurdity'
	impact = -1
	name = 'fail'
	code = 5
	color = 'red'

class Void(Fail):
	abstract = 'the coverage data of the test does not meet expectations'
	name = 'void'
	code = 6
	color = 'red'

class Expire(Fail):
	abstract = 'the test did not finish in the allowed time'
	name = 'expire'
	code = 8
	color = 'yellow'

class Core(Fail):
	abstract = 'the test caused a core dumped or segmentation violation'
	name = 'core'
	code = 9
	color = 'orange'

class Test(object):
	"""
	An object that manages an individual test unit.

	A test unit consists of a `focus`, `identity`, and `fate`:

	 `identity`
	  A unique identifier for the `Test`. Usually, a qualified name that can be used to
	  locate the `focus`.
	 `focus`
	  The callable that performs a series of checks--using the `Test` instance--that
	  determines the `fate`.
	 `fate`
	  The conclusion of the Test; pass, fail, error, skip.
	"""
	__slots__ = ('focus', 'identity', 'constraints', 'fate', 'proceeding',)

	# These referenced via Test instances to allow subclasses to override
	# the implementations.
	Defect = Defect
	Contention = Contention
	Fate = Fate
	Pass = Pass
	Return = Return
	Explicit = Explicit
	Skip = Skip
	Divide = Divide
	Fail = Fail
	Void = Void
	Core = Core
	Expire = Expire

	def __init__(self, proceeding, identity, focus, *constraints):
		# allow explicit identity as the callable may be a wrapped function
		self.proceeding = proceeding
		self.identity = identity
		self.focus = focus
		self.constraints = constraints

	def __truediv__(self, object):
		return self.Contention(self, object)

	def __rtruediv__(self, object):
		return self.Contention(self, object)

	def __floordiv__(self, object):
		return self.Contention(self, object, True)

	def __rfloordiv__(self, object):
		return self.Contention(self, object, True)

	def seal(self):
		"""
		Seal the fate of the Test. This should only be called once.
		"""
		tb = None

		try:
			r = self.focus(self)
			# Make an attempt at causing any deletions.
			gc.collect()
			if not isinstance(r, self.Fate):
				self.fate = self.Return(r)
			else:
				self.fate = r
		except (self.Pass, self.Divide) as exc:
			tb = exc.__traceback__ = exc.__traceback__.tb_next
			self.fate = exc
		except BaseException as err:
			# place error out
			tb = err.__traceback__ = err.__traceback__.tb_next
			self.fate = self.Fail('test raised exception')
			self.fate.__cause__ = err

		if tb is not None:
			self.fate.line = tb.tb_lineno

	def explicit(self):
		raise self.Explicit("must be explicitly invoked")

	def skip(self, condition):
		if condition:
			raise self.Skip(condition)

	def fail(self, cause):
		raise self.Fail(cause)

	def trap(self):
		"""
		Set a Trap for exceptions converting the Error fate to a Failure::

			with test.trap():
				...

		This allows :py:meth:`fail` implementations set a trace prior to exiting
		the test :term:`focus`.

		:py:class:`Fate` exceptions are not trapped.
		"""
		return (self / None.__class__)

	try:
		from gc import collect
		def garbage(self, minimum = 0, collect = collect, **kw):
			'Request collection with the expectation of a minimum unreachable.'
			unreachable = collect()
			if unreachable < minimum: raise test.Fail('missed garbage collection expectation')
	except ImportError:
		def garbage(self, *args, **kw):
			'Garbage collection not available'
			pass

def execute(module):
	"""
	Execute the tests contained in the given container. Usually given a module object.

	This test runner exists primarily for initial dev.bin.test dependency testing.
	Proceeding has a fair amount of complexity that presumes much about the
	structure of the package being tested.

	.. warning:: No status information is printed. Raises the first negative impact Test.
	"""
	for id, func in gather(module):
		test = Test(None, id, func)
		test.seal()
		if test.fate.impact < 0:
			raise test.fate
