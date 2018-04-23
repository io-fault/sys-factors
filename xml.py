"""
# XML interface set for &..development.

# Provides serialization methods for project metrics: profiling, coverage, and testing.
"""
import itertools
import typing

from fault.time import library as libtime
from fault.xml import library as libxml
from . import schemas

namespaces = libxml.document.index_namespace_labels(schemas)

def map_coverage_data(measures):
	# Coverage data is a mapping of line numbers to counts.
	# It needs to be transformed into a pair of keys and measures.

	for measure in measures:
		key = measure.pop(None)
		if key:
			for area, count in measure:
				yield (('area', line), ('source', key)), (('count', count),)
		else:
			for line, count in measure.items():
				yield (('area', line),), (('count', count),)

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
	'source': str, # test identifier (origin of data)
	'area': str,
}

def coverage(xml, data):
	missed, covered, possible, zeros, total, counters = data
	covxml = Metrics.serialize_coverage(xml, counters, prefix="coverage..")

	ntravb = len(possible)
	ntravd = len(covered)

	fragment = xml.element(
		'coverage', covxml,
		('untraversed', str(missed)),
		('traversed', str(covered)),
		('traversable', str(possible)),

		('zeros', zeros),
		('total', total),
	)

	return fragment

def join_metrics(xml, query, metrics, test, project, cname, key):
	test_element = xml.element('test', Test.serialize(xml, data))
	coverage_element = Metrics.serialize_coverage(xml, coverage, prefix="coverage..")
	profile_element = xml.element('profile',
		Metrics.serialize_profile(
			xml, profile, keys=profile_key_processor, prefix="profile.."),
	)

	r = query.first('/f:factor')
	if r is None:
		return
	r = r.first('f:module|f:chapter|f:document|f:void')
	if r is None:
		return

	r = r.element

	for x in elements:
		if x:
			sub = query.structure(b''.join(x))
			r.addprevious(sub)

	return dq
