"""
Test execution management and status control.

libharness provides management tools for the execution of tests and
the destination of their resulting status. Status being both the fate
of the test and any collected coverage or profile data.

! DEVELOPER:
	Future model: run tests with a specified concurrency level,
	failures are enqueued and processed by the (human) controller.
	Tests are not ran when queue is full; developer chooses to exit
	or pop/debug the failure.
	Concise failure is reported to the text log.
"""
import os
import sys
import contextlib
import signal
import functools
import types
import importlib

from ..routes import library as libroutes
from . import libtest
from . import libcore

class Status(object):
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

class Harness(object):
	"""
	The collection and execution of a set of tests.

	Harness provides overridable actions for the execution of Tests.
	Simple test runners subclass &Harness in order to manage the execution
	and status display of an evaluation.
	"""
	from . import libtest
	exit_on_failure = False

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

		module.__tests__ = self.libtest.gather(module)
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

		ir = libroutes.Import.from_fullname(module.__name__)
		module.__tests__ = [
			(x.fullname, self.module_test)
			for x in ir.subnodes()[1] # modules only; NO packages.
			if x.identity.startswith('test_') and (not test.constraints or x.identity in test.constraints)
		]

		raise libtest.Divide(module)

	def _status_test_sealing(self, test):
		self.status.write('{working} {tid} ...'.format(
			working = working_fate_messages,
			tid = color_identity(test.identity),
		))
		self.status.flush() # need to see the test being ran right now

	def _report_core(self, test):
		self.status.write('\r{start} {fate!s} {stop} {tid}                \n'.format(
			fate = color(test.fate.color, 'core'.ljust(8)), tid = color_identity(test.identity),
			start = open_fate_message,
			stop = close_fate_message
		))

	def _handle_core(self, corefile):
		if corefile is None:
			return

		if os.path.exists(corefile):
			self.status.write("CORE: Identified, {0!r}, loading debugger.\n".format(corefile))
			libcore.debug(corefile)
			self.status.write("CORE: Removed file.\n".format(corefile))
			os.remove(corefile)
		else:
			self.status.write("CORE: File does not exist: " + repr(corefile) + '\n')

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
			'interrupt': None,
		}

		if isinstance(test.fate, self.libtest.Divide):
			self.execute(test.fate.content, (), division = True)
		elif isinstance(test.fate, self.libtest.Fail):
			if isinstance(test.fate.__cause__, KeyboardInterrupt):
				report['interrupt'] = True
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
		_seal = self.concurrently(functools.partial(self._seal, test))

		l = []
		report = _seal(status_ref = l.append)

		if report is None:
			report = {'fate': 'unknown', 'impact': -1, 'interrupt': None}

		pid, status = l[0]

		if os.WCOREDUMP(status):
			faten = 'core'
			report['fate'] = 'core'
			test.fate = self.libtest.Core(None)
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

		if self.exit_on_failure and report['impact'] < 0 or report['interrupt']:
			sys.exit(report['exitstatus'])

		return report

	def execute(self, container, modules, division = None):
		for tid, tcall in getattr(container, '__tests__', ()):
			test = self.libtest.Test(tid, tcall)
			self._dispatch(test)

	def root(self, factor):
		"""
		Generate the root test from the given route.
		"""

		m = types.ModuleType("test.root")
		f = factor

		if f.type == 'project':
			m.__tests__ = [(package + '.test', self.package_test)]
		elif f.type == 'context':
			pkg, mods = f.route.subnodes()
			m.__tests__ = [
				(str(x) + '.test', self.package_test)
				for x in pkg
				if ((x/'test').module() is not None)
			]

		return m
