"""
Test report rendering and validation.
"""

import itertools
from ....chronometry import library as libtime
from ....xml import library as libxml

namespace = 'https://fault.io/xml/test'

def serialize(serialization, report, timestamp=None, chain=itertools.chain.from_iterable):
	"""
	Serialize the test &report.
	"""
	xml = serialization

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
		('xmlns', namespace),
	)

# libtraceback is depended on inside the schema.
# and resolvers are not inherited inside the validation contexts.
from .. import libtraceback
del libtraceback

from ....xml import libfactor
libfactor.load('schema')
