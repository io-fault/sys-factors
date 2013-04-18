"""
Run developer tests emitting test meta data.

Each test is ran in a subprocess, one at a time.
"""
import sys
import contextlib
import compile.lib
import compile.loader
from .. import libcore
from .. import libtest
from .. import libmeta
from .. import libtrace
from .. import libtraceback
from .. import gcov

import routes.lib
import fork.cpython
import signal

class Test(libtest.Test):
	def fail(self, *args):
		import pdb
		sys.stderr.write('\n')
		sys.stderr.write(libtest.color('yellow', 'failed ') + str(args[0]) + '\n')
		pdb.set_trace()
		sys.stderr.write(libtest.top_fate_messages + '\n')
		super().fail(*args)

def main(package, modules):
	# promote to test, but iff the role was unchanged.
	# in cases where finals are ran, this will be 'factor'.
	if compile.lib.role is None:
		compile.lib.role = 'test'

	if compile.lib.role == 'test':
		# gather extension modules
		x = routes.lib.Import.from_fullname(package)
		pkg, mods = x.tree()
		cexts = [
			x for x in mods
			if isinstance(x.loader, compile.loader.CLoader)
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
		p = libtest.Proceeding(package)
		p.execute(modules, (external, libtrace.Trace), Test = Test)

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
