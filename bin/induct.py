"""
Induct the constructed targets of the configured construction context.

This copies constructed files into a filesystem location that Python requires them
to be in order for them to be used. For fabricated targets, this means placing
bytecode compiles into (system:filename)`__pycache__` directories. For Python extension
modules managed with composite factors, this means copying the constructed extension
library into the appropriate package directory.
"""
import os
import sys
import contextlib
import itertools
import functools
import collections
import types
import importlib.util

from .. import libconstruct
from ...system import libfactor
from ...routes import library as libroutes

cache_from_source=importlib.util.cache_from_source

def update_cache(opt, src, implement, condition=libconstruct.updated, mkr=libroutes.File.from_path) -> bool:
	"""
	Update the cached Python bytecode file with the given &opt, optimization,
	and for the given &src, Python module file path, using the &implement as
	the new bytecode file to use.

	[ Returns ]
	/&bool
		Whether the cache file was updated.
	"""
	global cache_from_source

	fp = str(src)
	if not src.exists() or not fp.endswith('.py'):
		return (False, 'source does not exist or does not end with ".py"')

	# Validate that the links are installed for single pyc config.
	off_opt = mkr(cache_from_source(fp, optimization=0))
	one_opt = mkr(cache_from_source(fp, optimization=1))
	two_opt = mkr(cache_from_source(fp, optimization=2))

	cache_file = mkr(cache_from_source(fp, optimization=None))
	# Update local links.
	off_opt.link(cache_file)
	two_opt.link(cache_file)
	one_opt.link(cache_file)

	if condition((cache_file,), (implement,)):
		return (False, 'update condition was not present')

	cache_file.replace(implement)
	return (True, cache_file)

def main(role='optimal'):
	"""
	Implement the constructed targets.
	"""
	from ...io import library as libio

	call = libio.context()
	sector = call.sector
	proc = sector.context.process

	args = proc.invocation.parameters['system']['arguments']
	env = proc.invocation.parameters['system'].get('environment')
	if not env:
		env = os.environ

	context_name = env.get('libfc_CONTEXT') or None
	role = env.get('libfc_ROLE', role) or role

	reconstruct = env.get('libfc_RECONSTRUCT', '0')
	reconstruct = bool(int(reconstruct))
	if reconstruct:
		condition = libconstruct.reconstruct
	else:
		condition = libconstruct.updated

	if role == 'optimal':
		opt = 2
	else:
		opt = 0

	# collect packages to prepare from positional parameters
	roots = [
		libroutes.Import.from_fullname(x)
		for x in args
	]

	# Get the simulations for the bytecode files.
	simulations = []
	next_set = list(roots)
	while next_set:
		current_set = next_set
		next_set = []
		for pkg in current_set:
			mod, adds = libconstruct.simulate_composite(pkg)
			next_set.extend(adds)

			outdir = libfactor.cache_directory(mod, libfactor.bytecode_triplet, role, 'out')
			outdir = outdir / 'pyc'
			for src in mod.__factor_sources__:
				implement = outdir / src.identifier
				uc_report = update_cache(opt, src, implement, condition=condition)
				if uc_report[0]:
					print(str(implement), '->', uc_report[1])

	if role not in {'optimal', 'debug'}:
		return

	for route in roots:
		if not route.exists():
			raise RuntimeError("module does not exist in environment: " + repr(route))

		packages, modules = route.tree()
		del modules

		# Filter packages. Find composites.
		root_system_modules = []
		for target in packages:
			tm = importlib.import_module(str(target))
			if isinstance(tm, types.ModuleType) and libfactor.composite(target):
				root_system_modules.append((target, tm))

		exe_ctx_extensions = []

		# Collect extensions to be mounted into a package module.
		for target, tm in root_system_modules:
			for dm in tm.__dict__.values():
				if not isinstance(dm, types.ModuleType):
					continue
				# scan for module.context_extension_probe == True
				if getattr(dm, 'context_extension_probe', None):
					exe_ctx_extensions.append((target, tm))

		for target, tm in exe_ctx_extensions:
			libconstruct.mount(role, target, tm, condition=condition)

	sector.unit.result = 0

if __name__ == '__main__':
	from ...io import libcommand
	libcommand.execute()
