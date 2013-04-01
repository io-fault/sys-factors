"""
A testing library that minimizes the distance between the test runner, and
the actual tests for the purpose of keeping the execution machinary as simple as possible.
"""
import sys
import collections
import time
import pkgutil
import itertools
import importlib
import os
import contextlib

def packages(directory):
	"""
	Given a directory, yield all the package directories.

	This simply looks for directories that have a ``__init__.py`` file and should only
	be used in cases of initial discover where the directory may or may not be in
	:py:obj:`sys.path`.
	"""
	for x in os.listdir(directory):
		path = os.path.join(directory, x)
		if os.path.isdir(path):
			initfile = os.path.join(path, '__init__.py')
			if os.path.exists(initfile):
				yield (x, path)

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

def gather(container, prefix = 'test_'):
	"""
	:returns: Ordered dictionary of attribute names associated with a :py:class:`Test` instance.
	:rtype: {k : Test(v, k) for k, v in container.items()}

	Collect the objects in the container whose name starts with "test\_".
	The ordered is defined by the :py:func:`get_test_index` function.
	"""
	return collections.OrderedDict((
		(id, Test(f, id)) for (id, f) in
		sorted([i for i in container.items() if i[0].startswith(prefix)],
			key = lambda kv: get_test_index(kv[1]))
	))

def listpackage(package):
	"""
	Return a pair of lists containing the packages and modules in the given package module.
	"""
	packages = []
	modules = []
	prefix = package.__name__
	for (importer, name, ispkg) in pkgutil.iter_modules(package.__path__):
		path = '.'.join((prefix, name))
		if ispkg:
			packages.append(path)
		else:
			modules.append(path)
	return packages, modules

##
# Fate exceptions are used to manage the exception
# and the completion state of a test. Fate is a Control exception (BaseException).
class Fate(BaseException):
	"""
	The Fate of a test. Sealed by :py:func:`seal`.
	"""
	name = 'fate'
	content = None
	impact = None
	test = None
	line = None

	def __init__(self, content):
		self.content = content

	def __str__(self):
		return self.test.identity

class Sum(Fate):
	"""
	Fate of a collection of tests.
	"""
	name = 'sum'

	def __str__(self):
		return sum([
			k * v for (k, v) in self.content.items()
		])

class Pass(Fate):
	'the test explicitly passed'
	impact = 1
	name = 'pass'

class Return(Pass):
	'the test returned'
	impact = 1
	name = 'return'

class Skip(Pass):
	'the test was skipped by the focus'
	impact = 0
	name = 'skip'

class Dependency(Skip):
	'the test could not be ran because of a missing dependency'
	impact = 0
	name = 'dependency'

class Fail(Fate):
	'the test failed'
	impact = -1
	name = 'fail'

class Core(Fail):
	'the test caused a core dumped'
	name = 'core'

class Error(Fail):
	'the test raised an exception'
	name = 'error'

class Expire(Fail):
	'the test did not finish in the allowed time'
	name = 'expire'

def seal(test):
	"""
	Execute the given test, sealing its fate.

	Tests are designed to be repeatable, so :py:class:`Fate` instances are returned.
	"""
	fate = None
	tb = None

	try:
		with contextlib.ExitStack() as stack:
			r = test.focus(test)
		fate = Return(r)
	except Fate as exc:
		tb = exc.__traceback__ = exc.__traceback__.tb_next
		fate = exc
	except BaseException as err:
		# place error out
		tb = err.__traceback__ = err.__traceback__.tb_next
		fate = Error('test raised exception')
		fate.__cause__ = err

	fate.test = test
	if tb is not None:
		fate.line = tb.tb_lineno

	return fate

# Test Subjects offer some convenience while creating some
# opacity. Notably about __contains__ and issubclass/isinstance checks.
class Subject(tuple):
	"""
	An object to be tested.
	"""

	@property
	def test(self):
		return self[0]

	@property
	def object(self):
		return self[1]

	def __iter__(self):
		test, subject = self[0], self[1]
		for x in subject:
			yield self.__class__((test, x))

	def __ne__(self, ob):
		test, subject = self[0], self[1]
		test.fail_if_equal(subject, ob)
		return self

	def __eq__(self, case):
		test, subject = self[0], self[1]
		test.fail_if_not_equal(subject, case)
		return True

	def __gt__(self, case):
		test, subject = self[0], self[1]
		test.fail_if_less_than_or_equal(subject, case)
		return True

	def __lt__(self, case):
		test, subject = self[0], self[1]
		test.fail_if_greater_than_or_equal(subject, case)
		return True

	def __ge__(self, case):
		test, subject = self[0], self[1]
		test.fail_if_less_than(subject, case)
		return True

	def __le__(self, case):
		test, subject = self[0], self[1]
		test.fail_if_greater_than(subject, case)
		return True

	def __contains__(self, case):
		test, subject = self[0], self[1]
		test.fail_if_in(case, subject)
		return True

	def __lshift__(self, case):
		test, subject = self[0], self[1]
		test.fail_if_not_in(case, subject)
		return True

	def __rlshift__(self, case):
		return self.__rshift__(case)

	def __rshift__(self, case):
		test, subject = self[0], self[1]
		test.fail_if_not_in(subject, case)
		return True

	def __rrshift__(self, case):
		return self.__lshift__(case)

	def __xor__(self, subject):
		test, exception = self[0], self[1]
		return test.fail_if_not_raised(exception, subject)
	__rxor__ = __xor__

	def __mul__(self, superclass):
		test, subject = self[0], self[1]
		test.fail_if_not_subclass(subject, superclass)
		return True
	__rmul__ = __mul__

	def __mod__(self, superclass):
		test, subject = self[0], self[1]
		test.fail_if_not_instance(subject, superclass)
		return True
	__rmod__ = __mod__

	def __enter__(self):
		pass

	def __exit__(self, typ, val, tb):
		test, subject = self[0], self[1]
		if val is None:
			raise Fail("no exception raised")
		if not isinstance(val, subject):
			raise Fail("wrong exception raised") from val
		return True

class Test(object):
	__slots__ = ('focus', 'identity', 'module')

	def __init__(self, focus, identity = None, module = None):
		# allow explicit identity as the callable may be a wrapped function
		self.focus = focus
		self.identity = identity
		self.module = module

	def __truediv__(self, object):
		return Subject((self, object))

	def __rtruediv__(self, object):
		return Subject((self, object))

	def skip(self, cause):
		raise Skip(cause)

	def depends(self, module_path, *args, **kw):
		"""
		Import the module raising a Dependency fate if the module doesn't exist.
		"""
		try:
			return importlib.import_module(module_path, *args, **kw)
		except ImportError as exc:
			raise Dependency(module_path) from exc

	def fail(self, cause):
		"""
		Signal that the test failed.
		"""
		raise Fail(cause)

	def fail_if_exact(self, x, y):
		"""
		Fail if the `x` argument is exactly the `y` argument. ``x is y``.

		>>> x = b'a unique string'.decode('utf-8')
		>>> y = b'a unique string'.decode('utf-8')
		>>> test.fail_if_exact(x, y)
		False
		"""
		msg = "found exact object"
		if x is y: raise Fail(msg)

	def fail_if_not_exact(self, x, y):
		"""
		Fail if the `x` argument is *not* exactly `y` argument. ``x is not y``.

		>>> x = b'a unique string'.decode('utf-8')
		>>> test.fail_if_not_exact(x, x)
		False
		"""
		msg = "found inexact object"
		if x is not y: raise Fail(msg)

	def fail_if_equal(self, x, y):
		"""
		Fail if all of the given arguments or keywords are equal.

		>>> test.fail_if_equal(1, 2, 3)
		False
		"""
		msg = "equality"
		if x == y: raise Fail(msg)

	def fail_if_not_equal(self, x, y, f = lambda x: x):
		"""
		Fail if the `x` argument is *not* equal to the `y` argument.

		>>> test.fail_if_equal(1, 2)
		False
		"""
		msg = "inequality"
		if f(x) != f(y): raise Fail(msg)

	def fail_if_less_than(self, x, y):
		"""
		Fail if the `x` argument is less than the `y` argument.

		>>> test.fail_if_less_than(2, 1)
		False
		"""
		msg = "less than"
		if x < y: raise Fail(msg)

	def fail_if_greater_than(self, x, y):
		"""
		Fail if the `x` argument is greater than the `y` argument.

		>>> test.fail_if_greater_than(1, 2)
		False
		"""
		msg = "greater than"
		if x > y: raise Fail(msg)

	def fail_if_less_than_or_equal(self, x, y):
		"""
		Fail if the `x` argument is less than the `y` argument.

		>>> test.fail_if_less_than(2, 1)
		False
		"""
		msg = "less than or equal to"
		if x <= y: raise Fail(msg)

	def fail_if_greater_than_or_equal(self, x, y):
		"""
		Fail if the `x` argument is greater than the `y` argument.

		>>> test.fail_if_greater_than(1, 2)
		False
		"""
		msg = "greater than or equal to"
		if x >= y: raise Fail(msg)

	def fail_if_subclass(self, x, y):
		"""
		Fail if the `x` argument is a subclass of the `y` argument.

		>>> test.fail_if_subclass(ob, typ1, typ2)
		False
		"""
		msg = "subclass"
		if issubclass(x, y): raise Fail(msg)

	def fail_if_not_subclass(self, x, y):
		"""
		Fail if the `x` argument is NOT a subclass of the `y` argument.

		>>> test.fail_if_not_subclass(ob, typ1, typ2)
		False
		"""
		msg = "not subclass"
		if not issubclass(x, y): raise Fail(msg)

	def fail_if_instance(self, x, y):
		"""
		Fail if the `x` argument is a instance of the `y` class.

		>>> test.isinstance(ob, typ1)
		False
		"""
		msg = "instance"
		if isinstance(x, y): raise Fail(msg)

	def fail_if_not_instance(self, x, y):
		"""
		Fail if the `x` argument is not an instance of the `y` class.

		>>> test.fail_if_not_instance(ob, typ1, typ2)
		False
		"""
		msg = "not instance"
		if not isinstance(x, y): raise Fail(msg)

	def fail_if_raised(self, x, y, *args, **kw):
		"""
		Fail if the `x` argument is raised by the `y` argument callable.
		"""
		msg = "raised"
		try:
			z = y(*args, **kw)
		except BaseException as z:
			if isinstance(z, x): raise Fail(msg)
			return z
		else:
			pass

	def fail_if_not_raised(self, x, y, *args, **kw):
		"""
		Fail if the `x` argument is *not* raised by the `y` argument callable.
		"""
		msg = "not raised"
		try:
			z = y(*args, **kw)
		except BaseException as z:
			if not isinstance(z, x): raise Fail(msg)
			return z
		else:
			raise Fail(msg)

	def fail_if_in(self, x, y):
		msg = "contained"
		if x in y: raise Fail(msg)

	def fail_if_not_in(self, x, y):
		msg = "not contained"
		if x not in y: raise Fail(msg)

def _print_tb(fate):
	import traceback
	try:
		# dev.libtraceback por favor
		from IPython.core import ultratb
		x = ultratb.VerboseTB(ostream = sys.stderr)
		# doesn't support chains yet, so fallback to cause traceback.
		if fate.__cause__:
			exc = fate.__cause__
		else:
			exc = fate
		x(exc.__class__, exc, exc.__traceback__)
	except ImportError:
		tb = traceback.format_exception(fate.__class__, fate, fate.__traceback__)
		tb = ''.join(tb)
		sys.stderr.write(tb)

def _runtests(module, corefile, *xtests):
	import pdb
	tests = gather(module.__dict__)

	if xtests:
		test_progress = [tests[k] for k in xtests]
	else:
		test_progress = tests.values()

	for x in test_progress:
		sys.stderr.write(x.identity + ': ')
		sys.stderr.flush()
		before = time.time()
		pid = os.fork()
		if pid == 0:
			try:
				fate = seal(x)
				duration = time.time() - before
				sys.stderr.write('[' + str(duration) + ' seconds] ')
				sys.stderr.write(fate.__class__.__name__ + '\n')

				if not isinstance(fate, Pass):
					_print_tb(fate)
					if isinstance(fate, Error):
						# error cases chain the exception
						pdb.post_mortem(fate.__cause__.__traceback__)
					else:
						pdb.post_mortem(fate.__traceback__)
					break
			finally:
				os._exit(0)
		else:
			status = None
			signalled = False
			while status is None:
				try:
					# Interrupts can happen if a debugger is attached.
					rpid, status = os.waitpid(pid, 0)
				except OSError:
					pass
				except KeyboardInterrupt:
					import signal
					try:
						os.kill(pid, signal.SIGINT)
						signalled = True
					except OSError:
						pass

			if os.WCOREDUMP(status):
				sys.stderr.write('Core\n')
				if corefile is not None:
					import subprocess
					import shutil
					import getpass
					path = corefile(**{'pid': pid, 'uid': os.getuid(), 'user': getpass.getuser(), 'home': os.environ['HOME']})
					if os.path.exists(path):
						sys.stderr.write("CORE: Identified, {0!r}, loading debugger.\n".format(path))
						p = subprocess.Popen((shutil.which('gdb'), '--quiet', '--core=' + path, sys.executable))
						#p = subprocess.Popen((shutil.which('lldb'), '--core-file', path, sys.executable))
						p.wait()
						sys.stderr.write("CORE: Removed file.\n".format(path))
						os.remove(path)
					else:
						sys.stderr.write('CORE: File does not exist: ' + repr(path) + '\n')
			elif not os.WIFEXITED(status):
				import signal
				try:
					os.kill(pid, signal.SIGKILL)
				except OSError:
					pass

def _execmodule(module = None, args = (), corefile = None):
	if args:
		modules = [
			importlib.import_module(module.__package__ + '.' + args[0])
		]
	else:
		# package module; iterate over the "test" modules.
		packages, modules = listpackage(module)

		modules = [
			importlib.import_module(x)
			for x in modules
			if x.split('.')[-1].startswith('test_')
		]

	for x in modules:
		_runtests(x, corefile, *args[1:])
	return 0

def execmodule(module = None):
	import c.lib
	from . import libcore
	# promote to test, but iff the role was unchanged.
	if c.lib.role is None:
		c.lib.role = 'test'

	# resolve the package module

	if module is None:
		module = sys.modules['__main__']
		try:
			name = module.__loader__.name
		except AttributeError:
			name = module.__loader__.fullname

		# rename the module
		sys.modules[name] = module
		module.__name__ = name

	# if it's __main__, refer to the package; package/__main__.py
	if module.__package__ + '.__main__' == module.__name__:
		module = importlib.import_module(module.__package__)

	with contextlib.ExitStack() as stack:
		corefile = stack.enter_context(libcore.dumping())
		if 'context' in dir(module):
			stack.enter_context(module.context())

		sys.exit(_execmodule(module, args = sys.argv[1:], corefile = corefile))
