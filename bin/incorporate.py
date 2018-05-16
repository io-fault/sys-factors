"""
# Incorporate the constructed factors for use by the system targeted by the Construction Context.

# This copies constructed files into a filesystem location that Python requires them
# to be in order for them to be used. For fabricated targets, this means placing
# bytecode compiles into (system/filename)`__pycache__` directories. For Python extension
# modules managed with composite factors, this means copying the constructed extension
# library into the appropriate package directory.
"""
import os
import sys

from .. import cc

from fault.system import libfactor
from fault.system import library as libsys
from fault.routes import library as libroutes

def adjust_link_target(target, incorporation):
	tid = target.identifier
	return target.container / '__f_cache__' / incorporation / tid

def adjust_bytecode_target(target, incorporation):
	return adjust_link_target(target.container.container / target.identifier, incorporation)

def main(inv:libsys.Invocation) -> libsys.Exit:
	"""
	# Induct the constructed targets.
	"""
	import_from_fullname = libroutes.Import.from_fullname

	args = inv.args
	env = os.environ

	rebuild = env.get('FPI_REBUILD', '0')
	ctx = cc.Context.from_environment()
	variants, mech = ctx.select('bytecode.python')

	rebuild = bool(int(rebuild))
	if rebuild:
		condition = cc.rebuild
	else:
		condition = cc.updated

	# collect packages to prepare from positional parameters
	roots = [import_from_fullname(x) for x in args]

	ctx_params = ctx.parameters.load('context')[-1]
	# Get prefix name.
	incorp = ctx_params.get('incorporation')
	slot = ctx_params.get('slot')
	if incorp:
		mkr = (lambda x: adjust_bytecode_target(libroutes.File.from_path(x), incorp))
	else:
		mkr = libroutes.File.from_path

	# Get the simulations for the bytecode files.
	for f in cc.gather_simulations(roots):
		refs = cc.references(f.dependencies())
		(sp, (fvariants, key, locations)), = f.link(variants, ctx, mech, refs, [])
		outdir = locations['integral']

		for src in f.sources():
			target = outdir / src.identifier
			perform, cf = cc.update_bytecode_cache(src, target, condition, mkr=mkr)
			if perform:
				cf.container.init('directory')
				cf.replace(target)
				sys.stderr.write("*! %s <- %s\n" %(str(cf), str(target)))

	# Python Extensions (factors) are composites which are package modules.
	candidates = []
	for route in roots:
		if not route.exists():
			raise RuntimeError("module does not exist in environment: " + repr(route))

		packages, modules = route.tree()
		candidates.extend(packages)
		del modules

	for route in candidates:
		factor = cc.Factor(route, None, None)
		domain = factor.domain
		m = ctx.select(domain)
		if m is None:
			if domain not in {'factor'}:
				sys.stderr.write("!* unknown domain: [%s] %s\n"% (str(factor), domain))
			continue
		tvars, tmech = m

		if libfactor.composite(route):
			# Primarily need the probe to select the proper build.
			refs = cc.references(factor.dependencies())

			for sp, l in factor.link(tvars, ctx, tmech, refs, []):
				vars, key, locations = l
				factor_dir = libfactor.incorporated(factor.route)
				if incorp:
					fdi = factor_dir.identifier
					factor_dir = (factor_dir.container / (incorp+':'+fdi))
				fp = factor.integral(key=key)

				sys.stderr.write("*! %s <- %s\n" %(str(factor_dir), str(fp)))
				factor_dir.replace(fp)

				if libfactor.python_extension(factor.module):
					target, src = cc.extension_link(factor.route, factor_dir)
					if incorp:
						# Special case when incorporation field is present.
						target = adjust_link_target(target, incorp)
						target.container.init('directory')
					target.link(src)
					sys.stderr.write("&! %s <- %s\n" %(str(target), str(src)))

	return inv.exit(0)

if __name__ == '__main__':
	libsys.control(main, libsys.Invocation.system())
