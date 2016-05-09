"""
Prepare the project by constructing factor targets of all the &.library.Sources modules
contained within a package.
"""
import os
import sys
import contextlib
import itertools
import importlib.machinery

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

def mount(role, route, target, ext_suffixes=importlib.machinery.EXTENSION_SUFFIXES):
	# system.extension being built for this Python
	# construct links to optimal.
	# ece's use a special context derived from the Python install
	# usually consistent with the triplet of the first ext suffix.

	outfile = target.output(context=libconstruct.python_triplet, role=role)

	# peel until it's outside the first extensions directory.
	pkg = route
	while pkg.identifier != 'extensions':
		pkg = pkg.container
	names = route.absolute[len(pkg.absolute):]
	pkg = pkg.container

	link_target = pkg.file().container.extend(names)
	for suf in ext_suffixes:
		rmf = link_target.suffix(suf)
		if rmf.exists():
			print('removing', str(rmf))
			rmf.void()

	dsym = link_target.suffix('.so.dSYM')
	if dsym.exists():
		print('removing', str(dsym))
		dsym.void()

	link_target = link_target.suffix(ext_suffixes[0])
	print('linking', outfile, '->', link_target)
	link_target.link(outfile, relative=True)

def main(*args, role='optimal', mount_extensions=True):
	"""
	Prepare the entire package building factor targets and writing bytecode.
	"""
	dont_write_bytecode = os.environ.get('PYTHONDONTWRITEBYTECODE') == '1'
	reconstruct = os.environ.get('FAULT_RECONSTRUCT') == '1'
	role = os.environ.get('FAULT_ROLE', role) or role

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
				name = str(x)
				if name in sys.modules:
					# Primarily for cases where fault is preparing itself
					# and a dependency has been imported already.
					del sys.modules[name]

				with status(name):
					# TODO: Use py_compile module to build bytecode files.
					compiled = x.module()

		for target in packages:
			tm = target.module()
			if isinstance(tm, libdev.Sources):
				with status(str(target)):
					libconstruct.update(role, tm, reconstruct=reconstruct)

				if mount_extensions and getattr(tm, 'execution_context_extension', None):
					mount(role, target, tm)

if __name__ == '__main__':
	main(*sys.argv[1:])
