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
	def fail(self, *args):
		import pdb
		sys.stderr.write('\n')
		sys.stderr.write(libtest.color('yellow', 'failed ') + str(args[0]) + '\n')
		pdb.set_trace()
		sys.stderr.write(libtest.top_fate_messages + '\n')
		super().fail(*args)

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

	if factory.lib.role == 'test':
		# gather extension modules
		x = routes.lib.Import.from_fullname(package)
		pkg, mods = x.tree()
		cexts = [
			x for x in mods
			if isinstance(x.loader, factory.loader.CLoader)
		]
		@contextlib.contextmanager
		def external(identity, _cexts = cexts):
			try:
				yield None
			finally:
				for x in _cexts:
					gcov.record(identity, x.fullname)
					# Fill out coverable lines
					if not libmeta.route(x.file().fullpath, "lines").exists():
						gcov.record('variable', x.fullname, metatype = "lines", proc = gcov.lout)
	else:
		@contextlib.contextmanager
		def nothing(identity):
			try:
				yield None
			finally:
				pass
		external = nothing

	libmeta.void_package(package)
	with libcore.dumping():
		p = libtest.Proceeding(package, Test = Test)
		p.execute(modules, (external, libtrace.Tracing))

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
