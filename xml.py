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
