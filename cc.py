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
from . import vectorcontext

open_fs_context = vectorcontext.Context.from_directory
devnull = files.Path.from_absolute(os.devnull)

def local_query(integrand, local, query):
	if query in local:
		r = local[query]
		if isinstance(r, list):
			return r
		return [r]
	return list(map(str, integrand.select(query)))

def prepare(command, args, log, output, input, executor=None):
	"""
	# Given a command and its constructed arguments, interpret the
	# standard I/O fields in &args, formulate a &libexec.KInvocation
	# instance for execution, and prepare stdio &files.Path
	# assignments.

	# [ Parameters ]
	# /command/
		# The command prefix to be used with &args.
	# /args/
		# The argument vector produced by the construction context.
	# /log/
		# The &files.Path identifying the default location for standard error.
	# /output/
		# The &files.Path identifying the file that will be created by the command.
	# /input/
		# The &files.Path identifying the source file being translated or the sole unit.
	"""
	opid = next(args)
	stdin_spec = next(args)
	stdout_spec = next(args)

	if stdin_spec == '-':
		stdin = devnull
	else:
		if stdin_spec == 'input':
			stdin = input
		else:
			raise Exception("unrecognized standard input specifier: " + input)

	if stdout_spec == '-':
		stdout = devnull
	else:
		if stdout_spec == 'output':
			stdout = output
		else:
			raise Exception("unrecognized standard output specifier: " + output)

	xargs = list(command[2])
	xargs.extend(args)
	env = dict(os.environ)
	env.update(command[0])

	ki = libexec.KInvocation(executor or command[1], xargs, environ=env)
	return (opid, output, stdin, stdout, log, ki)

@tools.cachedcalls(12)
def _ftype(itype):
	return itype.project + '/' + str(itype.factor ** 1)

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
		try:
			stat = x.fs_status()
		except FileNotFoundError:
			# This appears undesirable, but the case is that &updated is used
			# in situation where the &inputs are supposed to exist. If they
			# do not, it is likely that integration was performed incorrectly.
			# Or, requirements without images are being referenced, which is
			# why this behavior is desired. Notably, lambda.sources factors
			# never have images.
			pass
		else:
			if stat.system.st_mtime > olm:
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
			yield core.Target(
				pj, fp, ft, rreqs, rsources,
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
			executor,
			channel,
			time,
			log,
			intentions,
			form,
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
		self._mcache = {}
		self.log = log
		self._end_of_factors = False

		self.reconstruct = reconstruct
		self.failures = 0
		self.exits = 0
		self.c_sequence = None

		self.c_intentions = intentions
		self.c_form = form
		self.c_executor = executor
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

	def select(self, ftype):
		if ftype in self._mcache:
			return self._mcache[ftype]

		mech = self._mcache[ftype] = vectorcontext.Mechanism(self.c_context, ftype)
		return mech

	def finish(self, factors):
		"""
		# Called when a set of factors have been completed.
		"""
		try:
			for x in factors:
				del self.progress[x]
				del self.tracking[x]

			work, reqs, deps = self.c_sequence.send(factors) # raises StopIteration
			for target in work:
				if isinstance(target, core.SystemFactor):
					self.tracking[target] = []
					self.finish([target])
				else:
					ftype = _ftype(target.type)
					fr = reqs.get(target, ())
					fd = deps.get(target, ())
					self.collect(self.select(ftype), target, fr, fd)
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
		units = locations['unit-directory']
		logs = locations['log-directory']

		workdir = ftr.container
		workdir.fs_mkdir()

		emitted = set((units, logs))

		# Mirror source directory trees to allow trivial unit/log initialization.
		for srcfmt, src in sources:
			unit = files.Path(units, src.points[:-1])
			log = files.Path(logs, src.points[:-1])
			emitted.update((unit, log))

		for x in emitted:
			if x.fs_type() == 'void':
				x.fs_alloc().fs_mkdir()

	if 0:
		# End of project processing.
		def finish_termination(self):
			return super().finish_termination()

	def collect(self, mechanism, factor, requirements, dependents=()):
		"""
		# Collect the parameters and work to be done for processing the &factor.

		# [ Parameters ]
		# /mechanism/
			# The abstraction to the Construction Context providing
			# translation and rendering command constructors for the variant set.
		# /factor/
			# The &core.Target being built.
		# /requirements/
			# The set of factors referred to by &factor. Often, the
			# dependencies that need to be built in order to build the factor.
		# /dependents/
			# The set of factors that refer to &factor.
		"""
		tracks = self.tracking[factor]

		# Subfactor of c_factor (selected path)
		subfactor = (factor.project.factor == self.c_project.factor)
		xfilter = functools.partial(self._filter, subfactor=subfactor)

		# Execution override for supporting command tracing and usage constraints.
		exe = self.c_executor
		skipped = 0
		nsources = len(factor.sources())

		for section, variants in mechanism.variants(self.c_intentions, form=self.c_form):
			u_prefix, u_suffix = mechanism.unit_name_delta(section, variants, factor.type)

			image = factor.image(variants)
			key = work(variants, factor.name)
			cdr = self.c_cache.select(factor.project.factor, factor.route, key)
			locations = {
				'factor-image': image,
				'work-directory': cdr,
				'log-directory': (cdr / 'log').delimit(),
				'unit-directory': (cdr / 'units').delimit(),
			}

			fint = core.Integrand((
				mechanism, factor,
				requirements, dependents,
				variants, locations
			))
			if not fint.operable:
				continue

			self._prepare_work_directory(locations, factor.sources())
			logs = locations['log-directory']
			units = locations['unit-directory']

			translations = []
			unitseq = []
			for fmt, src in factor.sources():
				unit_name = u_prefix + src.identifier + u_suffix
				tlout = files.Path(units, src.points[:-1] + (unit_name,))
				unitseq.append(str(tlout))

				if xfilter((tlout,), (src,)):
					continue

				tllog = files.Path(logs, src.points)
				cmd, tlc = mechanism.translate(section, variants, factor.type, fmt)
				local = {
					'source': str(src),
					'unit': str(tlout),
					'language': fmt.format.language,
					'dialect': fmt.format.dialect,
				}
				q = tools.partial(local_query, fint, local)

				args = tlc(q)
				translations.append(prepare(cmd, args, tllog, tlout, src, executor=exe))

			tracks.append(('translate', translations))

			if translations or not xfilter((image,), fint.required(variants)):
				# Build is triggered unconditionally if any translations are performed
				# or if the target image is older than any requirement image.

				cmd, ric = mechanism.render(section, variants, factor.type)
				local = {
					'units': unitseq,
				}
				if len(unitseq) == 1:
					local['unit'] = unitseq[0]

				q = tools.partial(local_query, fint, local)
				render = ric(q)
				rlog = files.Path(logs, ('Integration',))
				ops = [prepare(cmd, render, rlog, image, src, executor=exe)]
			else:
				ops = []

			tracks.append(('render', ops))

			# Communicate skip count.
			channel = self._channel + '/' + str(factor.name)
			skipped += nsources - len(translations)
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

	def _reapusage(self, pid, partial=functools.partial):
		deliver = partial(self._rusage.__setitem__, pid)
		wait = partial(libexec.waitrusage, deliver)
		return partial(libexec.reap, sysop=wait)

	def process_execute(self, instruction, f_target_path=(lambda x: str(x))):
		phase, factor, ins = instruction
		opid, tfile, cin, cout, cerr, ki = ins

		pid = None
		start_time = self.time()

		with cin.fs_open('rb') as ci:
			with cerr.fs_open('wb') as cl:
				with cout.fs_open('wb') as co:
					pid = ki.spawn(fdmap=(
						(ci.fileno(), 0),
						(co.fileno(), 1),
						(cl.fileno(), 2),
					))
					sp = kdispatch.Subprocess(self._reapusage(pid), {
						pid: (start_time, factor, cerr, opid, tfile)
					})
			xact = kcore.Transaction.create(sp)

		# Emit status frames.
		open_msg = open_process_transaction(
			start_time, factor.route, pid,
			opid, phase, (opid,), cerr
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

	def process_exit(self, pid, delta, rusage,
			start_time, factor, log, cmd, tfile,
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
		exitstr = cmd + '[' + str(exit_code) + ']'
		if exit_code == 0:
			if tfile.fs_type() == 'directory':
				# Force modification of directories for (persistent) cache checks.
				tfile.fs_modified()
		else:
			self.failures += 1

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

		phase, commands = self.tracking[factor][0]
		for x in commands:
			self.command_queue.append((phase, factor, x))

		if self.progress[factor] >= len(self.tracking[factor][0][1]):
			self.activity.add(factor)

			if self.continued is False:
				self.continued = True
				self.enqueue(self.continuation)
