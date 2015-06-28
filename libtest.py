"""
A testing library that minimizes the distance between the test runner, and
the actual tests for the purpose of keeping the execution machinary as simple as possible.

libtest provides the very basics for testing in Python. Test runners are implemented else-
where as they tend to be significant pieces of code. However, a trivial @execute
function is provided that, when given a module, will execute the tests therein. Exceptions
are allowed to raise normally in order to report failures of any kind.
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
	Key function used by @gather that uses @get_test_index in
	order to elevate a test's position given that it was explicitly listed.
	"""
	return get_test_index(kv[1])

def gather(container, prefix = 'test_'):
	"""
	:returns: Ordered dictionary of attribute names associated with a `Test` instance.
	:rtype: {k : Test(v, k) for k, v in container.items()}

	Collect the objects in the container whose name starts with "test_".
	The ordered is defined by the @get_test_index function.
	"""
	tests = [('.'.join((container.__name__, name)), getattr(container, name)) for name in dir(container) if name.startswith(prefix)]
	tests.sort(key = test_order)
	return tests

class Absurdity(Exception):
	"""
	Exception raised by @Contention instances.
	"""
	pass

# Exposes an assert like interface to Test objects.
class Contention(object):
	"""
	Contentions are objects used by @Test objects to provide assertions.
	Usually, contention instances are made by the true division operator of
	@Test instances passed into unit test subjects.

		import featurelib

		def test_feature(test):
			expectation = ...
			test/featurelib.functionality() == expectation

	True division, "/", is used as it has high operator precedance that allows assertion
	expresssions to be constructed using minimal syntax that lends to readable failure
	conditions.

	All of the comparison operations are supported by Contention and are passed on to the
	underlying objects being examined.
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
					if operator(x, y): raise self.test.Absurdity(opname)
				else:
					if not operator(x, y): raise self.test.Absurdity(opname)
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

		if not isinstance(y, x): raise self.test.Absurdity("unexpected exception")
		return True # !!! Inhibiting raise.

	def __xor__(self, subject):
		"""
		Contend that the @subject raises the given exception when it is called::

			test/Exception ^ subject

		Reads: "Test that 'Exception' is raised by 'subject'".
		"""
		with self as exc:
			subject()
		return exc()
	__rxor__ = __xor__

	def __lshift__(self, subject):
		"""
		Contend that the parameter is contained by the object, @Container::

			test/Container << subject

		Reads: "Test that 'Container' contains 'subject'".
		"""
		return subject in self.object
	__rlshift__ = __lshift__

class Fate(BaseException):
	"""
	The Fate of a test. @Test.seal uses @Fate exception to describe the result of a unit test.
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

class Interrupt(Fail):
	abstract = 'the test was interrupted by a control exception'
	name = 'interrupt'
	code = 9
	color = 'orange'

class Core(Fail):
	"""
	Failure cause by a process dumping a core image.

	This exception is used by advanced test runners that execute tests in subprocesses to
	protect subsequent tests.
	"""
	abstract = 'the test caused a core dump or segmentation violation'
	name = 'core'
	code = 90
	color = 'orange'

class Test(object):
	"""
	An object that manages an individual test unit and it's execution.

	Fields:

	 & identity
	  A unique identifier for the @Test. Usually, a qualified name that can be used to
	  locate @focus without having the actual object.

	 & focus
	  The callable that performs a series of checks--using the @Test instance--that
	  determines the @fate.

	 & fate
	  The conclusion of the Test; pass, fail, error, skip. An instance of @BaseException
	  subclass.

	&fields
	"""
	__slots__ = ('focus', 'identity', 'constraints', 'fate',)

	# These referenced via Test instances to allow subclasses to override
	# the implementations.
	Absurdity = Absurdity
	Contention = Contention

	Fate = Fate

	Pass = Pass
	Return = Return

	Explicit = Explicit
	Skip = Skip
	Divide = Divide

	Fail = Fail
	Void = Void
	Expire = Expire

	# criticals
	Interrupt = Interrupt
	Core = Core

	def __init__(self, identity, focus, *constraints):
		# allow explicit identity as the callable may be a wrapped function
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
		Seal the fate of the Test by executing the subject-callable with the Test
		instance as the only parameter.

		Any exception that occurs is trapped and assigned to the @fate attribute
		on the Test instance. @None is always returned by @seal.
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
			# libtest traps any exception raised by a particular test.

			if not isinstance(err, Exception) and not isinstance(err, Fate):
				# a "control" exception.
				# explicitly note as interrupt to consolidate identification
				self.fate = self.Interrupt('test raised interrupt')
				self.fate.__cause__ = err
				raise err # e.g. kb interrupt
			elif not isinstance(err, Fate):
				# regular exception; a failure
				tb = err.__traceback__ = err.__traceback__.tb_next
				self.fate = self.Fail('test raised exception')
				self.fate.__cause__ = err
			else:
				tb = err.__traceback__ = err.__traceback__.tb_next
				self.fate = err

		if tb is not None:
			self.fate.line = tb.tb_lineno

	def explicit(self):
		"""
		Used by test subjects to inhibit runs of a particular test in aggregate runs.
		"""
		raise self.Explicit("test must be explicitly invoked in order to run")

	def skip(self, condition):
		"""
		Used by test subjects to skip the test given that the provided @condition is
		@True.
		"""
		if condition: raise self.Skip(condition)

	def fail(self, cause):
		raise self.Fail(cause)

	def trap(self):
		"""
		Set a trap for exceptions converting an would-be @Error fate on exit to a @Failure.

			with test.trap():
				...

		This allows @fail implementations set a trace prior to exiting
		the test's @focus.

		@Fate exceptions are not trapped.
		"""
		return (self / None.__class__)

	# gc collect() interface. no-op if nothing
	try:
		from gc import collect
		def garbage(self, minimum = None, collect = collect, **kw):
			'Request collection with the expectation of a minimum unreachable.'
			unreachable = collect()
			if minimum is not None and (
				unreachable < minimum
			):
				raise test.Fail('missed garbage collection expectation')
		del collect
	except ImportError:
		def garbage(self, *args, **kw):
			'Garbage collection not available'
			pass

def execute(module):
	"""
	Execute the tests contained in the given container. Usually given a module object.

	.. warning:: No status information is printed. Raises the first negative impact Test.
	"""
	for id, func in gather(module):
		test = Test(id, func)
		test.seal()
		if test.fate.impact < 0:
			raise test.fate
