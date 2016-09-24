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
import collections

from .. import library as libdev

from ...system import libfactor
from ...routes import library as libroutes
from ...io import library as libio

def main():
	"""
	Induct the constructed targets.
	"""
	import_from_fullname = libroutes.Import.from_fullname

	call = libio.context()
	sector = call.sector
	proc = sector.context.process

	args = proc.invocation.parameters['system']['arguments']
	env = proc.invocation.parameters['system'].get('environment')
	if not env:
		env = os.environ

	rebuild = env.get('FPI_REBUILD', '0')
	ctx = libdev.Context.from_environment()
	variants, mech = ctx.select('bytecode.python')

	rebuild = bool(int(rebuild))
	if rebuild:
		condition = libdev.rebuild
	else:
		condition = libdev.updated

	# collect packages to prepare from positional parameters
	roots = [import_from_fullname(x) for x in args]

	# Get the simulations for the bytecode files.
	for f in libdev.gather_simulations(roots):
		refs = libdev.references(f.dependencies())
		(sp, (fvariants, key, locations)), = f.link(variants, ctx, mech, refs, [])
		outdir = locations['integral']

		for src in f.sources():
			induct = outdir / src.identifier
			perform, cf = libdev.update_bytecode_cache(src, induct, condition)
			if perform:
				cf.replace(induct)
				print(str(induct), '->', cf)

	# Composites and Python Extensions
	candidates = []
	for route in roots:
		if not route.exists():
			raise RuntimeError("module does not exist in environment: " + repr(route))

		packages, modules = route.tree()
		candidates.extend(packages)

		del modules

	for route in candidates:
		factor = libdev.Factor(route, None, None)
		m = ctx.select(factor.type)
		if m is None:
			print('ignoring[unknown type]', str(factor))
			continue
		tvars, tmech = m

		if libfactor.composite(route):
			# Primarily need the probe to select the proper build.
			refs = libdev.references(factor.dependencies())

			for sp, l in factor.link(tvars, ctx, tmech, refs, []):
				vars, key, locations = l
				factor_dir = libfactor.inducted(factor.route)
				fp = factor.integral(key=key)

				print(str(fp), '->', str(factor_dir))
				factor_dir.replace(fp)

				if libfactor.python_extension(factor.module):
					link, src = libdev.link_extension(factor.route, factor_dir)
					print(str(src), '->', str(link))

	sector.unit.result = 0

if __name__ == '__main__':
	from ...io import libcommand
	libcommand.execute()
