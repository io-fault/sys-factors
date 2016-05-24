"""
Prepare the project by constructing factor targets of all the &.library.Sources modules
contained within a package.
"""
import os
import sys
import contextlib
import itertools
import py_compile
import importlib.machinery
import functools
import collections

from .. import libconstruct
from .. import library as libdev

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
		sys.stderr.write(' ' + str(seconds) + '.' + str(ms) + '\n')

def main(sector, role='optimal', mount_extensions=True):
	"""
	Prepare the entire package building factor targets and writing bytecode.
	"""
	proc = sector.context.process
	args = proc.invocation.parameters['system']['arguments']
	env = proc.invocation.parameters['system'].get('environment')
	if not env:
		env = os.environ

	dont_write_bytecode = env.get('PYTHONDONTWRITEBYTECODE') == '1'
	reconstruct = env.get('FAULT_RECONSTRUCT') == '1'

	role = env.get('FAULT_ROLE', role) or role
	stack = contextlib.ExitStack()

	# collect packages to prepare from positional parameters
	roots = [
		libroutes.Import.from_fullname(x)
		for x in args
	]

	for route in roots:
		packages, modules = route.tree()

		if not dont_write_bytecode:
			del os.environ['PYTHONDONTWRITEBYTECODE']
			sys.dont_write_bytecode = False

			for x in itertools.chain(roots, packages, modules):
				with status(str(x)):
					fp = str(x.file())
					if fp.endswith('.py'):
						py_compile.compile(fp)

		# Identify all system modules in project/context package.
		root_system_modules = []

		for target in packages:
			tm = importlib.import_module(str(target))
			if isinstance(tm, libdev.Sources) and getattr(tm, 'constructed', None):
				# libdev.Sources and is identified as being constructed.
				root_system_modules.append((target, tm))

		if mount_extensions:
			# Construct a separate list of Python extensions for subsequent mounting.
			exe_ctx_extensions = []

			# Collect extensions to be mounted into a package module.
			for target, tm in root_system_modules:
				if getattr(tm, 'execution_context_extension', None):
					exe_ctx_extensions.append((target, tm))
		else:
			exe_ctx_extensions = ()

		for target, tm in exe_ctx_extensions:
			libconstruct.mount(role, target, tm)

		cxn = libconstruct.Construction(None, root_system_modules)
		sector.dispatch(cxn)

if __name__ == '__main__':
	from ...io import libcommand
	libcommand.execute()
