"""
Run the tests of a project while capturing coverage data and profile information.
"""
import os
import sys
import contextlib
import signal
import functools
import types
import importlib

from ...routes import library as routeslib
from ...system import library as libsys

from .. import libtest
from .. import libcore
from .. import libmeta
from .. import libtrace
from .. import coverage

def color(color, text, _model = "∫text xterm.fg.%s∫"):
	return text

def color_identity(identity):
	parts = identity.split('.')
	parts[0] = color('0x1c1c1c', parts[0])
	parts[:-1] = [color('gray', x) for x in parts[:-1]]
	return color('red', '.').join(parts)

open_fate_message = color('0x1c1c1c', '|')
close_fate_message = color('0x1c1c1c', '|')
top_fate_messages = color('0x1c1c1c', '+' + ('-' * 10) + '+')
working_fate_messages = color('0x1c1c1c', '+' + ('/\\' * 5) + '+')
bottom_fate_messages = color('0x1c1c1c', '+' + ('-' * 10) + '+')

class Test(libtest.Test):
	__slots__ = libtest.Test.__slots__ + ('proceeding',)

	def seal(self):
		with self.proceeding.tracing(self.proceeding.package, self.identity):
			return super().seal()

	def fail(self, *args):
		import pdb
		sys.stderr.write('\n')
		sys.stderr.write('failed ' + str(args[0]) + '\n')
		pdb.set_trace()
		sys.stderr.write(libtest.top_fate_messages + '\n')
		super().fail(*args)

class Proceeding(object):
	"""
	The collection and execution of a series of tests.
	"""
	Test = Test

	def __init__(self, package):
		self.package = package
		self.selectors = []
		self.cextensions = []
		self.fimports = {}
		self.tracing = libtrace.Tracing

	def module_test(self, test):
		"""
		Fork for each test. The actual execution of the module tests may not be in forked
		subprocesses. The *test* forks, which may or may not result in a process fork.
		"""
		module = importlib.import_module(test.identity)
		test/module.__name__ == test.identity

		module.__tests__ = libtest.gather(module)
		if '__test__' in dir(module):
			# allow module to skip the entire set
			module.__test__(test)
		raise libtest.Divide(module)

	def package_test(self, test):
		"""
		Fork for each test module. The actual execution of the module tests may not be in forked
		subprocesses. The *test* forks, which may or may not result in a process fork.
		"""
		# The package module
		module = importlib.import_module(test.identity)
		test/module.__name__ == test.identity

		if 'context' in dir(module):
			module.context()

		ir = routeslib.Import.from_fullname(module.__name__)
		module.__tests__ = [
			(x.fullname, self.module_test)
			for x in ir.subnodes()[1] # modules only; NO packages.
			if x.identity.startswith('test_') and (not test.constraints or x.identity in test.constraints)
		]
		raise libtest.Divide(module)

	@staticmethod
	def _status_test_sealing(test):
		sys.stderr.write('{working} {tid} ...'.format(
			working = working_fate_messages,
			tid = color_identity(test.identity),
		))
		sys.stderr.flush() # need to see the test being ran right now

	@staticmethod
	def _report_core(test):
		sys.stderr.write('\r{start} {fate!s} {stop} {tid}                \n'.format(
			fate = color(test.fate.color, 'core'.ljust(8)), tid = color_identity(test.identity),
			start = open_fate_message,
			stop = close_fate_message
		))

	@staticmethod
	def _handle_core(corefile):
		if corefile is None:
			return

		if os.path.exists(corefile):
			sys.stderr.write("CORE: Identified, {0!r}, loading debugger.\n".format(corefile))
			libcore.debug(corefile)
			sys.stderr.write("CORE: Removed file.\n".format(corefile))
			os.remove(corefile)
		else:
			sys.stderr.write("CORE: File does not exist: " + repr(corefile) + '\n')

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

	def _seal(self, test):
		sys.stderr.write('\b\b\b' + color('red', str(os.getpid())))
		sys.stderr.flush() # want to see the test being ran

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
			fate = color(test.fate.color, faten.ljust(8)),
			tid = ident,
			start = open_fate_message,
			stop = close_fate_message
		))

		report = {
			'test': test.identity,
			'impact': test.fate.impact,
			'fate': faten,
		}

		if isinstance(test.fate, libtest.Divide):
			self.execute(test.fate.content, (), division = True)
		elif isinstance(test.fate, libtest.Fail):
			self._print_tb(test.fate)
			import pdb
			# error cases chain the exception
			pdb.post_mortem(test.fate.__cause__.__traceback__)

		report['fimports'] = list(self.fimports.items())
		self.fimports.clear()

		return report

	def _dispatch(self, test):
		faten = None
		self._status_test_sealing(test)

		# seal fate in a child process
		_seal = libsys.concurrently(functools.partial(self._seal, test))

		l = []
		report = _seal(status_ref = l.append)

		if report is None:
			report = {'fate': 'unknown', 'impact': -1}

		pid, status = l[0]

		if os.WCOREDUMP(status):
			faten = 'core'
			report['fate'] = 'core'
			test.fate = libtest.Core(None)
			self._report_core(test)
			self._handle_core(libcore.corelocation(pid))
		elif not os.WIFEXITED(status):
			# redrum
			import signal
			try:
				os.kill(pid, signal.SIGKILL)
			except OSError:
				pass

		report['exitstatus'] = os.WEXITSTATUS(status)

		# C library coverage code

		if report['impact'] < 0 and faten != 'core':
			sys.exit(report['exitstatus'])

		return report

	def execute(self, container, modules, division = None):
		if division is None:
			sys.stderr.write(top_fate_messages + '\n')

		for tid, tcall in getattr(container, '__tests__', ()):
			test = self.Test(tid, tcall)
			test.proceeding = self
			self._dispatch(test)

		if division is None:
			sys.stderr.write(bottom_fate_messages + '\n')

def main(package, modules):
	# Set test role. Per project?
	# libconstruct.role = 'test'

	# enable core dumps
	p = Proceeding(package)

	m = types.ModuleType("testing")
	m.__tests__ = [(package + '.test', p.package_test)]

	p.execute(m, modules)

	raise SystemExit(0)

if __name__ == '__main__':
	package, *modules = sys.argv[1:]
	with libcore.dumping():
		libsys.control(functools.partial(main, package, modules))