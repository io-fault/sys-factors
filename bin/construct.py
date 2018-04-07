"""
# Construct the targets of a package hierarchy for the selected context and role.
"""
import os
import sys
import types
import importlib.util

from .. import include # Minimum modification time.
from .. import cc
from fault.system import libfactor

from fault.routes import library as libroutes
from fault.chronometry import library as libtime
from fault.io import library as libio

import_from_fullname = libroutes.Import.from_fullname
import_from_module = libroutes.Import.from_module

def report(cxn, unit=None):
	"""
	# Report failure and not exit status.
	"""
	fcount = cxn.failures
	sys.stderr.write('! SUMMARY: %d factor processing instructions failed.\n' %(fcount,))

	if fcount:
		unit.result = 70 # EX_SOFTWARE
	else:
		unit.result = 0

def set_exit_code(cxn, unit=None):
	"""
	# Report failure and not exit status.
	"""
	fcount = cxn.failures
	sys.stderr.write('! SUMMARY: %d factor processing instructions failed.\n' %(fcount,))

	if fcount:
		unit.result = 70 # EX_SOFTWARE
	else:
		unit.result = 0

def main():
	"""
	# Prepare the entire package building factor targets and writing bytecode.
	"""
	import builtins
	isinstance = builtins.isinstance
	import_module = importlib.import_module
	ModuleType = types.ModuleType

	call = libio.context()
	sector = call.sector
	proc = sector.context.process

	args = proc.invocation.args
	env = proc.invocation.parameters['system'].get('environment')
	if not env:
		env = os.environ

	rebuild = env.get('FPI_REBUILD') == '1'
	ctx = cc.Context.from_environment()

	# collect packages to prepare from positional parameters
	roots = [import_from_fullname(x) for x in args]

	# Collect Python packages in the roots to build bytecode.
	simulations = list(cc.gather_simulations(list(roots)))

	for route, ref in zip(roots, args):
		if not route.exists():
			raise RuntimeError("module does not exist in environment: " + repr(route))
		package_file = route.file()

		packages, modules = route.tree()

		# Identify all system modules in project/context package.
		root_system_modules = []
		packages.append(route)

		for target in packages:
			tm = import_module(str(target))
			if isinstance(tm, ModuleType) and libfactor.composite(target):
				root_system_modules.append(cc.Factor(target, tm, None))

		# Controls process execution queue.
		ncpu = 2
		try:
			import psutil
			ncpu = psutil.cpu_count(logical=False) or 2
		except ImportError:
			pass

		ii = import_from_module(include)
		cxn = cc.Construction(
			ctx, simulations + root_system_modules,
			processors = max(8, ncpu),
			reconstruct = rebuild,
			# Age requirement based on global includes.
			requirement = cc.scan_modification_times(ii),
		)

		sector.dispatch(cxn)
		cxn.atexit(lambda cxn: set_exit_code(cxn, unit=sector.unit))

if __name__ == '__main__':
	sys.dont_write_bytecode = True
	from fault.io import command
	command.execute()
