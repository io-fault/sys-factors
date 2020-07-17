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

from fault import routes
from fault.system import files

from fault.project.root import Product, Context
from fault.project import types as project_types

from fault.kernel import core as kcore
from fault.kernel import system as ksystem
from fault.transcripts import frames

class Log(object):
	"""
	# Abstraction for status frame logging.
	"""
	metrics = staticmethod(frames.metrics)
	from fault.status import frames
	from fault.time import sysclock

	_pack = frames.stdio()[1]
	Message = frames.types.Message
	Parameters = frames.types.Parameters

	def __init__(self, buffer, frequency=2, encoding='utf-8'):
		self.encoding = encoding
		self._buffer = buffer
		self._send = buffer.write
		self._flush = buffer.flush
		self._count = 0
		self._frequency = frequency

	def flush(self):
		self._count = 0
		self._flush()

	def transaction(self):
		self._count += 1
		if self._count > self._frequency:
			self.flush()

	def init(self):
		msg = self.frames.tty_notation_1_message
		p = self.frames.types.Parameters.from_nothing_v1()
		self._etime = self.sysclock.elapsed()
		p['reference-time'] = self.sysclock.now()
		p['time-offset'] = self._etime
		msg = self.frames.declaration(data=p)
		self._send(self._pack((None, msg)).encode(self.encoding))
		self.transaction()

	def time(self):
		return self.sysclock.elapsed().decrease(self._etime)

	def start_project(self, project, intention='unspecified'):
		self.root_channel = str(project.factor)

		p = project.information
		itxt = p.icon.get('emoji', '')
		msg = self.Message.from_string_v1(
			"transaction-started[->]: " + p.identifier + ' ' + 'factors',
			protocol=self.frames.protocol
		)
		self._send(self._pack((self.root_channel, msg)).encode(self.encoding))
		self.transaction()

	def finish_project(self, project):
		msg = self.Message.from_string_v1(
			"transaction-stopped[<-]: " + project.information.identifier,
			protocol=self.frames.protocol
		)
		msg.msg_parameters['data'] = self.Parameters.from_pairs_v1([
			('time-offset', int(self.time())),
		])

		self._send(self._pack((str(self.root_channel), msg)).encode(self.encoding))
		del self.root_channel
		self.transaction()

	def process_execute(self, factor, pid, synopsis, focus, command, logfile):
		start = int(self.time())
		channel = self.root_channel + '/' + str(factor) + '/system/' + str(pid)

		msg = self.Message.from_string_v1(
			"transaction-started[->]: " + synopsis + ' ' + focus,
			protocol=self.frames.protocol
		)
		msg.msg_parameters['data'] = self.Parameters.from_pairs_v1([
			('time-offset', start),
			('command', list(command)),
			('focus', str(focus)),
			('log', repr(logfile)[7:-2]),
		])

		self._send(self._pack((channel, msg)).encode(self.encoding))
		self.transaction()
		return start

	def _process_metrics(self, channel, time, rusage, exitcode):
		counts = {}
		if exitcode is None:
			counts['skipped'] = 1
		elif exitcode == 0:
			counts['finished'] = 1
		else:
			counts['failed'] = 1

		r = self.metrics(time, {'usage': rusage.ru_stime + rusage.ru_utime}, counts)
		msg = self.Message.from_string_v1(
			"transaction-event[--]: METRICS: system process",
			protocol=self.frames.protocol
		)
		msg.msg_parameters['data'] = r
		self._send(self._pack((channel, msg)).encode(self.encoding))

	def process_exit(self, factor, pid, synopsis, status, rusage, start_time):
		stop = int(self.time())
		channel = self.root_channel + '/' + str(factor) + '/system/' + str(pid)
		self._process_metrics(channel, stop - start_time, rusage, status)

		msg = self.Message.from_string_v1(
			"transaction-stopped[<-]: " + synopsis,
			protocol=self.frames.protocol
		)
		msg.msg_parameters['data'] = self.Parameters.from_pairs_v1([
			('time-offset', stop),
			('status', status),
			('system', rusage.ru_stime),
			('user', rusage.ru_utime),
		])

		self._send(self._pack((channel, msg)).encode(self.encoding))
		self.transaction()

	def write(self, text):
		self._send(text.encode(self.encoding))
		self.transaction()

	def warn(self, target, text):
		msg = self.Message.from_string_v1(
			"message-application[!#]: WARNING: " + text,
			protocol=self.frames.protocol
		)
		msg.msg_parameters['data'] = self.Parameters.from_pairs_v1([
			('time-offset', int(self.time())),
			('factor', str(target.route)),
		])

		self._send(self._pack((self.root_channel, msg)).encode(self.encoding))
		self.transaction()

class Application(kcore.Context):
	@property
	def cxn_work_directory(self):
		return self.cxn_product.route

	def __init__(self,
			context, cache, product,
			projects, symbols,
			domain='system',
			log=sys.stdout.buffer,
			rebuild=0,
		):
		self.cxn_cache = cache
		self.cxn_context = context
		self.cxn_product = product
		self.cxn_projects = projects
		self.cxn_local_symbols = symbols
		self.cxn_domain = domain
		self.cxn_log = Log(log)
		self.cxn_rebuild = rebuild
		self.cxn_extension_map = None

	@classmethod
	def from_command(Class, environ, arguments):
		ctxdir, cache_path, work, fpath, *symbols = arguments
		ctxdir = files.Path.from_path(ctxdir)
		work = files.Path.from_path(work)

		if environ.get('FPI_CACHE', 'persistent') == 'transient':
			cdi = cache.Transient(files.Path.from_path(cache_path))
		else:
			cdi = cache.Persistent(files.Path.from_path(cache_path))

		ctx = cc.Context.from_directory(ctxdir)
		rebuild = int((environ.get('FPI_REBUILD') or '0').strip())

		pd = Product(work)
		pd.load() #* .product/* files

		if fpath == '*':
			fpath = ''

		projects = itertools.chain.from_iterable(map(pd.select, [project_types.factor@fpath]))
		return Class(ctx, cdi, pd, list(projects), symbols, rebuild=rebuild)

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

		self.cxn_log.init()
		work = self.cxn_work_directory
		re = self.cxn_rebuild
		ctx = self.cxn_context

		# Stopgap for pre-language specification factors.
		self.cxn_extension_map = dict(
			(y[1], (y[0], set())) for y in [
				x.rsplit('.', 1) for x in
				os.environ.get('FACTORTYPES', 'python-module.py:chapter.txt').split(':')
			]
		)

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
				core.Target(
					pjo, fp,
					self.cxn_context.identify(ft),
					ft, # factor-type
					{x: symbols[x] for x in fs[0]},
					fs[1],
					variants={'name':fp.identifier})
				for (fp, ft), fs in pjo.select(constraint)
			]

			seq.append(cc.Construction(
				self.cxn_log,
				self.cxn_cache,
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
		'FPI_CACHE',
		'FPI_REBUILD',
		'FPI_MECHANISMS',
		'FACTORPATH',
	])

	cxn = Application.from_command(inv.environ, inv.args)

	os.environ['OLDPWD'] = os.environ.get('PWD')
	os.environ['PWD'] = str(cxn.cxn_work_directory)
	os.chdir(os.environ['PWD'])

	ksystem.dispatch(inv, cxn)
	ksystem.control()

if __name__ == '__main__':
	sys.dont_write_bytecode = True
	process.control(main, process.Invocation.system())
