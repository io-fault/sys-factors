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
import types
import importlib.util

from .. import libconstruct
from .. import library as libdev

from ...system import libfactor
from ...routes import library as libroutes

import_from_fullname = libroutes.Import.from_fullname
cache_from_source = importlib.util.cache_from_source

def update_cache(src, induct, condition=libconstruct.updated, mkr=libroutes.File.from_path) -> bool:
	"""
	Update the cached Python bytecode file using the inducted simulated factors.
	"""

	fp = str(src)
	if not src.exists() or not fp.endswith('.py'):
		return (False, 'source does not exist or does not end with ".py"')

	cache_file = mkr(cache_from_source(fp, optimization=None))

	if condition((cache_file,), (induct,)):
		return (False, 'update condition was not present')

	cache_file.replace(induct)
	return (True, cache_file)

def main():
	"""
	Induct the constructed targets.
	"""
	from ...io import library as libio

	call = libio.context()
	sector = call.sector
	proc = sector.context.process

	args = proc.invocation.parameters['system']['arguments']
	env = proc.invocation.parameters['system'].get('environment')
	if not env:
		env = os.environ

	rebuild = env.get('FPI_REBUILD', '0')
	contexts = libconstruct.contexts(env.get('FPI_PURPOSE', 'debug'), environment=env.get('FPI_CONTEXT_DIRECTORY', ()))

	rebuild = bool(int(rebuild))
	if rebuild:
		condition = libconstruct.reconstruct
	else:
		condition = libconstruct.updated

	# collect packages to prepare from positional parameters
	roots = [import_from_fullname(x) for x in args]

	# Get the simulations for the bytecode files.
	for mech, ctx in libconstruct.gather_simulations(contexts, roots):
		mod = ctx['module']
		outdir = ctx['locations']['reduction']

		for src in mod.__factor_sources__:
			implement = outdir / src.identifier
			uc_report = update_cache(src, implement, condition=condition)
			if uc_report[0]:
				print(str(implement), '->', uc_report[1])

	# Composites and Python Extensions
	candidates = []
	for route in roots:
		if not route.exists():
			raise RuntimeError("module does not exist in environment: " + repr(route))

		packages, modules = route.tree()
		candidates.extend(packages)

		del modules

	for target in candidates:
		tm = importlib.import_module(str(target))

		if isinstance(tm, types.ModuleType) and libfactor.composite(target):
			if tm.__factor_dynamics__ == 'interfaces':
				continue
			mech, fp, *ignored = libconstruct.initialize(contexts, tm, list(libconstruct.collect(tm)))
			variants = fp['variants']

			factor_dir = libfactor.inducted(target)
			fp = libconstruct.reduction(target, variants)

			print(str(fp), '->', str(factor_dir))
			factor_dir.replace(fp)

			if libfactor.python_extension(tm):
				link, src = libconstruct.link_extension(target, factor_dir)
				print(str(src), '->', str(link))

	sector.unit.result = 0

if __name__ == '__main__':
	from ...io import libcommand
	libcommand.execute()
