"""
Prepare the project by constructing factor targets of all the composite package modules
contained with the given set of package names.
"""
import os
import sys
import contextlib
import itertools
import py_compile
import functools
import collections
import types
import importlib.machinery
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

def main(role='optimal',
		mount_extensions=True,
		cache_from_source=importlib.util.cache_from_source
	):
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

	dont_write_bytecode = env.get('PYTHONDONTWRITEBYTECODE') == '1'
	reconstruct = env.get('FAULT_RECONSTRUCT') == '1'

	context_name = env.get('FAULT_CONTEXT') or None
	role = env.get('FAULT_ROLE', role) or role
	stack = contextlib.ExitStack()

	if role == 'optimal':
		opt = 2
	elif role in {'debug', 'test', 'metrics'}:
		# run asserts
		opt = 0
	else:
		# keep docstrings, but lose asserts
		opt = 1

	# collect packages to prepare from positional parameters
	roots = [
		libroutes.Import.from_fullname(x)
		for x in args
	]

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

		if not dont_write_bytecode:
			for x in itertools.chain(roots, packages, modules):
				xf = x.file()
				fp = str(xf)
				if not x.exists() or not fp.endswith('.py'):
					continue

				cache_file = libroutes.File.from_path(cache_from_source(fp, optimization=opt))
				if cache_file.exists():
					if cache_file.last_modified() > xf.last_modified():
						continue

				with status(str(x)):
					try:
						py_compile.compile(fp, optimize=opt, doraise=True)
						continue
					except py_compile.PyCompileError as err:
						exc = err.__context__
						exc.__traceback__ = None
					raise exc

		# Identify all system modules in project/context package.
		root_system_modules = []

		for target in packages:
			tm = importlib.import_module(str(target))
			if isinstance(tm, types.ModuleType) and libfactor.composite(target):
				root_system_modules.append((target, tm))

		if mount_extensions and role in {'optimal', 'debug'}:
			# Construct a separate list of Python extensions for subsequent mounting.
			exe_ctx_extensions = []

			# Collect extensions to be mounted into a package module.
			for target, tm in root_system_modules:
				for dm in tm.__dict__.values():
					if not isinstance(dm, types.ModuleType):
						continue
					# scan for module.context_extension_probe == True
					if getattr(dm, 'context_extension_probe', None):
						exe_ctx_extensions.append((target, tm))
		else:
			exe_ctx_extensions = ()

		for target, tm in exe_ctx_extensions:
			libconstruct.mount(role, target, tm)

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
			root_system_modules,
			processors=max(2, ncpu),
			reconstruct=reconstruct,
			# Age requirement based on global includes.
			requirement=max(x.last_modified() for x in files),
		)
		sector.dispatch(cxn)
		cxn.atexit(functools.partial(set_exit_code, unit=sector.unit))

if __name__ == '__main__':
	from ...io import libcommand
	libcommand.execute()
