"""
# Software Construction Context implementation in Python.
"""
import os
import sys
import functools
import collections
import contextlib
import typing

from fault.context import tools
from fault.time import sysclock
from fault.system import execution as libexec
from fault.system import files
from fault.internet import ri

from fault.kernel import core as kcore
from fault.kernel import dispatch as kdispatch

from . import graph
from . import core
from . import v1

Context=v1.Context

@tools.cachedcalls(8)
def work_key_cache(prefix, variants):
	key = prefix
	# Using slashes as separators as they should not
	# be present in the values for filesystem safety.
	key += '/i=' + variants.intention
	key += '/s=' + variants.system
	key += '/a=' + variants.architecture
	key += '/f=' + variants.form
	return key

def work(variants, name, /, encoding='utf-8'):
	key = work_key_cache('fpi-work', variants) + '/N=' + name
	return key.encode(encoding)

def rebuild(outputs, inputs, subfactor=True, cascade=False):
	"""
	# Unconditionally report the &outputs as outdated.
	"""
	if cascade is False and subfactor is False:
		# If rebuild is selected, &cascade must be enabled in order
		# for out-of-selection factors to be rebuilt.
		return True

	return False

def updated(outputs, inputs, never=False, cascade=False, subfactor=True):
	"""
	# Return whether or not the &outputs are up-to-date.

	# &False returns means that the target should be reconstructed,
	# and &True means that the file is up-to-date and needs no processing.
	"""

	if never:
		# Never up-to-date.
		if cascade:
			# Everything gets refreshed.
			return False
		elif subfactor:
			# Subfactor inherits never regardless of cascade.
			return False

	olm = None
	for output in outputs:
		if output.fs_type() == 'void':
			# No such object, not updated.
			return False
		lm = output.fs_status().system.st_mtime
		olm = min(lm, olm or lm)

	# Otherwise, check the inputs against outputs.
	# In the case of a non-cascading rebuild, it is desirable
	# to perform the input checks.

	for x in inputs:
		if x.fs_type() == 'void' or x.fs_status().system.st_mtime > olm:
			# rebuild if any output is older than any source.
			return False

	# object has already been updated.
	return True

def interpret_reference(cc, ctxpath, _factor, symbol, reference, rreqs={}, rsources=[]):
	"""
	# Extract the project identifier from the &url and find a corresponding project.

	# The fragment portion of the URL specifies the factor within the project
	# that should be connected in order to use the &symbol.
	"""
	if reference.method in {'type', 'control'}:
		# Virtual factors.
		return

	i = ri.parse(reference.project)
	fpath = reference.factor
	rproject_name = i['path'][-1]

	i['path'][-1] = '' # Force the trailing slash in serialize()
	product = ri.serialize(i)

	id = product + rproject_name
	for ctx in ctxpath:
		try:
			pj = ctx.project(id) #* No project in path.
		except LookupError:
			pass
		else:
			break
	else:
		raise Exception("could not find %s project in contexts" %(id,))

	for record in pj.select(fpath.container):
		fp = record[0][0]
		if fp.identifier == fpath.identifier:
			((fp, ft), (fsyms, fsrcs)) = record
			fts = str(ft)
			yield core.Target(
				pj, fp, fts, rreqs, rsources,
				method=reference.method)

def requirements(cc, ctxpath, symbols, factor):
	"""
	# Return the set of factors that is required to build this Target, &factor.
	"""

	for sym, refs in factor.symbols.items():
		if sym in symbols:
			yield from symbols[sym]
			continue

		for r in refs:
			if isinstance(r, (core.Target, core.SystemFactor)):
				yield r
			else:
				yield from interpret_reference(cc, ctxpath, factor, sym, r)

# Status Frames
from fault.transcript import frames
from fault.status.frames import protocol as frames_protocol

def open_project_transaction(time, project, intention='unspecified', channel=''):
	p = project.information
	itxt = p.icon.get('emoji', '')
	msg = frames.types.Message.from_string_v1(
		"transaction-started[->]: " + p.identifier + ' ' + 'factors',
		protocol=frames_protocol
	)
	msg.msg_parameters['data'] = frames.types.Parameters.from_pairs_v1([
		('time-offset', time),
	])

	return channel + '/' + str(project.factor), msg

def close_project_transaction(time, project, channel=''):
	msg = frames.types.Message.from_string_v1(
		"transaction-stopped[<-]: " + project.information.identifier,
		protocol=frames_protocol
	)
	msg.msg_parameters['data'] = frames.types.Parameters.from_pairs_v1([
		('time-offset', time),
	])

	return channel + '/' + str(project.factor), msg

def open_process_transaction(time, factor, pid, synopsis, focus, command, logfile):
	msg = frames.types.Message.from_string_v1(
		"transaction-started[->]: " + synopsis + ' ' + focus,
		protocol=frames.protocol
	)
	msg.msg_parameters['data'] = frames.types.Parameters.from_pairs_v1([
		('time-offset', time),
		('factor', str(factor)),
		('command', list(str(x) for x in command)),
		('focus', str(focus)),
		('log', str(logfile)),
	])
	return msg

def close_process_transaction(time, pid, synopsis, status, rusage):
	msg = frames.types.Message.from_string_v1(
		"transaction-stopped[<-]: " + synopsis,
		protocol=frames_protocol
	)
	msg.msg_parameters['data'] = frames.types.Parameters.from_pairs_v1([
		('time-offset', time),
		('status', status),
	])
	return msg

def process_metrics_signal(time, exit_type, rusage):
	counts = {exit_type: 1}
	r = frames.metrics(time, {'usage': rusage.ru_stime + rusage.ru_utime}, counts)
	msg = frames.types.Message.from_string_v1(
		"transaction-event[--]: METRICS: system process",
		protocol=frames_protocol
	)
	msg.msg_parameters['data'] = r
	return msg

def cached_operation_signal(time, skipped):
	counts = {'cached': skipped}
	r = frames.metrics(time, {}, counts)
	msg = frames.types.Message.from_string_v1(
		"transaction-event[--]: METRICS: cached operation count",
		protocol=frames_protocol
	)
	msg.msg_parameters['data'] = r
	return msg

class Construction(kcore.Context):
	"""
	# Construction process manager. Maintains the set of targets to construct and
	# dispatches the work to be performed for completion in the appropriate order.
	"""

	def warn(self, target, text):
		msg = frames.types.Message.from_string_v1(
			"message-application[!#]: WARNING: " + text,
			protocol=frames_protocol
		)
		msg.msg_parameters['data'] = frames.types.Parameters.from_pairs_v1([
			('time-offset', int(self.time())),
			('factor', str(target.route)),
		])
		return self.log.emit(self._channel, msg)

	def __init__(self,
			channel,
			time,
			log,
			intentions,
			cache,
			context,
			symbols,
			pcontext,
			ctxpath,
			project,
			factors,
			reconstruct=False,
			processors=4,
		):
		super().__init__()

		self._channel = channel
		self._etime = time
		self._rusage = {}
		self.log = log
		self._end_of_factors = False

		self.reconstruct = reconstruct
		self.failures = 0
		self.exits = 0
		self.c_sequence = None

		self.c_intentions = intentions
		self.c_cache = cache
		self.c_pcontext = pcontext
		self.c_ctxpath = ctxpath
		self.c_project = project
		self.c_symbols = symbols
		self.c_context = context
		self.c_factors = factors

		self.tracking = collections.defaultdict(list) # factor -> sequence of sets of tasks
		self.progress = collections.Counter()

		self.process_count = 0 # Track available subprocess slots.
		self.process_limit = processors
		self.command_queue = collections.deque()

		self.continued = False
		self.activity = set()

	def time(self):
		return sysclock.elapsed().decrease(self._etime)

	def actuate(self):
		if self.reconstruct:
			if self.reconstruct > 1:
				self._filter = functools.partial(updated, never=True, cascade=True)
			else:
				self._filter = functools.partial(updated, never=True, cascade=False)
		else:
			self._filter = functools.partial(updated)

		descent = functools.partial(requirements, self.c_context, self.c_ctxpath, self.c_symbols)

		# Manages the dependency order.
		self.c_sequence = graph.sequence(descent, self.c_factors)

		initial = next(self.c_sequence)
		assert initial is None # generator init

		self.finish(())
		self.drain_process_queue()

		return super().actuate()

	def finish(self, factors):
		"""
		# Called when a set of factors have been completed.
		"""
		try:
			for x in factors:
				del self.progress[x]
				del self.tracking[x]

			work, reqs, deps = self.c_sequence.send(factors) # raises StopIteration
			for x in work:
				self.collect(x, reqs, deps.get(x, ()))
		except StopIteration:
			self._end_of_factors = True
			self.xact_exit_if_empty()

	def xact_void(self, final):
		if self._end_of_factors:
			self.finish_termination()

	def _prepare_work_directory(self, locations, sources):
		"""
		# Generate processing instructions initializing directories in the work directory.
		"""

		ftr = locations['factor-image']
		units = locations['output']
		logs = locations['log']

		yield ('directory', None, None, (None, ftr.container))

		emitted = set((units, logs))

		# Mirror source directory tree.
		# Scan the whole set; don't presume all sources share a common directory.
		for srcfmt, src in sources:
			unit = files.Path(units, src.points[:-1])
			log = files.Path(logs, src.points[:-1])
			emitted.update((unit, log))

		for x in emitted:
			if x.fs_type() == 'void':
				yield ('directory', None, None, (None, x))

	if 0:
		# End of project processing.
		def finish_termination(self):
			return super().finish_termination()

	def collect(self, factor, requirements, dependents=()):
		"""
		# Collect the parameters and work to be done for processing the &factor.

		# [ Parameters ]
		# /factor/
			# The &core.Target being built.
		# /requirements/
			# The set of factors referred to by &factor. Often, the
			# dependencies that need to be built in order to build the factor.
		# /dependents/
			# The set of factors that refer to &factor.
		"""
		tracks = self.tracking[factor]

		if isinstance(factor, core.SystemFactor):
			# SystemFactors require no processing.
			self.finish([factor])
			return

		ctx = self.c_context
		reqs = requirements.get(factor, ())
		selection = ctx.select(factor.type)

		if selection is None:
			self.warn(factor, "no mechanism for %r factors"%(factor.type,))

			self.activity.add(factor)
			if self.continued is False:
				self.continued = True
				self.enqueue(self.continuation)
			return

		variants, mech = selection

		# Subfactor of c_factor (selected path)
		subfactor = (factor.project.factor == self.c_project.factor)
		xfilter = functools.partial(self._filter, subfactor=subfactor)

		for ci, variants in mech.variants(self.c_intentions):
			image = factor.image(variants)
			key = work(variants, factor.name)
			cdr = self.c_cache.select(factor.project.factor, factor.route, key)
			locations = {
				'factor-image': image,
				'work': cdr,
				'log': (cdr / 'log').delimit(),
				'output': (cdr / 'units').delimit(),
			}

			fint = core.Integrand((
				self.c_pcontext, mech,
				factor, reqs, dependents,
				variants, locations
			))
			if not fint.operable:
				continue

			xf = list(mech.translate(fint, xfilter))
			skipped = len(fint.factor.sources()) - len(xf)

			# If any commands or calls are made by the transformation,
			# rebuild the target.
			for x in xf:
				if x[0] not in ('directory', 'link'):
					f = rebuild
					break
			else:
				# Otherwise, update if out dated.
				f = xfilter

			fi = list(mech.render(fint, f))
			if xf or fi:
				pf = list(self._prepare_work_directory(
					locations, fint.factor.sources()
				))
			else:
				pf = ()
				# Cached.
				skipped += 1

			tracks.extend((('prepare', pf), ('translate', xf), ('render', fi)))

			# Communicate skip count.
			channel = self._channel + '/' + str(factor.name)
			self.log.emit(channel, cached_operation_signal(0, skipped))

		if tracks:
			self.progress[factor] = -1
			self.dispatch(factor)
		else:
			self.activity.add(factor)

			if self.continued is False:
				# Consolidate loading of the next set of processors.
				self.continued = True
				self.enqueue(self.continuation)

	devnull = files.Path.from_absolute(os.devnull)
	def _reapusage(self, pid, partial=functools.partial):
		deliver = partial(self._rusage.__setitem__, pid)
		wait = partial(libexec.waitrusage, deliver)
		return partial(libexec.reap, sysop=wait)

	def process_execute(self, instruction, f_target_path=(lambda x: str(x))):
		irole, factor, ins = instruction
		typ, cmd, log, io, *tail = ins

		stdout = stdin = self.devnull # Defaults

		if typ == 'execute-stdio':
			stdout = io[1]
			stdin = io[0][0]
			iostr = ' <' + str(stdin) + ' >' + str(stdout)
		elif typ == 'execute-redirection':
			stdout = io[1]
			iostr = ' >' + str(stdout)
		else:
			iostr = ''

		assert typ in ('execute', 'execute-redirection', 'execute-stdio')

		if irole == 'integrate':
			focus = str(io[1])
		elif irole == 'transform':
			focus = str(io[0][0])
		else:
			focus = '<unknown instruction role>'

		strcmd = tuple(map(str, cmd))
		pid = None
		start_time = self.time()

		with log.fs_open('wb') as f:
			ki = libexec.KInvocation(str(cmd[0]), strcmd, environ=dict(os.environ))
			with stdin.fs_open('rb') as ci:
				with stdout.fs_open('wb') as co:
					pid = ki.spawn(fdmap=((ci.fileno(), 0), (co.fileno(), 1), (f.fileno(), 2)))
					sp = kdispatch.Subprocess(self._reapusage(pid), {
						pid: (typ, cmd, log, factor, start_time, io)
					})
			xact = kcore.Transaction.create(sp)

		# Emit status frames.
		open_msg = open_process_transaction(
			start_time, factor.route, pid,
			strcmd[0], focus, strcmd, log
		)
		channel = "{0}/{1}/{2}/{3}".format(
			self._channel, str(factor.name), 'system', str(pid),
		)
		self.log.emit(channel, open_msg)

		self.xact_dispatch(xact)
		return xact

	def xact_exit(self, xact):
		# Subprocess Transaction
		sp = xact.xact_context
		for pid, params, status in sp.sp_report():
			self.process_exit(pid, status, None, *params)

	def process_exit(self,
			pid, delta, rusage, typ, cmd, log, factor, start_time, io,
			_color='\x1b[38;5;1m',
			_normal='\x1b[0m'
		):
		rusage = self._rusage.pop(pid, None)
		self.progress[factor] += 1
		self.process_count -= 1
		self.activity.add(factor)

		exit_code = delta.status
		if exit_code is None:
			# Bad exit event connected.
			self.warn(factor, "process exit event did not have status")

		self.exits += 1
		# Build synopsis.
		exitstr = cmd[0].rsplit('/', 1)[-1] + '[' + str(exit_code) + ']'
		if exit_code == 0:
			if io[1].fs_type() == 'directory':
				io[1].fs_modified()
		else:
			self.failures += 1
			exitstr = _color + exitstr + _normal

		synopsis = ' '.join([exitstr, str(log),])
		stop_time = self.time()

		if exit_code is None:
			exit_type = 'cached'
		elif exit_code == 0:
			exit_type = 'processed'
		else:
			exit_type = 'failed'

		close_msg = close_process_transaction(stop_time, pid, synopsis, exit_code, rusage)
		channel = "{0}/{1}/{2}/{3}".format(
			self._channel, str(factor.name), 'system', str(pid),
		)
		self.log.emit(channel, process_metrics_signal(stop_time - start_time, exit_type, rusage))
		self.log.emit(channel, close_msg)

		if self.continued is False:
			# Consolidate loading of the next set of processors.
			self.continued = True
			self.enqueue(self.continuation)

	def drain_process_queue(self):
		"""
		# After process slots have been cleared by &process_exit,
		# &continuation is called and performs this method to execute
		# system processes enqueued in &command_queue.
		"""
		# Process slots may have been cleared, run more if possible.
		nitems = len(self.command_queue)
		if nitems > 0:
			# Identify number of processes to spawn.
			# &process_exit decrements the process_count, so the available
			# logical slots are normally the selected count. Minimize
			# on the number of items in the &command_queue.
			pcount = min(self.process_limit - self.process_count, nitems)
			for x in range(pcount):
				cmd = self.command_queue.popleft()
				try:
					self.process_execute(cmd)
				except Exception as error:
					# Display exception and note progress.
					import traceback
					traceback.print_exception(error.__class__, error, error.__traceback__)
					self.progress[cmd[0]] += 1
				else:
					self.process_count += 1

	def continuation(self):
		"""
		# Process exits occurred that may trigger an addition to the working set of tasks.
		# Usually called indirectly by &process_exit, this manages the collection
		# of further work identified by the sequenced dependency tree managed by &sequence.
		"""
		# Reset continuation
		self.continued = False
		factors = list(self.activity)
		self.activity.clear()

		completions = set()

		for x in factors:
			tracking = self.tracking[x]
			if not tracking:
				# Empty tracking sets.
				completions.add(x)
				continue

			if self.progress[x] >= len(tracking[0][1]):
				# Pop action set.
				del tracking[0]
				self.progress[x] = -1

				if not tracking:
					# Complete.
					completions.add(x)
				else:
					# dispatch new set of instructions.
					self.dispatch(x)
			else:
				# Nothing to be done; likely waiting on more
				# process exits in order to complete the task set.
				pass

		if completions:
			self.finish(completions)

		self.drain_process_queue()

	def dispatch(self, factor):
		"""
		# Process the collected work for the factor.
		"""
		assert self.progress[factor] == -1
		self.progress[factor] = 0

		irole, commands = self.tracking[factor][0]
		for x in commands:
			typ, cmd, logfile, *tail = x

			if typ in ('execute', 'execute-redirection', 'execute-stdio'):
				self.command_queue.append((irole, factor, x))
			elif typ == 'directory':
				tail[0][1].fs_alloc().fs_mkdir()
				self.progress[factor] += 1
			elif typ == 'link':
				src, dst = tail[0]
				dst.fs_link_relative(src)

				self.progress[factor] += 1
			elif typ == 'call':
				try:
					cmd[0](*cmd[1:])
					if logfile.fs_type() != 'void':
						logfile.fs_void()
				except BaseException as err:
					self.failures += 1
					pi_call = cmd[0]
					pi_call_id = '.'.join((pi_call.__module__, pi_call.__name__))
					error = '%s call (%s) raised ' % (factor.absolute_path_string, pi_call_id,)
					error += err.__class__.__name__ + ': '
					error += str(err) + '\n'
					sys.stderr.write(error)

					from traceback import format_exception
					out = format_exception(err.__class__, err, err.__traceback__)

					heading = b'[Exception]\n#!/traceback\n\t'
					heading += '\t'.join(out).encode('utf-8')
					logfile.fs_store(heading)

				self.progress[factor] += 1
			else:
				self.log.write('unknown instruction %s\n' %(x,))

		if self.progress[factor] >= len(self.tracking[factor][0][1]):
			self.activity.add(factor)

			if self.continued is False:
				self.continued = True
				self.enqueue(self.continuation)
