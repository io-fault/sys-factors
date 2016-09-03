"""
Construct the targets of a package hierarchy for the selected context and role.
"""
import os
import sys
import contextlib
import itertools
import functools
import collections
import types
import importlib.util

from .. import include
from .. import libconstruct

from ...system import libfactor
from ...routes import library as libroutes
from ...chronometry import library as libtime

@contextlib.contextmanager
def status(message):
	global libtime
	try:
		with libtime.clock.stopwatch() as elapsed:
			sys.stderr.write(message)
			sys.stderr.flush()
			yield None
	finally:
		duration = elapsed()
		seconds = duration.select('second')
		ms = duration.select('millisecond', 'second')
		sys.stderr.write(' ' + str(seconds) + '.' + str(ms) + 's\n')

def set_exit_code(cxn, unit=None):
	"""
	Report the number of failures.
	"""
	# Restrict revealed count to 201. The exit code is rather small.
	unit.result = min(cxn.failures, 201)

def main(role='optimal'):
	"""
	Prepare the entire package building factor targets and writing bytecode.
	"""
	from ...io import library as libio

	call = libio.context()
	sector = call.sector
	proc = sector.context.process

	args = proc.invocation.parameters['system']['arguments']
	env = proc.invocation.parameters['system'].get('environment')
	if not env:
		env = os.environ

	reconstruct = env.get('libfc_RECONSTRUCT') == '1'
	context_name = env.get('libfc_CONTEXT') or None
	role = env.get('libfc_ROLE', role) or role
	stack = contextlib.ExitStack()

	if role == 'optimal':
		opt = 2
	elif role in {'debug', 'test', 'metrics'}:
		# run asserts
		opt = 0
	else:
		# keep docstrings, but lose asserts/__debug__
		opt = 1

	# collect packages to prepare from positional parameters
	roots = [
		libroutes.Import.from_fullname(x)
		for x in args
	]

	simulations = []
	next_set = list(roots)
	while next_set:
		current_set = next_set
		next_set = []
		for pkg in current_set:
			mod, adds = libconstruct.simulate_composite(pkg)
			next_set.extend(adds)
			simulations.append((pkg, mod))

	for route, ref in zip(roots, args):
		if not route.exists():
			raise RuntimeError("module does not exist in environment: " + repr(route))
		package_file = route.file()

		if package_file is None:
			# Initialize the context package module if not available.

			# Resolve from Python's identified location?
			package_file = libroutes.File.from_path(ref)
			ctxroot = package_file / 'context' / 'root.py'
			if ctxroot.exists():
				# context project package.
				package_file = (package_file / '__init__.py')
				package_file.link(ctxroot)

		packages, modules = route.tree()

		# Identify all system modules in project/context package.
		root_system_modules = []

		for target in packages:
			tm = importlib.import_module(str(target))
			if isinstance(tm, types.ModuleType) and libfactor.composite(target):
				root_system_modules.append((target, tm))

		# Controls process execution queue.
		ncpu = 2
		try:
			import psutil
			ncpu = psutil.cpu_count(logical=False)
			ncpu = max(2, ncpu)
		except ImportError:
			pass

		# Get minimum (output) modification time from fault.development.include headers.
		include_route = libroutes.Import.from_fullname(include.__name__)
		dirs, files = libfactor.sources(include_route).tree()

		cxn = libconstruct.Construction(
			context_name, role,
			simulations + root_system_modules,
			processors=max(2, ncpu),
			reconstruct=reconstruct,
			# Age requirement based on global includes.
			requirement=max(x.get_last_modified() for x in files),
		)
		sector.dispatch(cxn)
		cxn.atexit(functools.partial(set_exit_code, unit=sector.unit))

if __name__ == '__main__':
	sys.dont_write_bytecode = True
	from ...io import libcommand
	libcommand.execute()
