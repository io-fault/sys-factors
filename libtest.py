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
	The Fate of a test. Sealed by :py:meth:`Test.seal`.
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

class Implicit(Pass):
	'the test cannot be implicitly invoked'
	impact = 0
	name = 'implicit'

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

# Exposes an assert like interface to testing.
class Subject(object):
	__slots__ = ('test', 'object', 'storage', 'inverse')

	def __init__(self, test, object, inverse = False):
		self.test = test
		self.object = object
		self.inverse = inverse

	# Build operator methods based on operator.
	_override = {
		'__truediv__' : ('isinstance', isinstance),
		'__sub__' : ('issubclass', issubclass),
	}
	for k, v in operator.__dict__.items():
		if k.startswith('__get') or k.startswith('__set'):
			continue
		if k.strip('_') in operator.__dict__:
			if k in _override:
				cmpname, v = _override[k]
			else:
				cmpname = k

			def check(self, ob, cmpname = cmpname, comparison = v):
				test, x, y = self.test, self.object, ob
				if self.inverse:
					if comparison(x, y): test.fail(cmpname, x, y)
				else:
					if not comparison(x, y): test.fail(cmpname, x, y)
			locals()[k] = check

	##
	# Special cases for context manager exception traps.

	def __enter__(self, partial = functools.partial):
		return partial(getattr, self, 'storage', None)

	def __exit__(self, typ, val, tb):
		test, x = self.test, self.object
		self.storage = val

		if not isinstance(val, x): self.fail("isinstance", val, x)
		return True # !!! Inhibiting raise.

	def __xor__(self, subject):
		with self:
			subject()
	__rxor__ = __xor__

class Test(object):
	__slots__ = ('focus', 'identity', 'module')

	def __init__(self, focus, identity = None, module = None):
		# allow explicit identity as the callable may be a wrapped function
		self.focus = focus
		self.identity = identity
		self.module = module

	def __truediv__(self, object):
		return Subject(self, object)

	def __rtruediv__(self, object):
		return Subject(self, object)

	def __floordiv__(self, object):
		return Subject(self, object, True)

	def __rfloordiv__(self, object):
		return Subject(self, object, True)

	def seal(self):
		"""
		Seal the fate of the Test.
		"""
		fate = None
		tb = None

		try:
			with contextlib.ExitStack() as stack:
				r = self.focus(self)
			fate = Return(r)
		except Fate as exc:
			tb = exc.__traceback__ = exc.__traceback__.tb_next
			fate = exc
		except BaseException as err:
			# place error out
			tb = err.__traceback__ = err.__traceback__.tb_next
			fate = Error('test raised exception')
			fate.__cause__ = err

		fate.test = self
		if tb is not None:
			fate.line = tb.tb_lineno

		return fate

	def explicit(self):
		raise Implicit("must be explicitly invoked")

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

	def fail(self, cause, *args):
		x, y, *other = args; raise Fail(cause)

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

def _runtests(package, module, corefile, *xtests, foreachtest = contextlib.ExitStack):
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
				with foreachtest(module.__name__ + '.' + x.identity):
					fate = x.seal()
				sys.stderr.write(fate.__class__.__name__ + '\n')

				if not isinstance(fate, Pass):
					_print_tb(fate)
					if isinstance(fate, Error):
						# error cases chain the exception
						pdb.post_mortem(fate.__cause__.__traceback__)
					else:
						pdb.post_mortem(fate.__traceback__)
					break
			except:
				sys.excepthook(*sys.exc_info())
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

def _execmodule(package, module = None,
	args = (), corefile = None,
):
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

	from . import libtrace
	from . import libmeta
	libmeta.void_package(package)
	@contextlib.contextmanager
	def construct_trace(testname, package = package):
		T = libtrace.Trace(package)
		with T:
			yield None
		T.aggregate(testname)

	for x in modules:
		_runtests(package, x, corefile, *args[1:], foreachtest = construct_trace)
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

	package = module.__name__.rsplit('.', 1)[0]

	with contextlib.ExitStack() as stack:
		# enable core dumps for c-exts
		corefile = stack.enter_context(libcore.dumping())
		# package module has context?
		if 'context' in dir(module):
			stack.enter_context(module.context())

		sys.exit(_execmodule(package, module, args = sys.argv[1:], corefile = corefile))
