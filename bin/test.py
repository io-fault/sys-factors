"""
Run developer tests emitting test meta data.

Each test is ran in a clone, one at a time.
"""
import os
import sys
import contextlib
import signal
import functools

from ...xeno import lib as xenolib
from ...routes import lib as routeslib
from ...fork import lib as forklib
from ...txt import libint

from .. import libtest
from .. import libcore
from .. import libmeta
from .. import libtrace
from .. import gcov

def color(color, text, _model = "∫text xterm.fg.%s∫"):
	return libint.Model(_model % (color,)).argformat(text)

open_fate_message = color('0x1c1c1c', '|')
close_fate_message = color('0x1c1c1c', '|')
top_fate_messages = color('0x1c1c1c', '+' + ('-' * 10) + '+')
bottom_fate_messages = color('0x1c1c1c', '+' + ('-' * 10) + '+')

##
# Test and Proceeding are extremely basic in libtest, and
# dev.bin.test exists to provide a more communicable interface
# to the execution of a set of tests.
##

class Test(libtest.Test):
	def __init__(self, proceeding, *args, **kw):
		self.tracing = proceeding.tracing
		self.package = proceeding.package
		super().__init__(proceeding, *args, **kw)

	def seal(self):
		with self.tracing(self.package, self.identity):
			return super().seal()

	def fail(self, *args):
		import pdb
		sys.stderr.write('\n')
		sys.stderr.write(libtest.color('yellow', 'failed ') + str(args[0]) + '\n')
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

	def module_test(self, test):
		"""
		Fork for each test. The actual execution of the module tests may not be in forked
		subprocesses. The *test* forks, which may or may not result in a process fork.
		"""
		module = importlib.import_module(test.identity)
		module.__tests__ = gather(module)
		if '__test__' in dir(module):
			# allow module to skip the entire set
			module.__test__(test)
		return test.Divide(module)

	def package_test(self, test):
		"""
		Fork for each test module. The actual execution of the module tests may not be in forked
		subprocesses. The *test* forks, which may or may not result in a process fork.
		"""
		# The package module
		module = importlib.import_module(test.identity)
		test/module.__name__ == test.identity
		if 'context' in dir(module):
			module.context() # XXX: manage package context for dependency maanagement

		ir = routeslib.Import.from_fullname(module.__name__)
		module.__tests__ = [
			(x.fullname, self.module_test) for x in ir.subnodes()[1]
			if x.identity.startswith('test_') and (not test.constraints or x.identity in test.constraints)
		]
		return test.Divide(module)

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

	def _run(self, test):
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

		if isinstance(test.fate, test.Divide):
			self._dispatch(test.fate.content, ())
		elif isinstance(test.fate, test.Error):
			self._print_tb(test.fate)
			import pdb
			# error cases chain the exception
			pdb.post_mortem(test.fate.__cause__.__traceback__)

		return report

	def _handle_core(self, corefile):
		if corefile is None:
			return
		import subprocess
		import shutil

		if os.path.exists(corefile):
			sys.stderr.write("CORE: Identified, {0!r}, loading debugger.\n".format(corefile))
			libcore.debug(corefile)
			sys.stderr.write("CORE: Removed file.\n".format(corefile))
			os.remove(corefile)
		else:
			sys.stderr.write('CORE: File does not exist: ' + repr(corefile) + '\n')

	def _complete(self, test, report):
		rpid, status

		if os.WCOREDUMP(status):
			faten = 'core'
			report['fate'] = 'core'
			parts = test.identity.split('.')
			parts[0] = color('0x1c1c1c', parts[0])
			parts[:-1] = [color('gray', x) for x in parts[:-1]]
			ident = color('red', '.').join(parts)
			sys.stderr.write('\r{start} {fate!s} {stop} {tid}                \n'.format(
				fate = color(test.fate.color, faten.ljust(8)), tid = ident,
				start = open_fate_message,
				stop = close_fate_message
			))
			self._handle_core(libcore.corelocation(rpid))
		elif not os.WIFEXITED(status):
			# redrum
			import signal
			try:
				os.kill(pid, signal.SIGKILL)
			except OSError:
				pass

		report['exitstatus'] = os.WEXITSTATUS(status)
		return report

	def _dispatch(self, container, constraints):
		for id, tcall in container.__tests__:
			test = self.Test(self, id, tcall, *constraints)

			parts = test.identity.split('.')
			parts[0] = color('0x1c1c1c', parts[0])
			parts[:-1] = [color('gray', x) for x in parts[:-1]]
			ident = color('red', '.').join(parts)
			sys.stderr.write('{bottom} {tid} ...'.format(
				bottom = bottom_fate_messages,
				tid = ident,
			))
			sys.stderr.flush() # want to see the test being ran

			rsrc = spawn('clone', functools.partial(enqueue, self._run, test))
			graph(rsrc, crossmethod)

			report = {'fate': 'unknown', 'impact': -1}
			self._complete(test, report)
			if report['impact'] < 0:
				sys.exit(report['exitstatus'])

	def execute(self, modules):
		m = types.ModuleType("testing")
		m.__tests__ = [(self.package + '.test', self.package_test)]
		sys.stderr.write(top_fate_messages + '\n')
		self._dispatch(m, modules)
		sys.stderr.write(bottom_fate_messages + '\n')

class Proceeding(Proceeding):
	def track_imports(self, imported):
		self.fimports.add((imported.fullname, imported.source))

	def _run(self, *args, **kw):
		report = super()._run(*args, **kw)
		report['fimports'] = list(self.fimports)
		self.fimports.clear()
		return report

	def _complete(self, test, *args):
		report = super()._complete(test, *args)

		if factory.lib.role == 'test':
			for fullname, source in report.get('fimports', ()):
				gcov.record(test.identity, fullname)
				if not libmeta.route(source, "lines").exists():
					# Fill out crossable and ignored records for the module
					# Python modules should do this at some point.
					gcov.record('crossable', fullname, metatype = "lines", proc = gcov.crossable)
					gcov.record('ignored', fullname, metatype = "lines", proc = gcov.ignored)
		return report

	def __init__(self, *args):
		# tests return the cextensions loaded so we can collect coverage data
		self.fimports = set()
		factory.loader.CLoader.traceset.add(self.track_imports)
		self.tracing = libtrace.Tracing
		super().__init__(*args, Test = Test)

def main(package, modules):
	# promote to test, but iff the role was unchanged.
	# in cases where finals are ran, this will be 'factor'.
	if factory.lib.role is None:
		factory.lib.role = 'test'

	# clear prior reporting
	libmeta.void_package(package)

	# enable core dumps
	p = Proceeding(package)
	enqueue(functools.partial(p.execute, modules))

if __name__ == '__main__':
	package, *modules = sys.argv[1:]
	with libcore.dumping():
		fork.lib.control(init = functools.partial(main, package, modules))
