"""
A testing library that minimizes the distance between the test runner, and
the actual tests for the purpose of keeping the execution machinary as simple as possible.
"""
import os
import sys
import collections
import pkgutil
import itertools
import importlib
import contextlib
import operator
import functools
import types

import routes.lib

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
	return get_test_index(kv[1])

def gather(container, prefix = 'test_'):
	"""
	:returns: Ordered dictionary of attribute names associated with a :py:class:`Test` instance.
	:rtype: {k : Test(v, k) for k, v in container.items()}

	Collect the objects in the container whose name starts with "test_".
	The ordered is defined by the :py:func:`get_test_index` function.
	"""
	tests = [('.'.join((container.__name__, name)), getattr(container, name)) for name in dir(container) if name.startswith(prefix)]
	tests.sort(key = test_order)
	return tests

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
	line = None

	def __init__(self, content):
		self.content = content

class Pass(Fate):
	'the test explicitly passed'
	impact = 1
	name = 'pass'

class Return(Pass):
	'the test returned'
	impact = 1
	name = 'return'

class Explicit(Pass):
	'the test cannot be implicitly invoked'
	impact = 0
	name = 'explicit'

class Skip(Pass):
	'the test was skipped'
	impact = 0
	name = 'skip'

class Fork(Fate):
	'the test consisted of a set of tests'
	@property
	def impact(self):
		return sum([x.impact for x in self.tests])
	name = 'fork'

	def __init__(self, container):
		self.content = container
		self.tests = []

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
					if comparison(x, y): test.fail(cmpname)
				else:
					if not comparison(x, y): test.fail(cmpname)
			locals()[k] = check

	##
	# Special cases for context manager exception traps.

	def __enter__(self, partial = functools.partial):
		return partial(getattr, self, 'storage', None)

	def __exit__(self, typ, val, tb):
		test, x = self.test, self.object
		y = self.storage = val

		if not isinstance(y, x):
			test.fail("not instance")
		return True # !!! Inhibiting raise.

	def __xor__(self, subject):
		with self as exc:
			subject()
		return exc()
	__rxor__ = __xor__

class Test(object):
	__slots__ = ('focus', 'identity', 'fate')

	def __init__(self, identity, focus):
		# allow explicit identity as the callable may be a wrapped function
		self.identity = identity
		self.focus = focus

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
		Seal the fate of the Test. This should only be called once.
		"""
		tb = None

		try:
			r = self.focus(self)
			self.fate = Return(r)
		except Fate as exc:
			tb = exc.__traceback__ = exc.__traceback__.tb_next
			self.fate = exc
		except BaseException as err:
			# place error out
			tb = err.__traceback__ = err.__traceback__.tb_next
			self.fate = Error('test raised exception')
			self.fate.__cause__ = err

		if tb is not None:
			self.fate.line = tb.tb_lineno

	def fork(self, container):
		raise Fork(container)

	def explicit(self):
		raise Explicit("must be explicitly invoked")

	def skip(self, condition):
		if condition:
			raise Skip(condition)

	def fail(self, cause):
		raise Fail(cause)

def module_test(test):
	"""
	Fork for each test.
	"""
	module = importlib.import_module(test.identity)
	module.__tests__ = gather(module)
	test.fork(module)

def package_test(test):
	"""
	Fork the test for each test module.
	"""
	# The package module
	module = importlib.import_module(test.identity)
	test/module.__name__ == test.identity
	if 'context' in dir(module):
		module.context() # XXX: manage package context for dependency maanagement

	ir = routes.lib.Import.from_fullname(module.__name__)
	module.__tests__ = [
		(x.fullname, module_test) for x in ir.subnodes()[1]
		if x.identity.startswith('test_')
	]
	test.fork(module)

##
# XXX: This is a mess. It will be getting cleaned up soon.

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

def _run(test):
	pid = os.fork()
	if pid != 0:
		return pid

	test.seal()
	sys.stderr.write('[ {fate!s:^10} ] {tid} \n'.format(
		fate = test.fate.__class__.__name__.lower(), tid = test.identity
	))

	if isinstance(test.fate, Fork):
		_dispatch(test.fate.content)
	elif not isinstance(test.fate, Pass):
		_print_tb(test.fate)
		import pdb
		if isinstance(test.fate, Error):
			# error cases chain the exception
			pdb.post_mortem(test.fate.__cause__.__traceback__)
		else:
			pdb.post_mortem(test.fate.__traceback__)
	sys.exit(0)

def _handle_core(corefile):
	sys.stderr.write('Core\n')
	if corefile is None:
		return
	import subprocess
	import shutil

	if os.path.exists(corefile):
		sys.stderr.write("CORE: Identified, {0!r}, loading debugger.\n".format(path))
		p = subprocess.Popen((shutil.which('gdb'), '--quiet', '--core=' + path, sys.executable))
		#p = subprocess.Popen((shutil.which('lldb'), '--core=' + path, sys.executable))
		p.wait()
		sys.stderr.write("CORE: Removed file.\n".format(path))
		os.remove(path)
	else:
		sys.stderr.write('CORE: File does not exist: ' + repr(path) + '\n')

def _dispatch(container):
	for id, tcall in container.__tests__:
		test = Test(id, tcall)
		sys.stderr.write('[ {fate!s:^10} ] {tid}\r'.format(
			fate = 'Fated', tid = test.identity
		))
		sys.stderr.flush() # want to see the test being ran

		pid = _run(test)

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
			_handle_core(corelocation(pid))
		elif not os.WIFEXITED(status):
			# redrum
			import signal
			try:
				os.kill(pid, signal.SIGKILL)
			except OSError:
				pass

def execute(package, modules):
	m = types.ModuleType("testing")
	m.__tests__ = [(package + '.test', package_test)]
	_dispatch(m)
