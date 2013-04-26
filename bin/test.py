"""
Run developer tests emitting test meta data.

Each test is ran in a subprocess, one at a time.
"""
import os
import sys
import contextlib
import signal

import factory.lib
import factory.loader

import routes.lib
import fork.lib

from .. import libcore
from .. import libtest
from .. import libmeta
from .. import libtrace
from .. import libtraceback
from .. import gcov

class Test(libtest.Test):
	def __init__(self, proceeding, *args, **kw):
		self.tracing = proceeding.tracing
		self.package = proceeding.package

		super().__init__(proceeding, *args, **kw)

	def seal(self):
		with self.tracing(self.package, self.identity):
			super().seal()

	def fail(self, *args):
		import pdb
		sys.stderr.write('\n')
		sys.stderr.write(libtest.color('yellow', 'failed ') + str(args[0]) + '\n')
		pdb.set_trace()
		sys.stderr.write(libtest.top_fate_messages + '\n')
		super().fail(*args)

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
	def info():
		import linecache
		import fork.thread
		snapshot = dict(sys._current_frames())
		pid = os.getpid()
		ttid = fork.thread.identity()
		buf = "[{pid}] {nthreads} threads\n".format(pid=pid, nthreads=len(snapshot)-1)

		for tid, f in snapshot.items():
			if tid == ttid:
				continue
			co = f.f_code
			l = f.f_lineno
			path = co.co_filename
			func = co.co_name
			line = linecache.getline(path, l)
			buf += "File \"{file}\" line {lineno} in {func} ({tid})\n{line}".format(tid=hex(tid), func=func, file=path, lineno=l, line=line)
		print(buf)
	def _info(*args):
		fork.lib.taskq.enqueue(info)

	signal.signal(signal.SIGINFO, _info)

	# promote to test, but iff the role was unchanged.
	# in cases where finals are ran, this will be 'factor'.
	if factory.lib.role is None:
		factory.lib.role = 'test'

	libmeta.void_package(package)
	with libcore.dumping():
		p = Proceeding(package)
		fork.lib.pivot(p.execute, modules)

if __name__ == '__main__':
	import sys

	def ijtrace(*args):
		import os
		print(os.getpid())
		signal.signal(signal.SIGINT, signal.SIG_DFL)
		import pdb; pdb.set_trace() # sigint
	#signal.signal(signal.SIGINT, ijtrace)

	package, *modules = sys.argv[1:]
	main(package, modules)
