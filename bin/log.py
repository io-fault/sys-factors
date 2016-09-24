"""
Executable module taking a single parameter that emits the compilation
transcript to standard out.
"""
import sys
import os
import importlib
import collections

from ..probes import libpython
from .. import library as libdev

from ...system import libfactor
from ...routes import library as libroutes

if __name__ == '__main__':
	env = os.environ
	command, module_fullname, *files = sys.argv

	factor = libdev.Factor(libroutes.Import.from_fullname(module_fullname), None, None)

	ctx = libdev.Context.from_environment()
	variants, mech = ctx.select(factor.type)

	refs = list(factor.dependencies())
	cs = collections.defaultdict(set)
	for f in refs:
		cs[f.pair].add(f)

	vset = factor.link(variants, ctx, mech, cs, [])
	for src_params, (vl, key, locations) in vset:
		logs = locations['log']

		files = logs.tree()[1]
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
