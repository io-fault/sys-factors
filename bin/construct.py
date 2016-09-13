"""
Construct the targets of a package hierarchy for the selected context and role.
"""
import os
import sys
import types
import importlib.util

from .. import include # Minimum modification time.
from .. import libconstruct
from ...system import libfactor

from ...routes import library as libroutes
from ...chronometry import library as libtime
from ...io import library as libio

import_from_fullname = libroutes.Import.from_fullname
import_from_module = libroutes.Import.from_module

def set_exit_code(cxn, unit=None):
	"""
	Report the number of failures.
	"""
	# Restrict revealed count to 201. The exit code is rather small.
	unit.result = min(cxn.failures, 201)

def main():
	"""
	Prepare the entire package building factor targets and writing bytecode.
	"""
	call = libio.context()
	sector = call.sector
	proc = sector.context.process

	args = proc.invocation.parameters['system']['arguments']
	env = proc.invocation.parameters['system'].get('environment')
	if not env:
		env = os.environ

	rebuild = env.get('FPI_REBUILD') == '1'
	purpose = env.get('FPI_PURPOSE', 'debug')
	ctxname = env.get('FPI_CONTEXT', 'host')

	# collect packages to prepare from positional parameters
	roots = [import_from_fullname(x) for x in args]

	# Collect Python packages in the roots to build bytecode.
	simulations = []
	next_set = list(roots)
	while next_set:
		current_set = next_set
		next_set = []
		for pkg in current_set:
			mod, adds = libconstruct.simulate_composite(pkg)
			next_set.extend(adds)
			simulations.append(libconstruct.Factor(pkg, mod, None))

	for route, ref in zip(roots, args):
		if not route.exists():
			raise RuntimeError("module does not exist in environment: " + repr(route))
		package_file = route.file()

		packages, modules = route.tree()

		# Identify all system modules in project/context package.
		root_system_modules = []
		packages.append(route)

		for target in packages:
			tm = importlib.import_module(str(target))
			if isinstance(tm, types.ModuleType) and libfactor.composite(target):
				root_system_modules.append(libconstruct.Factor(target, tm, None))

		# Controls process execution queue.
		ncpu = 2
		try:
			import psutil
			ncpu = psutil.cpu_count(logical=False)
		except ImportError:
			pass

		ii = import_from_module(include)
		cxn = libconstruct.Construction(
			libconstruct.contexts(purpose, primary=ctxname),
			simulations + root_system_modules,
			processors = max(4, ncpu),
			reconstruct = rebuild,
			# Age requirement based on global includes.
			requirement = libconstruct.scan_modification_times(ii),
		)

		sector.dispatch(cxn)
		cxn.atexit(lambda cxn: set_exit_code(cxn, unit=sector.unit))

if __name__ == '__main__':
	sys.dont_write_bytecode = True
	from ...io import libcommand
	libcommand.execute()
