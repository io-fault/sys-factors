"""
# Construct the targets of a package hierarchy for the selected context and role.
"""
import os
import sys
import functools

from .. import core
from .. import options
from .. import cc

from fault import routes
from fault.system import files

from fault.kernel import core as kcore
from fault.kernel import system as ksystem

from fault.project import library as libproject
from fault.project import explicit
from fault.project import polynomial

from fault.system import process

def local_include_factor(project:str, root:files.Path=(files.Path.from_absolute(__file__) ** 3)):
	include_dir = (root / project / 'include')
	src = (include_dir / 'src').delimit()
	include_fc = libproject.factorcontext(libproject.identify_filesystem_context(include_dir))
	include_project = core.Project(
		include_fc,
		libproject.infrastructure(include_fc),
		libproject.information(include_fc),
	)

	ii = core.Target(
		include_project,
		libproject.factor@'include',
		'source',
		'library',
		{},
		src.tree()[1],
	)

	return ii

class Application(kcore.Context):
	def __init__(self, context, work, factors, symbols, domain='system', log=sys.stdout, rebuild=0):
		self.cxn_context = context
		self.cxn_work_dir = work # Product Directory
		self.cxn_factors = factors
		self.cxn_local_symbols = symbols
		self.cxn_domain = domain
		self.cxn_log = log
		self.cxn_rebuild = rebuild

	@classmethod
	def from_command(Class, environ, arguments):
		ctx = cc.Context.from_environment(environ)
		rebuild = int((environ.get('FPI_REBUILD') or '0').strip())
		work, factors, *symbols = arguments
		work = files.Path.from_absolute(work)
		return Class(ctx, work, [factors], symbols, rebuild=rebuild)

	def mkconstruct(self, symbols, projects, work, root, project, fc, constraint=None, rebuild=0):
		assert fc.enclosure == False # Resolved enclosure contents in the first pass.

		if constraint is None:
			constraint = root.segment(project)

		path = work//project//constraint
		factor = project//constraint

		ctx = self.cxn_context

		# Construction Context designated filename extensions.
		extmap = {
			k: (v, t, set())
			for k, v, t in [
				(k, v, ctx.default_type(v))
				for k, v in ctx._languages.items()
			]
			if t is not None
		}

		# XXX: Resolve protocol based on identified project index.
		protocol = polynomial.V1({'source-extension-map': extmap})

		# Resolve relative references to absolute while maintaining set/sequence.
		infra = protocol.infrastructure(fc)
		info = protocol.information(fc)
		ctx_project = core.Project(fc, infra, info)

		targets = [
			core.Target(ctx_project, segment,
				fs[0] or self.cxn_domain,
				fs[1], # factor-type
				{x: cc.resolve(infra, symbols, x) for x in fs[2]},
				fs[3],
				variants={'name':segment.identifier})
			for segment, fs in protocol.iterfactors(path)
		]

		return cc.Construction(
			self.cxn_log,
			self.cxn_context,
			symbols,
			projects,
			ctx_project,
			factor,
			targets,
			processors = 16, # overcommit significantly
			reconstruct = rebuild,
		)

	def xact_void(self, final):
		"""
		# Called atexit in order to dispatch the next.
		"""

		try:
			nj = next(self.cxn_state)
			self.xact_dispatch(kcore.Transaction.create(nj))
		except StopIteration:
			# Success unless a crash occurs.
			self.executable.exe_invocation.exit(0)

	def actuate(self):
		"""
		# Prepare the entire package building factor targets and writing bytecode.
		"""

		from fault.project.core import factor
		work = self.cxn_work_dir
		ctx = self.cxn_context
		re = self.cxn_rebuild

		factor_paths = [work] + [
			files.Path.from_absolute(x) for x in os.environ.get('FACTORPATH', '').split(':')
		]

		# Collect the index for each directory.
		project_index = {}
		for dirr in factor_paths:
			tc = (dirr / 'project-index.txt')
			if tc.fs_type() == 'void':
				continue

			tc = tc.get_text_content().split()
			project_index[dirr] = dict(zip(tc[1::2], [factor@x for x in tc[0::2]]))
		project_index = libproject.FactorSet(project_index)

		# collect packages to prepare from positional parameters
		rsegments = [libproject.factorsegment(x) for x in self.cxn_factors]

		# Join root segment with projects.
		roots = []
		for x in rsegments:
			for y in libproject.tree(work, x):
				roots.append((x,)+y)

		# Separate options into named slots.
		local_symbols = {}
		selection = None
		for x in self.cxn_local_symbols:
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

		self.cxn_log.write("[<> construct %s]\n" %(str(self.cxn_factors[0]),))

		# Initial job.
		root, project, fc = roots[0]
		cxn = self.mkconstruct(local_symbols, project_index, work, root, project, fc, rebuild=re)
		self.xact_dispatch(kcore.Transaction.create(cxn))

		# Chain subsequents.
		seq = self.cxn_sequence = [
			self.mkconstruct(local_symbols, project_index, work, root, project, fc, rebuild=re)
			for root, project, fc in roots[1:]
		]
		self.cxn_state = iter(seq)

def main(inv:process.Invocation) -> process.Exit:
	inv.imports([
		'FPI_REBUILD',
		'FPI_MECHANISMS',
		'FACTORPATH',
		'CONTEXT',
	])

	cxn = Application.from_command(inv.environ, inv.args)

	os.environ['OLDPWD'] = os.environ.get('PWD')
	os.environ['PWD'] = str(cxn.cxn_work_dir)
	os.chdir(os.environ['PWD'])

	ksystem.dispatch(inv, cxn)
	ksystem.control()

if __name__ == '__main__':
	sys.dont_write_bytecode = True
	process.control(main, process.Invocation.system())
