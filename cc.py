"""
# Software Construction Context implementation in Python.
"""
import os
import sys
import functools
import collections
import contextlib
import typing

from fault.time import sysclock
from fault.system import execution as libexec
from fault.system import files
from fault.internet import ri
from fault import routes

from fault.kernel import core as kcore
from fault.kernel import dispatch as kdispatch

from . import graph
from . import core
from . import v1

Context=v1.Context

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
		if not output.exists():
			# No such object, not updated.
			return False
		lm = output.get_last_modified()
		olm = min(lm, olm or lm)

	# Otherwise, check the inputs against outputs.
	# In the case of a non-cascading rebuild, it is desirable
	# to perform the input checks.

	for x in inputs:
		if not x.exists() or x.get_last_modified() > olm:
			# rebuild if any output is older than any source.
			return False

	# object has already been updated.
	return True

def group(factors:typing.Sequence[object]):
	"""
	# Organize &factors by their domain-type pair using (python/attribute)`pair` on
	# the factor.
	"""

	container = collections.defaultdict(set)
	for f in factors:
		container[f.pair].add(f)
	return container

def interpret_reference(index, factor, symbol, url):
	"""
	# Extract the project identifier from the &url and find a corresponding
	# entry in the project set, &index.

	# The fragment portion of the URL specifies the factor within the project
	# that should be connected in order to use the &symbol.
	"""

	i = ri.parse(url)
	rfactor = i.pop('fragment', None)
	rproject_name = i['path'][-1]

	i['path'][-1] = '' # Force the trailing slash in serialize()
	product = ri.serialize(i)

	project = None
	path = None
	ftype = (None, None)
	rreqs = {}
	sources = []

	project_url = product + rproject_name

	project = core.Project(*index.select(project_url))
	factor = routes.Segment.from_sequence(rfactor.split('.'))
	factor_dir = project.route // factor
	from fault.project import explicit
	ctx, fdata = explicit.struct.parse((factor_dir/'factor.txt').get_text_content())

	t = core.Target(project, factor, fdata['domain'] or 'system', fdata['type'], rreqs, [])
	return t

def requirements(index, symbols, factor):
	"""
	# Return the set of factors that is required to build this Target, &self.
	"""

	if isinstance(factor, core.SystemFactor): # XXX: eliminate variation
		return

	for sym, refs in factor.symbols.items():
		if sym in symbols:
			sdef = symbols[sym]
			if isinstance(sdef, list):
				yield from sdef
			else:
				yield from core.SystemFactor.collect(symbols[sym])
			continue

		for r in refs:
			if isinstance(r, core.Target):
				yield r
			else:
				yield interpret_reference(index, factor, sym, r)

def resolve(infrastructure, overrides, symbol):
	if symbol in overrides:
		return overrides[symbol]
	return infrastructure[symbol]

def initial_factor_defines(factor, factorpath):
	"""
	# Generate a set of defines that describe the factor being created.
	# Takes the full module path of the factor as a string.
	"""
	parts = factorpath.split('.')
	project = '.'.join(factor.project.segment.absolute)

	tail = factorpath[len(project)+1:].split('.')[1:]

	return [
		('FACTOR_SUBPATH', '.'.join(tail)),
		('FACTOR_PROJECT', project),
		('FACTOR_QNAME', factorpath),
		('FACTOR_BASENAME', parts[-1]),
		('FACTOR_PACKAGE', '.'.join(parts[:-1])),
	]

class Construction(kcore.Context):
	"""
	# Construction process manager. Maintains the set of target modules to construct and
	# dispatches the work to be performed for completion in the appropriate order.

	# [ Engineering ]
	# Primarily, this class traverses the directed graph constructed by imports
	# performed by the target modules being built.
	"""

	def __init__(self,
			log,
			context,
			symbols,
			index,
			project,
			factor,
			factors,
			reconstruct=False,
			processors=4
		):
		self.log = log
		self._end_of_factors = False

		self.reconstruct = reconstruct
		self.failures = 0
		self.exits = 0
		self.c_sequence = None

		self.c_factor = factor
		self.c_symbols = symbols
		self.c_index = index
		self.c_context = context
		self.c_project = project
		self.c_factors = factors

		self.tracking = collections.defaultdict(list) # module -> sequence of sets of tasks
		self.progress = collections.Counter()

		self.process_count = 0 # Track available subprocess slots.
		self.process_limit = processors
		self.command_queue = collections.deque()

		self.continued = False
		self.activity = set()

		super().__init__()

	def actuate(self):
		p = self.c_project.information
		itxt = p.icon.get('emoji', '')
		self.log.write("[<> %s%s %s %s]\n" %(itxt and itxt+' ', p.name, p.identifier, self.c_context.intention))

		if self.reconstruct:
			if self.reconstruct > 1:
				self._filter = functools.partial(updated, never=True, cascade=True)
			else:
				self._filter = functools.partial(updated, never=True, cascade=False)
		else:
			self._filter = functools.partial(updated)

		descent = functools.partial(requirements, self.c_index, self.c_symbols)

		# Manages the dependency order.
		self.c_sequence = graph.sequence(descent, self.c_factors)

		initial = next(self.c_sequence) # generator init
		assert initial is None

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
		intention = ctx.intention
		f_name = factor.absolute_path_string
		common_src_params = initial_factor_defines(factor, f_name)
		selection = ctx.select(factor.domain)

		if selection is None:
			# No mechanism found.
			self.log.write("[!# WARNING: no mechanism set for %r factors]\n"%(factor.domain))
			return

		variants, mech = selection
		variants['name'] = factor.name
		variant_set = factor.link(variants, ctx, mech, reqs, dependents)

		# Subfactor of c_factor (selected path)
		subfactor = (factor.project.segment == self.c_factor)
		xfilter = functools.partial(self._filter, subfactor=subfactor)
		envpath = factor.project.environment

		for src_params, (vl, key, locations) in variant_set:
			v = dict(vl)

			if not mech.integrates():
				# For mechanisms that do not specify reductions,
				# the transformed set is the factor.
				# XXX: Incomplete; check if specific output is absent.
				locations['output'] = locations['integral']

			build = core.Build((
				ctx, mech, factor, reqs, dependents,
				v, locations, src_params + common_src_params, envpath
			))
			xf = list(mech.transform(build, xfilter))

			# If any commands or calls are made by the transformation,
			# rebuild the target.
			for x in xf:
				if x[0] not in ('directory', 'link'):
					f = rebuild
					break
			else:
				# Otherwise, update if out dated.
				f = xfilter

			# Collect the exact mechanisms used for reference by integration.
			xfmechs = {}
			for src in build.factor.sources():
				langname = ctx.language(src.extension)
				xfmech = build.mechanism.adaption(build, langname, src, phase='transformations')
				if langname not in xfmechs:
					xfmechs[langname] = xfmech

			fi = list(mech.integrate(xfmechs, build, f))
			if xf or fi:
				pf = list(mech.prepare(build))
			else:
				pf = ()

			tracks.extend((pf, xf, fi))

		if tracks:
			self.progress[factor] = -1
			self.dispatch(factor)
		else:
			self.activity.add(factor)

			if self.continued is False:
				# Consolidate loading of the next set of processors.
				self.continued = True
				self.enqueue(self.continuation)

	def process_execute(self, instruction, f_target_path=(lambda x: str(x))):
		factor, ins = instruction
		typ, cmd, log, io, *tail = ins
		target = io[1]

		stdout = stdin = os.devnull

		if typ == 'execute-stdio':
			stdout = str(io[1])
			stdin = str(io[0][0]) # Catenate for integrations?
			iostr = ' <' + str(stdin) + ' >' + stdout
		elif typ == 'execute-redirection':
			stdout = str(io[1])
			iostr = ' >' + stdout
		else:
			iostr = ''

		assert typ in ('execute', 'execute-redirection', 'execute-stdio')

		strcmd = tuple(map(str, cmd))
		fpath = factor.absolute_path_string
		formatted = {str(target): f_target_path(target)}
		printed_command = tuple(formatted.get(x, x) for x in map(str, cmd))
		command_string = ' '.join(printed_command) + iostr

		pid = None
		with log.open('wb') as f:
			f.write(b'[Command]\n')
			f.write(' '.join(strcmd).encode('utf-8'))
			f.write(b'\n\n[Standard Error]\n')

			ki = libexec.KInvocation(str(cmd[0]), strcmd, environ=dict(os.environ))
			with open(stdin, 'rb') as ci, open(stdout, 'wb') as co:
				pid = ki.spawn(fdmap=((ci.fileno(), 0), (co.fileno(), 1), (f.fileno(), 2)))
				sp = kdispatch.Subprocess(libexec.reap, {
					pid: (sysclock.now(), typ, cmd, log, factor, command_string)
				})
			xact = kcore.Transaction.create(sp)

		self.log.write("[-> (%s/system/%d) %s]\n" %(fpath, pid, command_string))
		self.xact_dispatch(xact)

	def xact_exit(self, xact):
		sp = xact.xact_context
		for pid, params, status in sp.sp_report():
			self.process_exit(pid, status, *params)

	def process_exit(self,
			pid, delta, start, typ, cmd, log, factor, message,
			_color='\x1b[38;5;1m',
			_normal='\x1b[0m'
		):
		self.progress[factor] += 1
		self.process_count -= 1
		self.activity.add(factor)

		exit_code = delta.status
		if exit_code is None:
			exit_code = -0xFFFF

		self.exits += 1
		self.log.write("[<- (%s/system/%d) %d %s]\n" %(factor.absolute_path_string, pid, exit_code, cmd[0]))
		if exit_code != 0:
			self.failures += 1

			if message is not None:
				duration = repr(start.measure(sysclock.now()))
				prefix = "%s: %d -> %s in %s\n\t" %(
					_color + factor.absolute_path_string + _normal,
					pid,
					_color + str(exit_code) + _normal,
					str(duration)
				)
				self.log.write(prefix+message+'\n')

		l = ''
		l += ('\n[Profile]\n')
		l += ('/factor/\n\t%s\n' %(factor,))

		if log.points[-1] != 'reduction':
			l += ('/subject/\n\t%s\n' %('/'.join(log.points),))
		else:
			l += ('/subject/\n\treduction\n')

		l += ('/pid/\n\t%d\n' %(pid,))
		l += ('/status/\n\t%s\n' %(str(exit_code),))
		l += ('/start/\n\t%s\n' %(start.select('iso'),))
		l += ('/stop/\n\t%s\n' %(sysclock.now().select('iso'),))

		log.store(l.encode('utf-8'), mode='ba')

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
				self.process_execute(cmd)
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

			if self.progress[x] >= len(tracking[0]):
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

		for x in self.tracking[factor][0]:
			typ, cmd, logfile, *tail = x

			if typ in ('execute', 'execute-redirection', 'execute-stdio'):
				self.command_queue.append((factor, x))
			elif typ == 'directory':
				tail[0][1].init('directory')

				self.progress[factor] += 1
			elif typ == 'link':
				src, dst = tail[0]
				dst.link(src)

				self.progress[factor] += 1
			elif typ == 'call':
				try:
					cmd[0](*cmd[1:])
					if logfile.exists():
						logfile.void()
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
					logfile.store('[Exception]\n#!/traceback\n\t', 'w')
					logfile.store('\t'.join(out).encode('utf-8'), 'ba')

				self.progress[factor] += 1
			else:
				self.log.write('unknown instruction %s\n' %(x,))

		if self.progress[factor] >= len(self.tracking[factor][0]):
			self.activity.add(factor)

			if self.continued is False:
				self.continued = True
				self.enqueue(self.continuation)
