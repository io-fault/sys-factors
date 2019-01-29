"""
# Construct the targets of a package hierarchy for the selected context and role.
"""
import os
import sys
import functools

from .. import core
from .. import options
from .. import cc

from fault.system import process
from fault.system import files
from fault.routes import library as libroutes
from fault.time import library as libtime
from fault.io import library as libio

from fault.project import library as libproject
from fault.project import explicit

def local_include_factor(project:str, root:files.Path=(files.Path.from_absolute(__file__) ** 3)):
	include_dir = (root / project / 'include')
	src = include_dir / 'src'
	include_fc = libproject.factorcontext(libproject.identify_filesystem_context(include_dir))
	include_project = core.Project(
		include_fc,
		libproject.infrastructure(include_fc),
		libproject.information(include_fc),
	)

	ii = core.Target(
		include_project,
		libroutes.Segment(None, ('include',)),
		'source',
		'library',
		{},
		[src.__class__(src, (src>>x)[1]) for x in src.tree()[1]],
	)

	return ii

def mkconstruct(context, symbols, projects, work, root, project, fc, rebuild, domain='system'):
	assert libproject.enclosure(fc) == False # Resolved enclosure contents in the first pass.

	Segment = libroutes.Segment.from_sequence
	constraint = (project >> root)[1] # Path from project to factor selection.
	path = (work.extend(project).extend(constraint))
	factor = project.extend(constraint)

	context_name = getattr(fc.context, 'identifier', None)
	wholes, composites = explicit.query(path)
	wholes = dict(context.extrapolate(wholes.items()))

	# Resolve relative references to absolute while maintaining set/sequence.
	fc_infra = libproject.infrastructure(fc)
	info = libproject.information(fc)
	project = core.Project(fc, fc_infra, info)

	sr_composites = {
		k: (v[0] or domain, v[1], {x: cc.resolve(fc_infra, symbols, x) for x in v[2]}, v[3])
		for k, v in composites.items()
	}
	c_factors = [core.Target(project, Segment(k), *v) for k, v in sr_composites.items()]

	w_symbols = {}
	w_factors = [
		core.Target(project, Segment(k), v[0], v[1], w_symbols, *v[2:], variants={'name':k.identifier})
		for k, v in wholes.items()
	]

	return cc.Construction(
		context,
		symbols,
		projects,
		project,
		factor,
		w_factors + c_factors,
		processors = 16, # overcommit significantly
		reconstruct = rebuild,
	)

def continuation(sector, hold, iterator, processor):
	"""
	# Called atexit in order to dispatch the next.
	"""

	try:
		nj = next(iterator)
		sector.dispatch(nj)
		nj.atexit(functools.partial(continuation, sector, hold, iterator))
	except StopIteration:
		# Success unless a crash occurs.
		hold.terminate()
		hold.exit()
		unit = processor.unit
		unit.result = 0

def iomain(domain='system'):
	"""
	# Prepare the entire package building factor targets and writing bytecode.
	"""

	call = libio.context()
	sector = call.sector
	proc = sector.context.process

	args = proc.invocation.args
	env = os.environ

	rebuild = int(env.get('FPI_REBUILD', '0').strip())
	ctx = cc.Context.from_environment()
	work = files.Path.from_cwd()
	factor_paths = [work]

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

	local_symbols.update(ctx.symbols.items())

	# XXX: relocate symbols to context intialization
	local_symbols['fault:c-interfaces'] = [local_include_factor('posix'), local_include_factor('python')]

	hold = libio.Processor()
	sector.dispatch(hold)

	# Initial job.
	root, project, fc = roots[0]
	cxn = mkconstruct(ctx, local_symbols, project_index, work, root, project, fc, rebuild)
	sector.dispatch(cxn)

	# Chain subsequents.
	seq = [
		mkconstruct(ctx, local_symbols, project_index, work, root, project, fc, rebuild)
		for root, project, fc in roots[1:]
	]
	iseq = iter(seq)

	cxn.atexit(functools.partial(continuation, sector, hold, iseq))

def ioinit(unit):
	s = libio.Sector()
	s.subresource(unit)
	unit.place(s, "bin", "main")

	main_proc = libio.Call.partial(iomain)

	enqueue = unit.context.enqueue
	enqueue(s.actuate)
	enqueue(functools.partial(s.dispatch, main_proc))

def main(inv:process.Invocation) -> process.Exit:
	"""
	# ...
	"""

	import sdk.tools.python.bin.compile
	import sdk.tools.llvm.library
	import sdk.tools.host.library

	spr = libio.system.Process.spawn(inv, libio.Unit, {'command':(ioinit,)}, 'root')
	spr.boot(())

if __name__ == '__main__':
	sys.dont_write_bytecode = True
	process.control(main, process.Invocation.system())
