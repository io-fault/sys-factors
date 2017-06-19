"""
# Test coverage data aggregation and serialization.

# Used in conjunction with &.bin.measure and &..factors to report the collected trace data.

# [ Development Tasks ]

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
import resource
import subprocess
import types

from ..system import library as libsys
from ..system import corefile
from ..system import libfactor

from ..routes import library as libroutes
from ..filesystem import library as libfs
from ..computation import library as libc
from ..python import syntax

from . import tracing
from . import testing

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
	# Calculate basic statistics useful for analyzing time measurements.
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
		# The sources contained within the package's (filesystem/relative)`src/` directory.
	# /value
		# The factor's Python module path with the source's relative path appended.
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

def reorient(container:str, sfm:dict, input:tracing.Measurements, output:tracing.Measurements):
	"""
	# Transform per-test measurements produced by &measure
	# into per-file measurements. This essentially swaps the &container with
	# the file path while restructuring the key to be collapsible.

	# [ Parameters ]

	# /container
		# Expected to be a string identifying the source
		# of the trace data. Usually, the identity of the test,
		# the qualified name.
	# /sfm
		# A dictionary produced by &source_file_map for resolving
		# the module from the source file. This is what determines
		# which data is kept. Events from lines that do not
		# exist in any of these files are removed.
	# /output
		# The &trace.Measurements that will be updated.
	# /input
		# The source &trace.Measurements produced by &trace.Measure.
	"""
	out_times, out_counts = output
	times, counts = input

	for file, count in counts.items():
		if file not in sfm:
			continue
		out_counts[(sfm[file], container)].update(count)

	for keys, data in times.items():
		file = keys[1][0]
		if file not in sfm:
			# filter data outside of interests set.
			continue

		parent, local = keys
		if parent[0] in sfm:
			# rewrite parent to module if in map
			parent = (sfm[parent[0]], parent[1], parent[2])
		else:
			# Arguably resonable to see if the module is in our context
			# but that's not necessarily in our set of interests.
			pass

		call = local[1:]
		out_times[(sfm[file], call, parent, container)].extend(data)

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
	collapse = functools.lru_cache(128)(lambda x: x[:-dimensions])

	for k, v in data.items():
		merge(collapsed[collapse(k)], v)

	return collapsed

def isolate(measures) -> dict:
	"""
	# Construct a mapping that isolates each project's tests from each other.

	# [ Effects ]

	# /Product
		# A dictionary instance whose keys are &libroutes.Import instances referring
		# to the project containing the test. The values are a triple containing
		# the &libroutes.Import referring to the test module, the attributes that
		# select the test from the module, and the key used to access the entry
		# in the given &measures dictionary.
	"""

	project_tests = collections.defaultdict(list)

	for key in measures.keys():
		if not key.startswith(b'source:'):
			continue

		mid = key[len('source:'):].decode('utf-8')
		r, attrs = libroutes.Import.from_attributes(mid)
		r = r.anchor() # set context to project bottom package
		prj = r.context # bottom()
		project_tests[prj].append((r, attrs, key))

	return dict(project_tests)

def merge(perspective, sfm, project_entry, measures):
	"""
	# Merge the re-oriented metrics into the given perspective and return
	# the test results in a dictionary..

	# This loads the stored metrics from disk for the given test specified in &project_entry.
	"""
	import pickle
	# recollect stored coverage data and orient them relative to the project
	project, (route, test, key) = project_entry

	with measures.route(key).open('rb') as f:
		data = pickle.load(f)

	container = key[len('source:'):]
	reorient(container, sfm, data['measurements'], perspective)

	return {
		k: data.get(k) for k in {'fate', 'impact', 'duration', 'error'}
	}

def aggregate(item, islice=itertools.islice):
	global statistics

	ctimes = statistics(islice(item[1], 0, None, 2))
	rtimes = statistics(islice(item[1], 1, None, 2))

	return (
		(item[0] + ('cumulative',), ctimes),
		(item[0] + ('resident',), rtimes),
	)

def group(times, counts):
	"""
	# Construct the set of groupings for the times and counts.

	# [ Parameters ]

	# /measures
		# A mapping of test results produced by &.bin.measure.
	"""

	# recollect stored coverage data and orient them relative to the project
	context = collapse(times, list.extend)
	times_groups = {
		('floor', 'call', 'outercall', 'test'): times,
		('context', 'call', 'outercall'): context,
	}

	times_groups[('ceiling', 'call')] = collapse(context, list.extend)

	counts_groups = {
		('floor', 'test'): counts,
		('ceiling',): collapse(counts, collections.Counter.update),
	}

	return times_groups, counts_groups

def coverage(module, counts, RangeSet=libc.range.Set, irs=libc.range.inclusive_range_set):
	"""
	# Identify the uncovered units (lines) from the line counts.

	# ! DEVELOPER:
		# This is hardcoded to Python. fault.development being multi-lingual needs
		# to be able to find the necessary coverage information for arbitrary languages.

		# For gcov, the diagnostic files produced during tests runs were processed
		# and the traversed-traversable information was available at the end of the test.
		# Currently, the measurements do not collect this information as the structure of
		# extension modules have changed to a multi-file configuration.

		# Potentially, traversable information should be made available
		# prior to this point.
	"""

	traversable = syntax.apply(module.spec().origin, syntax.coverable)
	traversable = RangeSet.from_set(traversable)

	traversed = RangeSet.from_set(counts)
	traversable = traversed.union(traversable)

	untraversed = traversable - traversed

	return traversable, traversed, untraversed

def process(measures, item,
		defaultdict=collections.defaultdict, chain=itertools.chain,
		list=list, zip=zip, map=map,
	):
	"""
	# Process the isolated project data.
	"""
	project, data = item

	p = (defaultdict(list), defaultdict(collections.Counter))
	sfm = source_file_map((project,))
	test_results = defaultdict(list)

	# merge into perspectives for per-file access.
	for test in data:
		test_result = merge(p, sfm, (project, test), measures)
		ctx, test_path = test[:2]
		error = test_result.pop('error', None)
		test_results[ctx].append((test_path or None, error, test_result))

	times, counts = group(*p)

	# Aggregate the profile data and arrange it perfile.
	permodule_times = defaultdict(lambda: defaultdict(list))
	for gid, tdata in times.items():
		for k, times in chain(*map(aggregate, tdata.items())):
			m, *key = k
			times[None] = list(zip(gid[1:] + ('area',), key))
			permodule_times[m][gid[0]].append(times)

	permodule_counts = defaultdict(lambda: defaultdict(list))
	for gid, cdata in counts.items():
		for k, counts in cdata.items():
			m, *key = k

			if key:
				# Counts only have per-file-per-test at the floor.
				key = key[0].decode('utf-8') # The test generating the coverage.
			else:
				key = None
				if isinstance(m, libroutes.Import):
					# String instances are composite subfactors; Import's are Python factors.
					traversable, traversed, untraversed = coverage(m, counts)
					permodule_counts[m]['untraversed'] = untraversed
					permodule_counts[m]['traversed'] = traversed
					permodule_counts[m]['traversable'] = traversable

			fcounts = {None:key}
			fcounts.update(counts)
			permodule_counts[m][gid[0]].append(fcounts)

	return (project, (test_results, permodule_times, permodule_counts))

def prepare(metrics:libfs.Dictionary, store=pickle.dump):
	"""
	# Prepare the metrics for formatting by tools like &..factors.

	# Given a &libfs.Dictionary of collected metrics by &.metrics.Harness, process
	# it into a form that is more suitable for consumption by reporting tools.
	"""

	i = isolate(metrics)

	# Process on a per-project basis so old perspectives can be thrown away.
	for project, data in i.items():
		project_key = str(project).encode('utf-8')
		data = process(metrics, (project, data))[1]

		# project test results
		# per-module times and counts.
		test_results, pm_times, pm_counts = data
		for module, times in pm_times.items():
			m = str(module).encode('utf-8')
			with metrics.route(b'profile:'+m).open('wb') as f:
				store(times, f)

		for module, counts in pm_counts.items():
			m = str(module).encode('utf-8')
			with metrics.route(b'coverage:'+m).open('wb') as f:
				store(dict(counts), f)

		with metrics.route(b'tests:'+project_key).open('wb') as f:
			store(test_results, f)

class Harness(testing.Harness):
	"""
	# Test harness for measuring a project using its tests.
	"""
	from ..chronometry import library as libtime

	concurrently = staticmethod(libsys.concurrently)

	metrics_postprocessor = libroutes.File.which('llvm-profdata')
	@staticmethod
	def llvm_merge_profile_data(output, *inputs):
		"""
		# Return the constructed command to perform instrumentation profile data merge.

		# This is a requisite step in order to get the recordd coverage information.
		"""
		l = ['llvm-profdata', 'merge', '-instr', '-output=' + str(output)]
		l.extend(inputs)
		return l

	def __init__(self, work, measurements, package, status):
		super().__init__(package, role='metrics')
		self.work = work
		self.measurements = measurements
		self.status = status
		self.instrumentation_set = set()

	def _status_test_sealing(self, test):
		self.status.write(test.identity+'\n')
		self.status.flush() # need to see the test being ran right now

	def preload_extension(self, test_id, *args):
		mod = super().preload_extension(test_id, *args)

		m = self.work / 'llvm' / test_id
		if not m.exists():
			m.init('directory')

		mod._instrumentation_path = str(m / mod.__name__)
		mod._instrumentation_set_path(mod._instrumentation_path)
		mod._instrumentation_write()
		mod._instrumentation_reset()
		self.instrumentation_set.add(mod)

		return mod

	def dispatch(self, test):
		faten = None
		self._status_test_sealing(test)

		# seal fate in a child process

		seal = self.concurrently(lambda: self.seal(test))

		l = []
		report = seal(status_ref = l.append)

		if report is None:
			report = {'fate': 'unknown', 'impact': -1}

		pid, status = l[0]

		if os.WCOREDUMP(status):
			# fork core dumped.
			faten = 'core'
			report['fate'] = 'core'
			test.fate = self.libtest.Core(None)
			corepath = corefile.location(pid)
			if corepath is None or not os.path.exists(corepath):
				pass
			else:
				report['core'] = corepath
				rr = self.measurements.route(test.identity.encode('utf-8'))
				cr = self.measurements.route(('core:'+test.identity).encode('utf-8'))
				os.move(corepath, str(cr))
				# dump the report with core's snapshot.
				with rr.open('wb') as f:
					pickle.dump(report, f)
		elif not os.WIFEXITED(status):
			# redrum
			import signal
			try:
				os.kill(pid, signal.SIGKILL)
			except OSError:
				pass

		report['exitstatus'] = os.WEXITSTATUS(status)
		return report

	def prepare_extensions(self, test_id):
		"""
		# Prepare extensions with instrumentation for collection.

		# This sets the desintation path of the counters and resets
		# the current in memory data inside the extension.
		"""
		prefix = self.work / 'llvm' / test_id
		prefix.init('directory')
		for mod in self.instrumentation_set:
			mod._instrumentation_set_path(str(prefix / mod.__name__))
			mod._instrumentation_reset()
		return prefix

	@staticmethod
	def merge_instrumentation_metrics(work, path):
		"""
		# When collecting metrics for instrumented binaries, merge the per-test set
		# produced into a single file for each binary.

		# This performs a final merge giving a set of counters that represent the
		# counts across all test runs. When using &.bin.measure, this is performed
		# when the (system:environment)`FAULT_COVERAGE_TOTALS` is set.
		"""
		prefix = work / 'llvm'
		totals = libroutes.File.from_path(path)
		totals.init('directory')

		for cd in prefix.subnodes()[0]:
			# llvm/*
			for f in cd.subnodes()[1]:
				# llvm/*/*
				if f.extension == 'mpd':
					continue
				i = f.suffix('.mpd')
				if not i.exists():
					continue

				out = totals / f.identifier
				if not out.exists():
					# first entry, just copy.
					out.replace(i)
					continue
				tmp = out.prefix('tmp:')

				cmd = list(map(str, Harness.llvm_merge_profile_data(str(tmp), str(out), i)))
				cmd[0] = str(Harness.metrics_postprocessor)
				sp = subprocess.Popen(cmd)
				sp.wait()
				# Move tmp back
				out.replace(out.prefix('tmp:'))

		for f in totals.subnodes()[1]:
			if f.identifier.startswith('tmp:'):
				f.void()

	def flush_extensions(self, directory):
		"""
		# Iterate over the extensions writing any collected data to disk.
		# The data is written to a file determined by &prepare_extensions prior
		# to the execution of a test.

		# After the data has been written, a postprocessor is immediately ran in-place
		# to merge the data.
		"""
		if not self.instrumentation_set:
			# No instrumentation extensions loaded.
			return

		for mod in self.instrumentation_set:
			mod._instrumentation_write()

		for x in directory.subnodes()[1]:
			# Each file in this directory is the profile emitted by an extension.
			cmd = list(map(str, self.llvm_merge_profile_data(str(x) + '.mpd', x)))
			cmd[0] = str(self.metrics_postprocessor)
			sp = subprocess.Popen(cmd)
			sp.wait()

	def instrumentation_metrics(self, directory):
		"""
		# Iterate over the merged profile data in the given &directory
		# to collect the per-file measurements.
		"""
		from ..llvm import instr

		for mod in self.instrumentation_set:
			basename = mod.__name__
			data = directory / (basename + '.mpd')
			if not data.exists():
				continue

			# Each file in this directory is the profile emitted by an extension.
			yield from instr.extract_nonzero_counters(mod.__file__, str(data))

	def seal(self, test, prepare=tracing.prepare):
		"""
		# Perform the test and store its report and measurements into
		# the configured metrics directory.
		"""
		trace, events = prepare()
		subscribe = trace.subscribe
		cancel = trace.cancel

		# Get timing of test execution.
		with self.libtime.clock.stopwatch() as view:
			try:
				llmetrics = self.prepare_extensions(test.identity)
				subscribe()
				with test.exits:
					test.seal()
			finally:
				cancel()

		if isinstance(test.fate, self.libtest.Fail):
			import traceback
			import sys
			fate = test.fate
			tb = traceback.format_exception(fate.__class__, fate, fate.__traceback__)
			tb = ''.join(tb)
			sys.stderr.write(tb)
			from ..xml.python import Serialization
			xml = Serialization(xml_prefix='py:', xml_encoding='ascii')
			error = list(xml.exception(test.fate, attributes=[
					('xmlns:py', 'http://fault.io/xml/python')
				], traversed=set((id(test.fate), id(events), id(xml), id(test), id(view), id(self))))
			)
		else:
			error = None

		self.flush_extensions(llmetrics)

		faten = test.fate.__class__.__name__.lower()
		profile, coverage = tracing.measure(events)

		for path, counters in self.instrumentation_metrics(llmetrics):
			coverage[path].update({
				x[0]: x[-1]
				for x in counters
				if x[-1] is not None
			})

		report = {
			'test': test.identity,
			'impact': test.fate.impact,
			'fate': faten,
			'duration': int(view()),
			'error': error,
			'measurements': (profile, coverage)
		}

		tid = test.identity.encode('utf-8')
		with self.measurements.route(b'source:'+tid).open('wb') as f:
			pickle.dump(report, f)

		if isinstance(test.fate, self.libtest.Divide):
			# subtests
			self.execute(test.fate.content, ())

if __name__ == '__main__':
	import sys
	prepare(libfs.Dictionary.open(sys.argv[1]))
