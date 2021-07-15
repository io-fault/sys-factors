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
from .. import cache

from fault.system import process
from fault.system import files
from fault.project import system as lsf

from fault.kernel import core as kcore
from fault.kernel import system as ksystem

from fault.time import sysclock
from fault.status import types as statustypes
from fault.status import frames as statusframes
from fault.transcript import frames as transcripts

class Application(kcore.Context):
	@property
	def cxn_work_directory(self):
		return self.cxn_product.route

	def __init__(self,
			channel,
			context, cache, product,
			projects, symbols,
			rebuild=0,
		):
		self.cxn_channel = channel
		self.cxn_cache = cache
		self.cxn_context = context
		self.cxn_product = product
		self.cxn_projects = projects
		self.cxn_local_symbols = symbols
		self.cxn_rebuild = rebuild
		self.cxn_extension_map = None
		self.cxn_log = transcripts.Log.stdout()

	@classmethod
	def from_command(Class, environ, arguments):
		ctxdir, cache_path, work, fpath, *symbols = arguments
		ctxdir = files.Path.from_path(ctxdir)
		work = files.Path.from_path(work)
		channel = environ.get('FRAMECHANNEL') or 'build'

		if environ.get('FPI_CACHE', 'persistent') == 'transient':
			cdi = cache.Transient(files.Path.from_path(cache_path))
		else:
			cdi = cache.Persistent(files.Path.from_path(cache_path))

		ctx = cc.Context.from_directory(ctxdir)
		rebuild = int((environ.get('FPI_REBUILD') or '0').strip())

		pd = lsf.Product(work)
		pd.load() #* .product/* files

		if fpath == '*':
			fpath = ''

		projects = itertools.chain.from_iterable(map(pd.select, [lsf.types.factor@fpath]))
		return Class(channel, ctx, cdi, pd, list(projects), symbols, rebuild=rebuild)

	def xact_void(self, final):
		"""
		# Called atexit in order to dispatch the next.
		"""

		try:
			nj = next(self.cxn_state)
			self.xact_dispatch(kcore.Transaction.create(nj))
		except StopIteration:
			# Success unless a crash occurs.
			self.cxn_log.flush()
			self.executable.exe_invocation.exit(0)

	def actuate(self):
		"""
		# Prepare the entire package building factor targets and writing bytecode.
		"""

		self._etime = sysclock.elapsed()
		p = statustypes.Parameters.from_nothing_v1()
		p['reference-time'] = int(sysclock.now())
		p['time-offset'] = int(self._etime)
		msg = statusframes.declaration(data=p)
		self.cxn_log.emit(self.cxn_channel, msg)
		self.cxn_log.flush()

		work = self.cxn_work_directory
		re = self.cxn_rebuild
		ctx = self.cxn_context

		# Project Context
		pctx = lsf.Context()
		rctx = lsf.Context.from_product_connections(pctx.connect(work))
		rctx.load() # Connection Project Index (requirements)
		pctx.load() # Build Project Index (targets)
		pctx.configure() # Protocol Configuration Inheritance.

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
			local_symbols[k] = list(options.parse(local_symbols[k]))

		seq = self.cxn_sequence = []
		for project_factor in self.cxn_projects:
			constraint = lsf.types.factor
			pj_id = self.cxn_product.identifier_by_factor(project_factor)[0]
			project = pctx.project(pj_id)

			# Resolve relative references to absolute while maintaining set/sequence.
			symbols = collections.ChainMap(local_symbols, pctx.symbols(project))
			targets = [
				core.Target(
					project, fp,
					ft, # factor-type
					{x: symbols[x] for x in fs[0]}, # requirements
					fs[1], # sources
					variants={'name':fp.identifier})
				for (fp, ft), fs in project.select(constraint)
			]

			seq.append(cc.Construction(
				self.cxn_channel,
				self._etime,
				self.cxn_log,
				self.cxn_cache,
				self.cxn_context,
				local_symbols,
				pctx,
				[pctx, rctx],
				project,
				targets,
				processors=16, # overcommit significantly
				reconstruct=re,
			))

		self.cxn_state = iter(seq)
		self.xact_void(None)

def main(inv:process.Invocation) -> process.Exit:
	inv.imports([
		'FPI_CACHE',
		'FPI_REBUILD',
		'FPI_MECHANISMS',
		'FACTORPATH',
		'FRAMECHANNEL',
	])

	cxn = Application.from_command(inv.environ, inv.argv)

	os.environ['OLDPWD'] = os.environ.get('PWD')
	os.environ['PWD'] = str(cxn.cxn_work_directory)
	os.chdir(os.environ['PWD'])

	ksystem.dispatch(inv, cxn)
	ksystem.control()

if __name__ == '__main__':
	sys.dont_write_bytecode = True
	process.control(main, process.Invocation.system())
