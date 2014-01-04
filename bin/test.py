"""
Run developer tests emitting test meta data.

Each test is ran in a clone, one at a time.
"""
import os
import sys
import contextlib
import signal
import functools

import factory.lib
import factory.loader

import routes.lib
import fork.lib

from .. import libcore
from .. import libtest
from .. import libmeta
from .. import libtrace
from .. import gcov

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

@fork.lib.procedure
def dispatch(
	catalog,
	test_process = fork.lib.Process,
	test = Test,
):
	@fork.lib.crossmethod
	def start(test):
		"""
		Kick off the test in a subprocess.
		"""
		catalog.test_process = context().spawn('fork', test)

	@fork.lib.crossmethod
	def finished(test_process, process_exit = tuple):
		"""
		Executed when the test subprocess exits.
		"""
		pass

class Proceeding(libtest.Proceeding):
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
