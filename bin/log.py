"""
# Executable module taking a single parameter that emits the compilation
# transcript to standard out.
"""
import sys
import os
import importlib
import collections

from .. import cc

from fault.system import python

if __name__ == '__main__':
	env = os.environ
	command, module_fullname, *files = sys.argv

	factor = cc.Factor(python.Import.from_fullname(module_fullname), None, None)

	ctx = cc.Context.from_environment()
	variants, mech = ctx.select(factor.domain)

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
			if logfile.fs_type() == 'void':
				sys.stdout.write('! ERROR: File does not exist.\n')
				continue

			with logfile.fs_open('rb') as f:
				log = f.read()
				if log:
					sys.stdout.buffer.write(log)
					sys.stdout.write("\n")
				else:
					sys.stdout.write('! NOTE: Empty logfile.\n')
