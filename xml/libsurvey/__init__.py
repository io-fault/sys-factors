"""
Report grammar for serializing profile and coverage data.

The grammar is designed for formatting making XSLT processing as easy as possible.
This is nearly a direct mapping to row data for populating table elements.
The primary distinguishing factor is the explicit separation of measurements and
dimensions. This is done to simplify the acceptance of ordering parameters
to XSL transformations.
"""

import itertools
from ....chronometry import library as libtime
from ....xml import library as libxml

namespace = 'https://fault.io/xml/survey'

def profile(serialization, report,
		timestamp=None, keys=None, prefix='',
		chain=itertools.chain.from_iterable
	):
	"""
	Serialize the profiling measurements.
	"""
	xml = serialization
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
		('xmlns', namespace),
		('xmlns:key', 'https://fault.io/xml/key'),
	)

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

def coverage(serialization, report,
		timestamp=None, keys=None, prefix='',
		chain=itertools.chain.from_iterable
	):
	"""
	Serialize coverage data.
	"""
	# Essentially the same as &profile, but the line count data is structured
	# differently, so run the measures through &map_coverage_data.

	xml = serialization
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
		('xmlns', namespace),
		('xmlns:key', 'https://fault.io/xml/key'),
	)

from ....xml import libfactor
libfactor.load('schema')
