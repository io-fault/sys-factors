"""
# XML interface set for &..development.

# Provides serialization methods for project metrics: profiling, coverage, and testing.
"""
import itertools
import typing

from ..chronometry import library as libtime
from ..xml import library as libxml
from . import schemas

namespaces = libxml.document.index_namespace_labels(schemas)

def map_coverage_data(measures):
	# Coverage data is a mapping of line numbers to counts.
	# It needs to be transformed into a pair of keys and measures.

	for measure in measures:
		key = measure.pop(None)
		if key:
			for line, count in measure.items():
				yield (('line', line), ('test', key)), (('count', count),)
		else:
			for line, count in measure.items():
				yield (('line', line),), (('count', count),)

class Metrics(libxml.document.Interface):
	"""
	# System invocation descriptor.
	"""

	@staticmethod
	def serialize_profile(xml, report,
			timestamp=None, keys=None, prefix='',
			chain=itertools.chain.from_iterable
		):
		"""
		# Serialize the profiling measurements.
		"""
		key_strings = keys

		yield from xml.element('report',
			chain([
				xml.element('measurements', chain(
						xml.element('frame',
							None,
							*[('key:'+k, str(key_strings[k](v))) for k, v in keys],
							**data
						)
						for keys, data in map(lambda x: (x.pop(None, ()), x), measures)
					),
					('xml:id', prefix+str(ctx)),
				)
				for ctx, measures in report.items()
			]),
			('timestamp', (timestamp or libtime.now()).select('iso')),
			('xmlns', namespaces['metrics']),
			('xmlns:key', 'http://fault.io/xml/key'),
		)

	@staticmethod
	def serialize_coverage(xml, report,
			timestamp=None, keys=None, prefix='',
			chain=itertools.chain.from_iterable
		):
		"""
		# Serialize coverage data.
		"""
		# Essentially the same as &profile, but the line count data is structured
		# differently, so run the measures through &map_coverage_data.

		key_strings = keys

		yield from xml.element('report',
			chain([
				xml.element('measurements', chain(
						xml.element('frame',
							None,
							*[('key:'+k, str(v)) for k, v in keys] + list(data),
						)
						for keys, data in map_coverage_data(measures)
					),
					('xml:id', prefix+str(ctx)),
				)
				for ctx, measures in report.items()
			]),
			('timestamp', (timestamp or libtime.now()).select('iso')),
			('xmlns', namespaces['metrics']),
			('xmlns:key', 'http://fault.io/xml/key'),
		)

class Test(libxml.document.Interface):
	"""
	# XML Document describing the fates of executed tests.
	"""

	def serialize(xml, report, timestamp=None,
			chain=itertools.chain.from_iterable
		):
		"""
		# Serialize the test &report.
		"""

		yield from xml.element('report',
			chain([
				xml.element('context', chain(
						xml.element('test',
							error,
							# route is assumed to be anchored.
							('identifier', test if not test else '.'.join(test)),
							**data
						)
						for test, error, data in tests
					),
					('identifier', str(ctx)),
				)
				for ctx, tests in report.items()
			]),
			('timestamp', (timestamp or libtime.now()).select('iso')),
			('xmlns', namespaces['test']),
		)

# function set for cleaning up the profile data keys for serialization.
profile_key_processor = {
	'call': lambda x: x[0] if x[1] != '<module>' else 0,
	'outercall': lambda x: ':'.join(map(str, x)),
	'test': lambda x: x.decode('utf-8'),
	'area': str,
}

def load_metrics(metrics, key):
	import pickle
	pdata = cdata = tdata = None
	p = b'profile:' + key
	c = b'coverage:' + key

	if metrics.has_key(p):
		with metrics.route(p).open('rb') as f:
			try:
				pdata = pickle.load(f)
			except EOFError:
				pdata = None

	if metrics.has_key(c):
		with metrics.route(c).open('rb') as f:
			try:
				cdata = pickle.load(f)
			except EOFError:
				cdata = None

	return pdata, cdata

def materialize_metrics(xml, snapshot, test, project, cname, key, len=len):
	import pickle
	profile, coverage = load_metrics(snapshot, key)

	if coverage is not None:
		# Complete coverage data.
		untraversed = coverage.pop('untraversed', '')
		traversed = coverage.pop('traversed', '')
		traversable = coverage.pop('traversable', '')
		# instrumentation coverage data.
		fc = coverage.pop('full_counters', None)
		zc = coverage.pop('zero_counters', None)

		covxml = Metrics.serialize_coverage(xml, coverage, prefix="coverage..")

		ntravb = len(traversable)
		ntravd = len(traversed)

		coverage = xml.element(
			'coverage', covxml,
			('untraversed', str(untraversed)),
			('traversed', str(traversed)),
			('traversable', str(traversable)),

			('n-traversed', ntravd),
			('n-traversable', ntravb),
		)
	else:
		coverage = ()

	if profile is not None:
		# Complete measurements. Parts are still going to be referenced.
		profile = xml.element('profile',
			Metrics.serialize_profile(
				xml, profile, keys=profile_key_processor, prefix="profile.."),
		)
	else:
		profile = ()

	# Currently this is inconsistent from the above as
	# the tests are consolidated in the project key prefixed with 'tests:'
	# Measurements needs to be adjusted to duplicate the test data into
	# the individual test modules to avoid the extra scans.
	tests = ()

	if test or cname == project:
		tk = b'tests:' + project.encode('utf-8')

		if cname == project:
			# full test report included in project.
			data = snapshot.get(tk)
			if data is not None:
				data = pickle.loads(data)
				tests = xml.element('test',
					Test.serialize(xml, data)
				)
		else:
			# test report for the specific module.
			sub = cname
			data = snapshot.get(tk)
			if data is not None:
				data = pickle.loads(data)
				tests = xml.element('test',
					Test.serialize(xml, {
							k: v for k, v in data.items()
							if str(k).startswith(sub)
						}
					)
				)

	return coverage, profile, tests
