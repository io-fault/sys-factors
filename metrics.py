"""
# Metrics data aggregation and serialization.

# Used in conjunction with &.bin.measure and &..factors to report the collected measurements
# along side the tests that produced them.

# [ Engineering ]

# This is heavily Python specific, and &..development needs to be able to support arbitrary
# languages. The structure of the module may need significant refactoring in order
# to properly support arbitrary measurement pipelines.
"""
import typing
import operator
import collections
import functools
import itertools
import pickle
import os
import os.path
import subprocess
import types
import contextlib

from fault.system import library as libsys
from fault.system import corefile
from fault.system import libfactor

from fault.routes import library as libroutes
from fault.filesystem import library as libfs
from fault.computation import library as libc
from fault.range import library as librange
from fault.syntax import library as libsyntax

from . import testing
from . import cc

def target(context, route):
	"""
	# Identify the route to the binary produced by a composite factor using the given &context.
	"""
	return context.f_target(cc.Factor(route, None, None))

class SyntaxLocator(object):
	"""
	# Data structure used to identify fragments or concepts created therein.
	# &SyntaxLocator is a base class for locations that need to be inverted in
	# order to identify and connect references to their Factor fragments.

	# [ Properties ]
	# /location
		# The area of syntax that identifies the referenced concept.
	# /precision
		# Whether the &location is exact. Defaults to &True.
	"""
	location:(libsyntax.Area) = None
	precision:(bool) = True

	def __init__(self, area:libsyntax.Area):
		self.location = area

	def __str__(self):
		return "SL(%s)" %(self.location,)

	def __hash__(self):
		return self.location.__hash__()

class SymbolQualifiedLocator(SyntaxLocator):
	"""
	# Imprecise locator used to invert Python traceback frames.
	"""
	symbol:(str) = None
	precision = False

	def __init__(self, area:libsyntax.Area, symbol:str, lambda_type:str):
		self.location = area
		self.symbol = symbol
		self.lambda_type = lambda_type

	def __str__(self):
		return "SL(%s[%s]:%s)" %(self.symbol, self.lambda_type, self.location)

	def __repr__(self):
		return str(self)

	def __hash__(self):
		return hash((self.location, self.symbol, self.lambda_type))

	def __eq__(self, ob):
		return (self.location, self.symbol, self.lambda_type) == (ob.location, ob.symbol, ob.lambda_type)

class Probe(object):
	"""
	# Context manager set used by tools to manage environment variables and dependencies.
	"""
	def __init__(self, name, trap=None):
		self.name = name

	def join(self, measures):
		"""
		# Select all the collected data files from a measurements directory using the tool name.
		"""
		for x in [m_route/self.name for (m_typ, m_id, m_route) in measures]:
			yield from [(y.identifier, y) for y in x.files()]

	def setup(self, harness, data):
		"""
		# Global initialization for tool probes. Context manager used once per invocation
		# of &.bin.measure.
		"""
		return contextlib.ExitStack()

	def connect(self, harness, measures):
		"""
		# Per-test context manager used to connect to the counters managed by the tool.
		"""
		return contextlib.ExitStack()

class Measurements(object):
	"""
	# Measurement storage and access interface for &Harness instances.

	# An instance of &Measurements contains physical divisions that contains
	# the actual measurements collected. Usually physical is referring to the process
	# that caused the emission of measurement data.
	"""
	route = None

	def __init__(self, route):
		self.route = route

	def __eq__(self, ob):
		return isinstance(ob, self.__class__) and ob.route == self.route

	def init(self):
		"""
		# Select and create a root measurement directory.
		"""
		r = self.route
		if not r.exists():
			r.init('directory')

		return r

	def event(self, identifier=None, type='process-executed'):
		"""
		# Initialize a space for the process' data; a capture event.
		# Measurement events are the physical (metaphoric) windows of data
		# that make up the set.
		"""
		if identifier is None:
			pid = os.getpid()
		else:
			pid = identifier

		pr = self.route / (type + '.' + str(pid))
		pr.init('directory')

		pe = pr / '.enter'
		pe.store(b'')

		return pr

	def __iter__(self):
		"""
		# Produce the set of capture events that contributed to the measurements.
		"""

		# Directories are measurement capture events.
		return (
			(y[0][0], int(y[0][1]), y[1])
			for y in (
				(x.identifier.rsplit('.', 1), x) for x in self.route.subnodes()[0]
			)
		)

class Telemetry(object):
	"""
	# The complete set of measurements collected from a set probes(usually tests).

	# A telemetry directory contains a set of &Measurements which represent the tests
	# performed by an invocation of &.bin.measure. Each &Measurement instance contains
	# process (UNIX system process) divisions which hold raw tool specific measurements.
	"""
	route = None
	Measurements = Measurements

	def __init__(self, route):
		self.route = route

	def __eq__(self, ob):
		return isinstance(ob, self.__class__) and ob.route == self.route

	def init(self):
		"""
		# Create the telemetry directory.
		"""
		self.route.init('directory')

	def __iter__(self):
		"""
		# Produce the &Measurements instances associated with their directory name.
		# Emits pairs in the form `(directory_name, Measurement(route))`.
		"""
		return (
			(x.identifier, self.Measurements(x))
			for x in self.route.subnodes()[0]
			if x.identifier.startswith('test_')
		)

	def event(self, identifier):
		"""
		# Initialize a new set of measurements using the given identifier as the directory name.
		# Returns the created &Measurements instance.
		"""
		m = self.Measurements(self.route.container / identifier)
		m.init()
		return m

def statistics(
		data,
		modes:int=8,
		medians:int=8,
		Sequence=list,
		tuple=tuple,
		abs=abs, len=len,
		Counter=collections.Counter,
	):
	"""
	# Calculate basic statistics occasionally useful for analyzing (profile) time data.
	"""

	timings = Sequence(data)
	count = len(timings)
	timings.sort() # min/max/median
	mid = count // 2

	agg = {
		'total': sum(timings),
		'count': count,
		'minimum': timings[0],
		'maximum': timings[-1],
		'median': (tuple(timings[mid-medians:mid]), tuple(timings[mid:mid+medians])),
	}

	avg = agg['total'] / count
	agg['average'] = avg
	agg['distance'] = 0
	agg['variance'] = 0
	freq = Counter()

	for measure in timings:
		agg['distance'] += abs(measure - avg)
		agg['variance'] += (measure - avg) ** 2
		freq[measure] += 1

	# modes; a single mode might not be terribly
	# useful, but the common high frequents should be useful.
	freq = [(y, x) for x, y in freq.items()]
	freq.sort()
	agg['modes'] = (tuple(freq[:modes]), tuple(freq[-modes:])) # Most frequent and least frequent

	return agg

def source_file_map(interests:typing.Sequence[libroutes.Import]) -> typing.Mapping[str, str]:
	"""
	# Query Python for the entire package tree of all the given Import routes.

	# [Return]
	# /key
		# The sources contained within the package's (system/file)`src` directory and
		# the Python module sources found within the &interests packages.
	# /value
		# The factor's path with the source's relative path appended.
		# For example: `'project.libcpkg/main.c'`.
	"""

	# Get the full set of modules that are of interest to the perspective.
	modules = []
	fractions = []
	for r in interests:
		pkgs, mods = r.tree()
		modules.extend(pkgs)
		modules.extend(mods)
		for pkg in pkgs:
			if libfactor.composite(pkg):
				sources = libfactor.sources(pkg)
				prefix = str(sources)
				prefix_length = len(prefix)
				for s in sources.tree()[1]:
					srcstr = str(s)
					fractions.append((srcstr, str(pkg) + srcstr[prefix_length:]))

	sfm = {
		r.spec().origin: r for r in modules
	}
	sfm.update(fractions)

	return sfm

def collapse(data:typing.Mapping, merge:typing.Callable, dimensions:int=1) -> typing.Mapping:
	"""
	# Collapse dimensions in the given &data by removing
	# the specified number of &dimensions from the key and merging
	# data with the given &merge function.

	# Collapse is primarily used by &aggregates.

	# [ Parameters ]

	# /data
		# A &collections.defaultdict instance designating the data to collapse.
	# /merge
		# A callable that can combine measurements. For &collections.Counter,
		# this is &collections.Counter.update. For &list, this is &list.extend.
	"""
	collapsed = collections.defaultdict(data.default_factory)
	collapse_key = functools.lru_cache(128)(lambda x: x[:-dimensions])

	for k, v in data.items():
		merge(collapsed[collapse_key(k)], v)

	return collapsed

def aggregate(data, islice=itertools.islice):
	"""
	# Aggregate profile data using the &statistics function.
	# &data is expected to be a simple sequence of positive numbers
	# where the even indexes (and zero) are cumulative, and the odds are
	# resident.
	"""
	ctimes = statistics(islice(data, 0, None, 2))
	rtimes = statistics(islice(data, 1, None, 2))
	return (ctimes, rtimes)

def timings(data):
	context = collapse(data, list.extend)
	times_groups = {
		('floor', 'call', 'outercall', 'test'): data,
		('context', 'call', 'outercall'): context,
	}

	times_groups[('ceiling', 'call')] = collapse(context, list.extend)
	return times_groups

def counters(data):
	counts_groups = {
		('floor', 'test'): data,
		('ceiling',): collapse(data, collections.Counter.update),
	}
	return counts_groups

def coverage(counts, counters):
	"""
	# Construct coverage summary from the given set of counters.
	"""
	positives = set(counts.keys())
	zeros = set(
		key for key in counters.keys() if key not in positives
	)

	n_missing = len(zeros)
	n_counted = len(positives)

	traversable = librange.Set(([],[]))
	for x, y in counters.items():
		startl = x[0]
		stopl = y[0] or startl
		traversable.add(librange.IRange((startl,stopl)))

	traversed = librange.Set(([],[]))
	for x in positives:
		startl = x[0]
		stopl = counters_meta.get(x, (startl,))[0] or startl
		traversed.add(librange.IRange((startl,stopl)))

	untraversed = librange.Set(([],[]))
	for x in zeros:
		startl = x[0]
		stopl = counters_meta[x][0] or startl
		untraversed.add(librange.IRange((startl,stopl)))

	return (
		n_missing, n_counted, len(counters),
		traversed, untraversed, traversable,
	)

def summary(telemetry):
	"""
	# Generate coverage summary for the given telemetry.
	"""
	assert telemetry.exists()

	project_data = telemetry/'project'
	with (project_data/'source_index').open('rb') as f:
		relevant = pickle.load(f)
	with (project_data/'counters').open('rb') as f:
		countable = pickle.load(f)

	filtered = set()
	for path in countable:
		if path not in relevant:
			filtered.add(path)
	for path in filtered:
		countable.pop(path, None)

	n_counters_per_file = {f:len(v) for f,v in countable.items()}
	n_counters = sum(n_counters_per_file.values())

	counters = collections.defaultdict(collections.Counter)
	tests = set(telemetry.subnodes()[0])
	tests.discard(project_data)
	test_counters = collections.defaultdict(dict)

	# Aggregate per-file and collect for each test.
	for test in tests:
		fragment = '.'.join((telemetry.identifier, test.identifier))

		pf = test / 'counters'
		with pf.open('rb') as f:
			f_counters = pickle.load(f)

		for f, data in f_counters.items():
			if f not in relevant:
				# Filter out-of-project files.
				continue
			counters[f].update(data)
			test_counters[fragment][f] = data

	for path, counters in countable.items():
		counts = counters[path]
		yield (path,) + coverage(counts, counters)

def profile(telemetry, record='profile'):
	"""
	# Extract profile data.
	"""
	assert telemetry.exists()

	project_factor = telemetry.identifier
	project_data = telemetry/'project'
	with (project_data/'source_index').open('rb') as f:
		relevant = pickle.load(f)

	tests = set(telemetry.subnodes()[0])
	tests.discard(project_data)

	data = collections.defaultdict(lambda: collections.defaultdict(list))

	for test in tests:
		fragment = '.'.join((project_factor, test.identifier))

		pf = test / record
		with pf.open('rb') as f:
			test_data = pickle.load(f)

		for path, times_set in test_data.items():
			if path not in relevant:
				continue
			for key, times in times_set.items():
				data[path][(fragment,)+key].extend(times)

	return data

def process(
		route, project,
		defaultdict=collections.defaultdict,
		chain=itertools.chain,
		list=list, zip=zip, map=map,
	):
	"""
	# Process the telemetry.
	"""

	p = (defaultdict(list), defaultdict(collections.Counter))
	sfm = source_file_map((project,))
	test_results = defaultdict(list)

	# merge into perspectives for per-file access.
	for test in route.subdirectories():
		test_result = None
		test_project = test.identifier
		test_path = '.'.join((test_project, test.identifier))
		error = test_result.pop('error', None)
		test_results[test_project].append((test_path or None, error, test_result))

	times, counts = group(*p)

	# Aggregate the profile data and arrange it per-file.
	perfactor_times = defaultdict(lambda: defaultdict(list))
	for gid, tdata in times.items():
		tdata = list(tdata.items())
		kiter = d
		adata = map(aggregate, (x[1] for x in tdata))
		for k, times in chain(*map(aggregate, tdata.items())):
			m, *key = k
			times[None] = list(zip(gid[1:] + ('area',), key))
			permodule_times[m][gid[0]].append(times)

	perfactor_counters = defaultdict(lambda: defaultdict(list))

	return (project, (test_results, permodule_times, permodule_counts))

class Harness(testing.Harness):
	"""
	# Harness for performing test-based measurements of a set of factors.
	"""
	from ..chronometry import library as libtime

	concurrently = staticmethod(libsys.concurrently)

	def __init__(self, tools, context, telemetry, package, status):
		super().__init__(context, package, intent='metrics')
		self.tools = tools
		self.telemetry = telemetry
		self.measures = None
		self.status = status
		self._root_test_executed = False

	def _status_test_sealing(self, test):
		self.status.write('\n\t'+test.identity[len(self.package)+1:])
		self.status.flush() # need to see the test being ran right now

	def dispatch(self, test):
		faten = None
		self._status_test_sealing(test)

		# perform test in a child process
		seal = self.concurrently(lambda: self.seal(test))

		# report written to storage by child and returned to parent over a pipe.
		l = []
		report = seal(status_ref = l.append)

		if report is None:
			# child crashed or was interrupted.
			report = {'fate': 'unknown', 'impact': -1}

		pid, status = l[0]

		if os.WCOREDUMP(status):
			# Test dumped core.
			faten = 'core'
			report['fate'] = 'core'
			test.fate = self.libtest.Core(None)
			corepath = corefile.location(pid)
			if corepath is None or not os.path.exists(corepath):
				pass
			else:
				# Relocate core file to process-executed directory.
				report['core'] = corepath
				measurements = self.telemetry.event(test.identity[len(self.package)+1:])
				report_path = measurements.route / 'report.pickle'
				r = measurements.event(pid)
				os.move(corepath, r / 'core')

				# dump the report with core's snapshot.
				with report_path.open('wb') as f:
					pickle.dump(report, f)
		elif not os.WIFEXITED(status):
			# Check process-executed directory and make sure a report was generated.
			import signal
			measurements = self.telemetry.event(test.identity[len(self.package)+1:])
			r = measurements.event(pid)
			report_path = measurements.route / 'report.pickle'

			try:
				os.kill(pid, signal.SIGKILL)
			except OSError:
				pass

			if not report_path.exists():
				# No report and killed.
				report['fate'] = 'kill'
				report['pid'] = pid
				with report_path.open('wb') as f:
					pickle.dump(report, f)

		report['exitstatus'] = os.WEXITSTATUS(status)
		return report

	def seal(self, test):
		"""
		# Perform the test and store its report and measurements into
		# the configured metrics directory.
		"""

		probes = contextlib.ExitStack()
		measures = self.telemetry.event(test.identity[len(self.package)+1:])
		self.measures = process_data = measures.event()
		for x, d in self.tools:
			probes.enter_context(x.connect(self, process_data))

		os.environ['FAULT_MEASUREMENT_CONTEXT'] = str(measures)

		# Get timing of test execution.
		with probes, self.libtime.clock.stopwatch() as view:
			with test.exits:
				test.seal()

		if isinstance(test.fate, self.libtest.Fail):
			# Print to standardd and serialize as XML for the report.
			import traceback
			import sys
			fate = test.fate
			tb = traceback.format_exception(fate.__class__, fate, fate.__traceback__)
			tb = ''.join(tb)
			sys.stderr.write(tb)

			from fault.xml.python import Serialization
			xml = Serialization(xml_prefix='py:', xml_encoding='ascii')
			error = list(xml.exception(test.fate, attributes=[
					('xmlns:py', 'http://fault.io/xml/data')
				], traversed=set(
					(id(test.fate), id(xml), id(test), id(view), id(self)))
				)
			)
		else:
			error = None

		faten = test.fate.__class__.__name__.lower()

		report = {
			'test': test.identity,
			'impact': test.fate.impact,
			'fate': faten,
			'duration': int(view()),
			'error': error,
		}

		r = measures.route / 'report.pickle'
		with r.open('wb') as f:
			pickle.dump(report, f)

		if isinstance(test.fate, self.libtest.Divide):
			# subtests
			self.execute(test.fate.content, ())
