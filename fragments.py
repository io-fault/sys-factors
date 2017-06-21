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

	yield from xml.prefixed('source',
		itertools.chain(
			xml.prefixed('hash',
				[hash.encode('utf-8')],
				('type', 'sha512'),
				('format', 'hex'),
			),
			xml.prefixed('data',
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

def remove_common_indentation(lines):
	"""
	# Remove the leading indentation level from the given lines.
	"""

	# first non-empty line is used to identify
	# the indentation level of the entire string.
	for fl in lines:
		if fl.strip():
			break

	if fl.startswith('\t'):
		indentation = len(fl) - len(fl.lstrip('\t'))
		return [x[indentation:] for x in lines]
	else:
		# presume no indentation and likely single line
		return lines

def strip_notation_prefix(lines, prefix='# '):
	"""
	# Remove the comment notation prefix from a sequence of lines.
	"""

	pl = len(prefix)
	return [
		(('\t'*(xl-len(y))) + y[pl:] if y[:pl] == prefix else x)
		for xl, x, y in [
			(len(z), z, z.lstrip('\t'))
			for z in lines
		]
	]

def normalize_documentation(lines, prefix='# '):
	"""
	# Remove the leading indentation level from the given lines.
	"""

	# first non-empty line is used to identify
	# the indentation level of the entire string.
	for fl in lines:
		if fl.strip():
			break

	if fl.startswith('\t'):
		indentation = len(fl) - len(fl.lstrip('\t'))
		plines = strip_notation_prefix([x[indentation:] for x in lines], prefix=prefix)
		return plines
	else:
		# assume no indentation and likely single line
		plines = strip_notation_prefix(lines, prefix=prefix)
		return plines
