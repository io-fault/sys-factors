"""
# Construct the targets of a package hierarchy for the selected context and role.
"""
import os
import sys
import functools

from .. import options
from .. import cc

from fault.system import libfactor
from fault.system import files

from fault.routes import library as libroutes
from fault.time import library as libtime
from fault.io import library as libio

from fault.project import library as libproject
from fault.project import explicit

def set_exit_code(project, unit, cxn):
	"""
	# Report failure and not exit status.
	"""
	fcount = cxn.failures
	segstr = '.'.join(project)

	sys.stderr.write("#! SUMMARY: In %s, %d factor processing instructions failed.\n" %(segstr, fcount,))

	if fcount:
		unit.result = 70 # EX_SOFTWARE
	else:
		unit.result = 0

def main(domain='system'):
	"""
	# Prepare the entire package building factor targets and writing bytecode.
	"""

	# Compensate for what appears to be parsing bug in Python.
	# When loaded by the task queue thread, the module import would
	# SIGSEGV.
	import sdk.tools.llvm.library
	import sdk.tools.host.apple
	import sdk.tools.host.elf

	Segment = libroutes.Segment.from_sequence
	call = libio.context()
	sector = call.sector
	proc = sector.context.process

	args = proc.invocation.args
	env = os.environ

	rebuild = int(env.get('FPI_REBUILD', '0').strip())
	ctx = cc.Context.from_environment()
	factor_paths = [files.Path.from_absolute(x) for x in env.get('FACTORPATH', '').split(':') if x.strip()]
	work = files.Path.from_cwd()

	if work not in factor_paths:
		factor_paths.append(work)

	# Collect the index for each directory.
	project_index = {}
	for dirr in factor_paths:
		tc = (dirr / 'project-index.txt')
		if not tc.exists():
			continue

		tc = tc.get_text_content().split()
		project_index[dirr] = dict(zip(tc[1::2], tc[0::2]))
	project_index = libproject.FactorSet(project_index)

	# collect packages to prepare from positional parameters
	rsegments = [libproject.factorsegment(x) for x in args[:1]]

	# Join root segment with projects.
	roots = []
	for x in rsegments:
		for y in libproject.tree(work, x):
			roots.append((x,)+y)

	# Separate options into named slots.
	local_symbols = {}
	selection = None
	for x in args[1:]:
		if x[:1] != '-':
			selection = local_symbols[x] = []
		else:
			selection.append(x)

	# Parse options for each slot.
	for k in list(local_symbols):
		local_symbols[k] = options.parse(local_symbols[k])

	# Merge?
	local_symbols.update(ctx.symbols.items())

	include_dir = ((files.Path.from_absolute(__file__) ** 2) / 'include')
	src = include_dir/'src'
	include_fc = libproject.factorcontext(libproject.identify_filesystem_context(include_dir))
	include_project = cc.Project(
		include_fc,
		libproject.infrastructure(include_fc),
		libproject.information(include_fc),
	)

	ii = cc.Target(
		include_project,
		libroutes.Segment(None, ('include',)),
		'source',
		'library',
		{},
		[src.__class__(src, (src>>x)[1]) for x in src.tree()[1]],
	)
	local_symbols['fault:c-interfaces'] = [ii]

	for root, project, fc in roots:
		assert libproject.enclosure(fc) == False # Resolved enclosure contents in the first pass.

		constraint = (project >> root)[1] # Path from project to factor selection.
		path = (work.extend(project).extend(constraint))
		factor = project.extend(constraint)

		context_name = getattr(fc.context, 'identifier', None)
		wholes, composites = explicit.query(path)
		wholes = dict(ctx.extrapolate(wholes.items()))

		# Resolve relative references to absolute while maintaining set/sequence.
		fc_infra = libproject.infrastructure(fc)
		info = libproject.information(fc)
		project = cc.Project(fc, fc_infra, info)

		sr_composites = {
			k: (v[0] or domain, v[1], {x: cc.resolve(fc_infra, local_symbols, x) for x in v[2]}, v[3])
			for k, v in composites.items()
		}
		c_factors = [cc.Target(project, Segment(k), *v) for k, v in sr_composites.items()]

		w_symbols = {}
		w_factors = [
			cc.Target(project, Segment(k), v[0], v[1], w_symbols, *v[2:], variants={'name':k.identifier})
			for k, v in wholes.items()
		]

		# Controls process execution queue.
		ncpu = 2
		cxn = cc.Construction(
			ctx,
			local_symbols,
			project_index,
			project,
			factor,
			w_factors + c_factors,
			ii,
			processors = max(8, ncpu),
			reconstruct = rebuild,
		)

		sector.dispatch(cxn)
		sec = functools.partial(set_exit_code, project.segment.absolute, sector.unit)
		cxn.atexit(sec)

if __name__ == '__main__':
	sys.dont_write_bytecode = True
	from fault.io import command
	command.execute()
