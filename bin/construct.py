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
		routes.Segment(None, ('include',)),
		'source',
		'library',
		{},
		src.tree()[1],
	)

	return ii

class Application(kcore.Context):
	def __init__(self, work, factors, symbols, domain='system'):
		self.cxn_work_dir = work # Product Directory
		self.cxn_factors = factors
		self.cxn_local_symbols = symbols
		self.cxn_domain = domain

	@classmethod
	def from_command(Class, arguments):
		work, factors, *symbols = arguments
		work = files.Path.from_absolute(work)
		return Class(work, [factors], symbols)

	def mkconstruct(self, symbols, projects, work, root, project, fc, rebuild, constraint=None):
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

		self.cxn_log = sys.stdout
		env = os.environ

		rebuild = int(env.get('FPI_REBUILD', '0').strip())
		ctx = self.cxn_context = cc.Context.from_environment()

		work = self.cxn_work_dir
		w = env['PWD'] = str(work)
		os.chdir(w)

		factor_paths = [work] + [
			files.Path.from_absolute(x) for x in env.get('FACTORPATH', '').split(':')
		]

		# Collect the index for each directory.
		project_index = {}
		for dirr in factor_paths:
			tc = (dirr / 'project-index.txt')
			if tc.fs_type() == 'void':
				continue

			tc = tc.get_text_content().split()
			project_index[dirr] = dict(zip(tc[1::2], tc[0::2]))
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
		cxn = self.mkconstruct(local_symbols, project_index, work, root, project, fc, rebuild)
		self.xact_dispatch(kcore.Transaction.create(cxn))

		# Chain subsequents.
		seq = self.cxn_sequence = [
			self.mkconstruct(local_symbols, project_index, work, root, project, fc, rebuild)
			for root, project, fc in roots[1:]
		]
		self.cxn_state = iter(seq)

def main(inv:process.Invocation) -> process.Exit:
	inv.imports([
		'FPI_REBUILD',
		'FACTORPATH',
	])
	ksystem.dispatch(inv, Application.from_command(inv.args))
	ksystem.control()

if __name__ == '__main__':
	sys.dont_write_bytecode = True
	process.control(main, process.Invocation.system())
