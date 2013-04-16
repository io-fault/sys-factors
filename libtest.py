"""
A testing library that minimizes the distance between the test runner, and
the actual tests for the purpose of keeping the execution machinary as simple as possible.
"""
import os
import sys
import importlib
import contextlib
import operator
import functools
import types

import routes.lib
from . import libcore

#: Mapping of Fate names to colors.
color_of_fate = {
	'fate': 'white',
	'pass': 'green', # bright green. pass is unusual
	'return': '0x00aa00', # dim green. return is usual.
	'skip': 'cyan',
	'fork': 'blue',
	'explicit': 'magenta',

# failures
	'error': 'red',
	'core': 'orange',
	'fail': 'yellow',
	'expire': 'yellow',
}

import txt.libint

def color(color, text, _model = "∫text xterm.fg.%s∫"):
	return txt.libint.Model(_model % (color,)).argformat(text)

open_fate_message = color('0x1c1c1c', '│')
close_fate_message = color('0x1c1c1c', '│')
top_fate_messages = color('0x1c1c1c', '┌' + ('─' * 10) + '┐')
bottom_fate_messages = color('0x1c1c1c', '└' + ('─' * 10) + '┘')

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
	impact = 0
	name = 'fork'

	def __init__(self, container, limit = 1):
		self.content = container
		self.tests = []
		self.limit = limit

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
				opname, v = _override[k]
			else:
				opname = k

			def check(self, ob, opname = opname, operator = v):
				test, x, y = self.test, self.object, ob
				if self.inverse:
					if operator(x, y): test.fail(opname)
				else:
					if not operator(x, y): test.fail(opname)
			locals()[k] = check

	##
	# Special cases for context manager exception traps.

	def __enter__(self, partial = functools.partial):
		return partial(getattr, self, 'storage', None)

	def __exit__(self, typ, val, tb):
		test, x = self.test, self.object
		y = self.storage = val

		if not isinstance(y, x): test.fail("not exception")
		return True # !!! Inhibiting raise.

	def __xor__(self, subject):
		with self as exc:
			subject()
		return exc()
	__rxor__ = __xor__

class Test(object):
	__slots__ = ('focus', 'identity', 'constraints', 'fate')

	def __init__(self, identity, focus, *constraints):
		# allow explicit identity as the callable may be a wrapped function
		self.identity = identity
		self.focus = focus
		self.constraints = constraints

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

class Proceeding(object):
	"""
	The collection and executions of a series of tests.
	"""
	def __init__(self, package):
		self.package = package
		self.selectors = []

	def module_test(self, test):
		"""
		Fork for each test.
		"""
		module = importlib.import_module(test.identity)
		module.__tests__ = gather(module)
		test.fork(module)

	def package_test(self, test):
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
			(x.fullname, self.module_test) for x in ir.subnodes()[1]
			if x.identity.startswith('test_') and (not test.constraints or x.identity in test.constraints)
		]
		test.fork(module)

	##
	# XXX: This is a mess. It will be getting cleaned up soon.

	def _print_tb(self, fate):
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

	def _run(self, test, contexts, Test = Test):
		pid = os.fork()
		if pid != 0:
			return pid

		with contexts[1](self.package, test.identity):
			test.seal()

		faten = test.fate.__class__.__name__.lower()
		parts = test.identity.split('.')
		parts[0] = color('0x1c1c1c', parts[0])
		if test.fate.impact >= 0:
			parts[1:] = [color('gray', x) for x in parts[1:]]
		else:
			parts[1:-1] = [color('gray', x) for x in parts[1:-1]]
		ident = color('red', '.').join(parts)
		sys.stderr.write('\r{start} {fate!s} {stop} {tid}                \n'.format(
			fate = color(color_of_fate[faten], faten.ljust(8)),
			tid = ident,
			start = open_fate_message,
			stop = close_fate_message
		))

		if isinstance(test.fate, Fork):
			self._dispatch(test.fate.content, (), contexts, Test = Test)
		elif isinstance(test.fate, Error):
			self._print_tb(test.fate)
			import pdb
			# error cases chain the exception
			pdb.post_mortem(test.fate.__cause__.__traceback__)

		if test.fate.impact < 0:
			sys.exit(9)
		else:
			sys.exit(0)

	def _handle_core(self, corefile):
		if corefile is None:
			return
		import subprocess
		import shutil

		if os.path.exists(corefile):
			sys.stderr.write("CORE: Identified, {0!r}, loading debugger.\n".format(corefile))
			p = subprocess.Popen((shutil.which('gdb'), '--quiet', '--core=' + corefile, sys.executable))
			#p = subprocess.Popen((shutil.which('lldb'), '--core=' + corefile, sys.executable))
			p.wait()
			sys.stderr.write("CORE: Removed file.\n".format(corefile))
			os.remove(corefile)
		else:
			sys.stderr.write('CORE: File does not exist: ' + repr(corefile) + '\n')

	def _complete(self, test, pid):
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
			faten = 'core'
			parts = test.identity.split('.')
			parts[0] = color('0x1c1c1c', parts[0])
			parts[:-1] = [color('gray', x) for x in parts[:-1]]
			ident = color('red', '.').join(parts)
			sys.stderr.write('\r{start} {fate!s} {stop} {tid}                \n'.format(
				fate = color(color_of_fate[faten], faten.ljust(8)), tid = ident,
				start = open_fate_message,
				stop = close_fate_message
			))
			self._handle_core(libcore.corelocation(pid))
			return 7
		elif not os.WIFEXITED(status):
			# redrum
			import signal
			try:
				os.kill(pid, signal.SIGKILL)
			except OSError:
				pass

		return os.WEXITSTATUS(status)

	def _dispatch(self, container, constraints, contexts, Test = Test):
		for id, tcall in container.__tests__:
			test = Test(id, tcall, *constraints)

			parts = test.identity.split('.')
			parts[0] = color('0x1c1c1c', parts[0])
			parts[:-1] = [color('gray', x) for x in parts[:-1]]
			ident = color('red', '.').join(parts)
			sys.stderr.write('{bottom} {tid} ...'.format(
				bottom = bottom_fate_messages,
				tid = ident,
			))
			sys.stderr.flush() # want to see the test being ran

			pid = self._run(test, contexts, Test = Test)
			sys.stderr.write('\b\b\b' + color('red', str(pid)))
			sys.stderr.flush() # want to see the test being ran

			with contexts[0]():
				# (package, test.identity, pid)
				status = self._complete(test, pid)
				if status:
					sys.exit(status)

	def execute(self, modules, contexts, Test = Test):
		m = types.ModuleType("testing")
		m.__tests__ = [(self.package + '.test', self.package_test)]
		sys.stderr.write(top_fate_messages + '\n')
		self._dispatch(m, modules, contexts, Test = Test)
		sys.stderr.write(bottom_fate_messages + '\n')
