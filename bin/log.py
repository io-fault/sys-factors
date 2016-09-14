"""
Executable module taking a single parameter that emits the compilation
transcript to standard out.
"""
import sys
import os
import importlib
import collections

from ..probes import libpython
from .. import libconstruct

from ...system import libfactor
from ...routes import library as libroutes

if __name__ == '__main__':
	env = os.environ
	command, module_fullname, *files = sys.argv

	factor = libconstruct.Factor(libroutes.Import.from_fullname(module_fullname), None, None)

	contexts = libconstruct.contexts(env.get('FPI_PURPOSE', 'debug'), environment=env.get('DEV_CONTEXT_DIRECTORY', ()))
	refs = list(factor.dependencies())
	cs = collections.defaultdict(set)
	for f in refs:
		cs[f.pair].add(f)

	mech, fp, *ignored = libconstruct.initialize(contexts, factor, cs, [])
	logdir = factor.reduction().container / 'log'

	if files:
		files = [logdir.extend(x.split('/')) for x in files]
	else:
		files = logdir.tree()[1]

	for logfile in files:
		sys.stdout.write('[' + str(logfile) + ']\n')
		if not logfile.exists():
			sys.stdout.write('! ERROR: File does not exist.\n')
			continue

		with logfile.open('rb') as f:
			log = f.read()
			if log:
				sys.stdout.buffer.write(log)
				sys.stdout.write("\n")
			else:
				sys.stdout.write('! NOTE: Empty logfile.\n')
