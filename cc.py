"""
# Software Construction Context implementation in Python.

# [ Engineering ]
# /Mechanism Load Order/
	# Mechanism data layers are not merged in a particular order.
	# This allows for inconsistencies to occur across &Context instances.
"""
import os
import sys
import functools
import itertools
import collections
import contextlib
import operator
import importlib
import importlib.machinery
import types
import typing
import copy

from fault.computation import library as libc
from fault.time import library as libtime
from fault.routes import library as libroutes
from fault.io import library as libio
from fault.system import library as libsys
from fault.system import python as system_python
from fault.system import files as system_files
from fault.text import struct as libstruct
from fault.project import library as libproject
from fault.internet import ri

from . import graph
from . import data
from . import core

File = system_files.Path

def context_interface(path):
	"""
	# Resolves the construction interface for processing a source or performing
	# the final reduction (link-stage).
	"""

	# Avoid at least one check as it is known there is at least
	# one attribute in the path.
	leading, final = path.rsplit('.', 1)
	mod, apath = system_python.Import.from_attributes(leading)
	obj = importlib.import_module(str(mod))

	for x in apath:
		obj = getattr(obj, x)

	return getattr(obj, final)

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

	print(url, index)
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
	factor = libroutes.Segment.from_sequence(rfactor.split('.'))
	factor_dir = project.route.extend(factor.absolute)
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
			if isinstance(r, Target):
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

class Mechanism(object):
	"""
	# The mechanics used to produce an Integral from a set of Sources associated
	# with a Factor. &Mechanism instances are usually created by &Context instances
	# using &Context.select.

	# [ Properties ]

	# /descriptor/
		# The data structure referring to the interface used
		# to construct processing instructions for the selected mechanism.
	# /cache/
		# Mapping of resolved adapters. Used internally for handling
		# adapter inheritance.
	"""

	def __init__(self, descriptor):
		self.descriptor = descriptor
		self.cache = {}

	@property
	def symbol(self):
		return self.descriptor['path'][0]

	@property
	def groups(self):
		return self.descriptor['groups']

	@property
	def integrations(self):
		return self.descriptor['integrations']

	@property
	def transformations(self):
		return self.descriptor['transformations']

	def integrates(self):
		ints = self.descriptor.get('integrations')
		if ints:
			return True
		else:
			return False

	def suffix(self, factor):
		"""
		# Return the suffix that the given factor should use for its integral.
		"""
		tfe = self.descriptor.get('target-file-extensions', {None: '.v'})
		return (
			tfe.get(factor.type) or \
			tfe.get(None) or '.i'
		)

	def prepare(self, build):
		"""
		# Generate any requisite filesystem requirements.
		"""

		loc = build.locations
		f = build.factor
		ftr = loc['integral']

		yield ('directory', None, None, (None, ftr.container))

		od = loc['output']
		ld = loc['log']
		emitted = set((od, ld))

		for src in f.sources():
			outfile = File(od, src.points)
			logfile = File(ld, src.points)

			for x in (outfile, logfile):
				d = x.container
				emitted.add(d)

		for x in emitted:
			if not x.exists():
				yield ('directory', None, None, (None, x))

	def adaption(self, build, domain, source, phase='transformations'):
		"""
		# Select the adapter of the mechanism for the given source.

		# Adapters with inheritance will be cached by the mechanism.
		"""
		acache = self.cache
		aset = self.descriptor[phase]

		# Mechanisms support explicit inheritance.
		if (phase, domain) in acache:
			return acache[(phase, domain)]

		if domain in aset:
			key = domain
		else:
			# For transformations, usually a compiler collection.
			# Integrations usually only consist of one.
			key = None

		lmech = aset[key]
		layers = [lmech]
		while 'inherit' in (lmech or ()):
			basemech = lmech['inherit']
			layers.append(aset[basemech]) # mechanism inheritance
			lmech = aset[basemech]
		layers.reverse()

		cmech = {}
		for x in layers:
			if x is not None:
				data.merge(cmech, x)
		cmech.pop('inherit', None)

		# cache merged mechanism
		acache[(phase, domain)] = cmech

		return cmech

	def transform(self, build, filtered=rebuild):
		"""
		# Transform the sources using the mechanisms defined in &context.
		"""

		f = build.factor
		fdomain = f.domain
		loc = build.locations
		logs = loc['log']
		intention = build.context.intention
		fmt = build.variants['format']

		mechanism = build.mechanism.descriptor
		ignores = mechanism.get('ignore-extensions', ())

		commands = []
		for src in f.sources():
			fnx = src.extension
			if intention != 'fragments' and fnx in ignores or src.identifier.startswith('.'):
				# Ignore header files and dot-files for non-delineation contexts.
				continue
			obj = File(loc['output'], src.points)

			if filtered((obj,), (src,)):
				continue

			logfile = File(loc['log'], src.points)

			src_type = build.context.language(src.extension)
			out_format = mechanism['formats'][f.type]

			adapter = self.adaption(build, src_type, src, phase='transformations')
			if 'interface' in adapter:
				xf = context_interface(adapter['interface'])
			else:
				sys.stdout.write('[!# ERROR: no interface for transformation %r %s]\n' % (src_type, str(src)))
				continue

			# Compilation to out_format for integration.
			seq = list(xf(build, adapter, out_format, obj, src_type, (src,)))

			yield self.formulate(obj, (src,), logfile, adapter, seq)

	def formulate(self, route, sources, logfile, adapter, sequence, python=sys.executable):
		"""
		# Convert a generated instruction into a form accepted by &Construction.
		"""

		method = adapter.get('method')
		command = adapter.get('command')
		redirect = adapter.get('redirect')

		if method == 'python':
			sequence[0:1] = (python, '-m', command)
		elif method == 'internal':
			return ('call', sequence, logfile, (sources, route))
		else:
			# Adapter interface leaves this as None or a relative name.
			# Update to absolute path entered into adapter.
			sequence[0] = command

		if redirect == 'io':
			return ('execute-stdio', sequence, logfile, (sources, route))
		elif redirect:
			return ('execute-redirection', sequence, logfile, (sources, route))
		else:
			# No redirect.
			return ('execute', sequence, logfile, (sources, route))

	def integrate(self, transform_mechs, build, filtered=rebuild, sys_platform=sys.platform):
		"""
		# Construct the operations for reducing the object files created by &transform
		# instructions into a set of targets that can satisfy
		# the set of dependents.
		"""

		f = build.factor
		loc = build.locations
		mechanism = build.mechanism.descriptor

		fmt = build.variants.get('format')
		if fmt is None:
			return
		if 'integrations' not in mechanism:# or f.reflective: XXX
			# warn/note?
			return

		mechp = mechanism
		ftr = loc['integral']
		rr = ftr

		# Discover the known sources in order to identify which objects should be selected.
		objdir = loc['output']
		sources = set([
			x.points for x in f.sources()
			if x.extension not in mechp.get('ignore-extensions', ())
		])
		objects = [
			objdir.__class__(objdir, x) for x in sources
		]

		if build.requirements:
			partials = [x for x in build.requirements[(f.domain, 'partial')]]
		else:
			partials = ()

		# XXX: does not account for partials
		if filtered((rr,), objects):
			return

		adapter = self.adaption(build, f.type, objects, phase='integrations')

		# Mechanisms with a configured root means that the
		# transformed objects will be referenced by the root file.
		root = adapter.get('root')
		if root is not None:
			objects = [objdir / root]

		# Libraries and partials of the same domain are significant.
		if build.requirements:
			libraries = [x for x in build.requirements[(f.domain, 'library')]]
		else:
			libraries = ()

		xf = context_interface(adapter['interface'])
		seq = xf(transform_mechs, build, adapter, f.type, rr, fmt, objects, partials, libraries)
		logfile = loc['log'] / 'Integration.log'

		yield self.formulate(rr, objects, logfile, adapter, seq)

class Build(tuple):
	"""
	# Container for the set of build parameters used by the configured abstraction functions.
	"""
	context = property(operator.itemgetter(0))
	mechanism = property(operator.itemgetter(1))
	factor = property(operator.itemgetter(2))
	requirements = property(operator.itemgetter(3))
	dependents = property(operator.itemgetter(4))
	variants = property(operator.itemgetter(5))
	locations = property(operator.itemgetter(6))
	parameters = property(operator.itemgetter(7))
	environment = property(operator.itemgetter(8))

	def required(self, domain, ftype):
		ctx = self.context
		needed_variants = ctx.variants(domain, ftype)

		reqs = self.requirements.get((domain, ftype), ())

		srcvars = ctx.index['source']['variants']
		for x in reqs:
			if isinstance(x, core.SystemFactor):
				yield x.integral(), x
				continue

			v = {'name': x.name}
			v.update(needed_variants)
			g = ctx.groups(x.project.environment)
			path = x.integral(g, v)
			yield path, x

class Context(object):
	"""
	# A collection of mechanism sets and parameters used to construct processing instructions.

	# [ Engineering ]
	# This class is actually a Context implementation and should be relocated
	# to make room for a version that interacts with an arbitrary context
	# for use in scripts that perform builds. Direct use is not actually
	# intended as it's used to house the mechanisms.
	"""

	@staticmethod
	def systemfactors(ifactors) -> typing.Iterator[core.SystemFactor]:
		"""
		# Load the system factors in the parameters file identified by &sf_name.
		"""

		for domain, types in ifactors.items():
			for ft, sf in types.items():
				for sf_int in sf:
					if sf_int is not None:
						sf_route = File.from_absolute(sf_int)
					else:
						sf_route = None

					for sf_name in sf[sf_int]:
						yield core.SystemFactor(
							domain = domain,
							type = ft,
							integral = sf_route,
							name = sf_name
						)

	def __init__(self, sequence, symbols):
		self.sequence = sequence or ()
		self.symbols = symbols
		self._languages = {}

		self.index = dict()
		for mid, slots in self.sequence:
			for name, mdata in slots.items():
				data.merge(self.index, mdata)

		syntax = self.index.get('syntax')
		if syntax:
			s = syntax.get('target-file-extensions')
			for pl, exts in s.items():
				for x in exts.split(' '):
					self._languages[x] = pl

	def variants(self, domain, ftype):
		"""
		# Get the variants associated with the domain using the cached view provided by &select.
		"""
		return self.select(domain)[0]

	@functools.lru_cache(8)
	def groups(self, environment) -> typing.Sequence[typing.Sequence[str]]:
		"""
		# Parse and cache the contents of the (filename)`groups.txt` file in the
		# &environment route.

		# This is the context's perspective; effectively consistent across reads
		# due to the cache. If no (filename)`groups.txt` is found, the
		# default (format)`system-architecture/name` is returned.
		"""

		return [['system', 'architecture'], ['name']]

	def extrapolate(self, factors):
		"""
		# Rewrite factor directories into sets of specialized domain factors.
		# Query implementations have no knowledge of specialized domains. This
		# method interprets the files in those directories and creates a proper
		# typed factor for the source.
		"""
		ftype = 'library'

		for path, files in factors:
			for f in files[-1]:
				# Split from left to capture name.
				try:
					stem, suffix = f.identifier.split('.', 1)
				except ValueError:
					stem = f.identifier
					suffix = None
					# XXX: data factor
					continue

				# Find domain.
				try:
					domain = self.language(suffix)
				except:
					# XXX: map to void domain indicating/warning about unprocessed factor?
					continue

				yield (libroutes.Segment(None, path + (stem,)), (domain, ftype, [f]))

	def language(self, extension):
		"""
		# Syntax domain query selecting the language associated with a file extension.
		"""
		return self._languages.get(extension, 'void')

	@property
	def name(self):
		"""
		# The context name identifying the target architectures.
		"""
		return self.index['context']['name']

	@property
	def intention(self):
		return self.index['context']['intention']

	@functools.lru_cache(8)
	def select(self, fdomain):
		# Scan the paths (loaded data sets) for the domain.
		variants = {'intention': self.intention}

		if fdomain in self.index:
			mechdata = copy.deepcopy(self.index[fdomain])
			variants.update(mechdata.get('variants', ()))

			if 'inherit' in mechdata:
				# Recursively merge inherit's.
				inner = mechdata['inherit']
				ivariants, imech = self.select(inner)
				data.merge(mechdata, imech.descriptor)
				variants.update(ivariants)
				mechdata['path'] = [fdomain] + mechdata['path']
			else:
				mechdata['path'] = [fdomain]

			mech = Mechanism(mechdata)
		else:
			# Unsupported domain.
			mech = Mechanism(self.index['void'])
			mech.descriptor['path'] = [fdomain]

		return variants, mech

	@functools.lru_cache(16)
	def field(self, path, prefix):
		"""
		# Retrieve a field from the set of mechanisms.
		"""
		domain, *start = prefix.split('/')
		variants, cwd = self.select(domain)
		for key in start:
			cwd = cwd[key]
		for key in path.split('/'):
			cwd = cwd[key]
		return cwd

	def __bool__(self):
		"""
		# Whether the Context has any mechanisms.
		"""
		return bool(self.sequence)

	@staticmethod
	def load(route:File):
		for x in route.files():
			yield x.identifier, data.load(x)

	@classmethod
	def from_environment(Class, envvar='FPI_MECHANISMS'):
		mech_refs = os.environ.get(envvar, '').split(os.pathsep)
		seq = []
		for mech in mech_refs:
			mech = File.from_absolute(mech)
			seq.extend(list(Class.load(mech)))

		ctx = File.from_absolute(os.environ.get('CONTEXT'))
		r = Class(seq, dict(Class.load(ctx/'symbols')))
		return r

	@classmethod
	def from_directory(Class, route):
		syms = (route / 'symbols')
		mechs = Class.load(route/'mechanisms')

		return Class(list(mechs), dict(Class.load(syms)))

class Construction(libio.Context):
	"""
	# Construction process manager. Maintains the set of target modules to construct and
	# dispatches the work to be performed for completion in the appropriate order.

	# [ Engineering ]
	# Primarily, this class traverses the directed graph constructed by imports
	# performed by the target modules being built.
	"""

	def terminate(self, by=None):
		# Manages the dispatching of processes,
		# so termination is immediate.
		self.exit()

	def __init__(self,
			context,
			symbols,
			index,
			project,
			factor,
			factors,
			reconstruct=False,
			processors=4
		):
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
			self.terminate()

	def collect(self, factor, requirements, dependents=()):
		"""
		# Collect the parameters and work to be done for processing the &factor.

		# [ Parameters ]
		# /factor/
			# The &Target being built.
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
		if selection is not None:
			variants, mech = selection
		else:
			# No mechanism found.
			sys.stdout.write("[!# WARNING: no mechanism set for %r factors]\n"%(factor.domain))
			return

		variants['name'] = factor.name
		variant_set = factor.link(variants, ctx, mech, reqs, dependents)

		# Subfactor of c_factor (selected path)
		subfactor = factor.absolute in self.c_factor
		xfilter = functools.partial(self._filter, subfactor=subfactor)
		envpath = factor.project.environment

		for src_params, (vl, key, locations) in variant_set:
			v = dict(vl)

			# The context parameters for rendering FPI.
			b_src_params = [
				('F_SYSTEM', v.get('system', 'void')),
				('F_INTENTION', intention),
				('F_FACTOR_DOMAIN', factor.domain),
				('F_FACTOR_TYPE', factor.type),
			] + src_params + common_src_params

			if not mech.integrates():
				# For mechanisms that do not specify reductions,
				# the transformed set is the factor.
				# XXX: Incomplete; check if specific output is absent.
				locations['output'] = locations['integral']

			build = Build((
				ctx, mech, factor, reqs, dependents,
				v, locations, b_src_params, envpath
			))
			xf = list(mech.transform(build, filtered=xfilter))

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

			fi = list(mech.integrate(xfmechs, build, filtered=f))
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
				self.ctx_enqueue_task(self.continuation)

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

		pid = None
		with log.open('wb') as f:
			f.write(b'[Command]\n')
			f.write(' '.join(strcmd).encode('utf-8'))
			f.write(b'\n\n[Standard Error]\n')

			ki = libsys.KInvocation(str(cmd[0]), strcmd, environ=dict(os.environ))
			with open(stdin, 'rb') as ci, open(stdout, 'wb') as co:
				pid = ki(fdmap=((ci.fileno(), 0), (co.fileno(), 1), (f.fileno(), 2)))
				sp = libio.Subprocess(pid)

		fpath = factor.absolute_path_string
		pidstr = str(pid)
		formatted = {str(target): f_target_path(target)}
		printed_command = tuple(formatted.get(x, x) for x in map(str, cmd))
		command_string = ' '.join(printed_command) + iostr
		sys.stdout.write("[-> %s:%d %s]\n" %(fpath, pid, command_string))

		self.sector.dispatch(sp)
		sp.atexit(functools.partial(
			self.process_exit,
			start=libtime.now(),
			descriptor=(typ, cmd, log),
			factor=factor,
			message=command_string,
		))

	def process_exit(self, processor,
			start=None, factor=None, descriptor=None,
			message=None,
			_color='\x1b[38;5;1m',
			_pid='\x1b[38;5;2m',
			_normal='\x1b[0m'
		):
		assert factor is not None
		assert descriptor is not None

		self.progress[factor] += 1
		self.process_count -= 1
		self.activity.add(factor)

		typ, cmd, log = descriptor
		pid, status = processor.only
		exit_method, exit_code, core_produced = status

		self.exits += 1
		sys.stdout.write("[<- %s %s %d %d]\n" %(factor.absolute_path_string, cmd[0], pid, exit_code))
		if exit_code != 0:
			self.failures += 1

			if message is not None:
				duration = repr(start.measure(libtime.now()))
				prefix = "%s: %d -> %s in %s\n\t" %(
					_color + factor.absolute_path_string + _normal,
					pid,
					_color + str(exit_code) + _normal,
					str(duration)
				)
				print(prefix+message)

		l = ''
		l += ('\n[Profile]\n')
		l += ('/factor/\n\t%s\n' %(factor,))

		if log.points[-1] != 'reduction':
			l += ('/subject/\n\t%s\n' %('/'.join(log.points),))
		else:
			l += ('/subject/\n\treduction\n')

		l += ('/pid/\n\t%d\n' %(pid,))
		l += ('/status/\n\t%s\n' %(str(status),))
		l += ('/start/\n\t%s\n' %(start.select('iso'),))
		l += ('/stop/\n\t%s\n' %(libtime.now().select('iso'),))

		log.store(l.encode('utf-8'), mode='ba')

		if self.continued is False:
			# Consolidate loading of the next set of processors.
			self.continued = True
			self.ctx_enqueue_task(self.continuation)

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
					print(factor.absolute_path_string, 'call (%s) raised' % (pi_call_id,), err.__class__.__name__, str(err))

					from traceback import format_exception
					out = format_exception(err.__class__, err, err.__traceback__)
					logfile.store('[Exception]\n#!/traceback\n\t', 'w')
					logfile.store('\t'.join(out).encode('utf-8'), 'ba')

				self.progress[factor] += 1
			else:
				print('unknown instruction', x)

		if self.progress[factor] >= len(self.tracking[factor][0]):
			self.activity.add(factor)

			if self.continued is False:
				self.continued = True
				self.ctx_enqueue_task(self.continuation)
