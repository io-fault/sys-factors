"""
# Construct the targets of a package hierarchy for the selected context and role.
"""
import os
import sys
import itertools
import collections

from .. import core
from .. import options
from .. import cc

from fault.system import process

from fault import routes
from fault.system import files

from fault.project.root import Product, Context
from fault.project import types as project_types

from fault.kernel import core as kcore
from fault.kernel import system as ksystem

class Application(kcore.Context):
	@property
	def cxn_work_directory(self):
		return self.cxn_product.route

	def __init__(self,
			context, product,
			projects, symbols,
			domain='system',
			log=sys.stdout,
			rebuild=0,
		):
		self.cxn_context = context
		self.cxn_product = product
		self.cxn_projects = projects
		self.cxn_local_symbols = symbols
		self.cxn_domain = domain
		self.cxn_log = log
		self.cxn_rebuild = rebuild
		self.cxn_extension_map = None

	@classmethod
	def from_command(Class, environ, arguments):
		ctx = cc.Context.from_environment(environ)
		rebuild = int((environ.get('FPI_REBUILD') or '0').strip())
		work, fpath, *symbols = arguments
		work = files.Path.from_absolute(work)

		pd = Product(work)
		pd.load() #* .product/* files

		if fpath == '*':
			fpath = ''

		projects = itertools.chain.from_iterable(map(pd.select, [project_types.factor@fpath]))
		return Class(ctx, pd, list(projects), symbols, rebuild=rebuild)

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

		work = self.cxn_work_directory
		re = self.cxn_rebuild
		ctx = self.cxn_context

		# Construction Context designated filename extensions.
		self.cxn_extension_map = {
			k: (v, t, set())
			for k, v, t in [
				(k, v, ctx.default_type(v))
				for k, v in ctx._languages.items()
			]
			if t is not None
		}

		# Project Context
		pctx = Context()
		factor_paths = [work] + [
			files.Path.from_absolute(x)
			for x in os.environ.get('CONNECTIONS', '').split(':')
		]
		for x in factor_paths:
			if x != files.root and x.fs_type() == 'directory':
				pctx.connect(x)

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

		self.cxn_log.write("[<> construct %s]\n" %(str(self.cxn_projects[0]),))

		seq = self.cxn_sequence = []
		for project in self.cxn_projects:
			constraint = project_types.factor
			pj_id = self.cxn_product.identifier_by_factor(project)[0]
			pjo = pctx.project(pj_id)
			pjo.protocol.parameters.update({
				'source-extension-map': self.cxn_extension_map,
			})

			# Resolve relative references to absolute while maintaining set/sequence.
			symbols = collections.ChainMap(local_symbols, pctx.symbols(pjo))
			targets = [
				core.Target(pjo, fp,
					fs[0] or self.cxn_domain,
					fs[1], # factor-type
					{x: symbols[x] for x in fs[2]},
					fs[3],
					variants={'name':fp.identifier})
				for fp, fs in pjo.select(constraint)
			]

			seq.append(cc.Construction(
				self.cxn_log,
				self.cxn_context,
				local_symbols,
				pctx,
				pjo,
				targets,
				processors=16, # overcommit significantly
				reconstruct=re,
			))

		self.cxn_state = iter(seq)
		self.xact_void(None)

def main(inv:process.Invocation) -> process.Exit:
	inv.imports([
		'FPI_REBUILD',
		'FPI_MECHANISMS',
		'FACTORPATH',
		'CONTEXT',
	])

	cxn = Application.from_command(inv.environ, inv.args)

	# Add the context local support product.
	ctxdir = files.Path.from_path(inv.environ['CONTEXT'])
	support = ctxdir/'local'
	if support.fs_type() == 'directory':
		if 'FACTORPATH' in os.environ:
			os.environ['FACTORPATH'] += ':' + str(support)
		else:
			os.environ['FACTORPATH'] = str(support)

	os.environ['OLDPWD'] = os.environ.get('PWD')
	os.environ['PWD'] = str(cxn.cxn_work_directory)
	os.chdir(os.environ['PWD'])

	ksystem.dispatch(inv, cxn)
	ksystem.control()

if __name__ == '__main__':
	sys.dont_write_bytecode = True
	process.control(main, process.Invocation.system())
