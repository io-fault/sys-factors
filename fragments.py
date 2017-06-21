"""
# Fragments module providing support for generating xml/fragments instances
# for source inspection purposes.
"""
import itertools
import hashlib
import codecs

def source_element(xml, route):
	"""
	# Construct a source element for serialization.

	# Used by delineation implementations in order to provide a snapshot
	# of the source that the extracted fragments were identified from.
	"""

	if route.exists():
		cs = route.load(mode='rb')
		lc = cs.count(b'\n')
		hash = hashlib.sha512(cs).hexdigest()
	else:
		hash = ""
		cs = b""
		lc = 0

	yield from xml.element('source',
		itertools.chain(
			xml.element('hash',
				[hash.encode('utf-8')],
				('type', 'sha512'),
				('format', 'hex'),
			),
			xml.element('data',
				[codecs.encode(cs, 'base64')],
				('type', None),
				('format', 'base64'),
			),
		),
		('path', str(route)),
		# inclusive range
		('start', "1"),
		('stop', str(lc)),
	)
