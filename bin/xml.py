"""
XML integration and transformation command.

Used by the default configuration to integrate the transformed sources into a single
XML document.
"""
import sys
from ...xml import lxml, libfactor
from ...xml import library as libxml

def transform(document, parameters):
	"""
	Load the given &route as an XML document and perform any necessary processing.
	"""

	# Remove elements ctl:include-if
	libxml.Control.filter(document, vd)

def integrate(document):
	"""
	Load the given &route as an XML document and perform any necessary processing.
	"""

	# Perform inclusions.
	document.xinclude()
	# Create elements and attributes from fault.io/xml/control
	libxml.Control.materialize(document)
	# Cleanup the namespaces after materialize (create elements/attributes)
	lxml.etree.cleanup_namespaces(document)

if __name__ == '__main__':
	cmd = sys.argv[1] # integrate or transform
	out, input, *vars = sys.argv[2:]
	vd = dict(zip(vars[0::2], vars[1::2]))
	document = libfactor.readfile(str(input))

	if cmd == 'integrate':
		integrate(document)
		with open(str(out), 'wb') as f:
			document.write_c14n(f, with_comments=False)
	elif cmd == 'transform':
		transform(document, vd)
		with open(str(out), 'wb') as f:
			document.write(f)

	raise SystemExit(0)
