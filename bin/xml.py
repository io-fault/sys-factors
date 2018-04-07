"""
# XML integration and transformation command.

# Used by the default configuration to integrate the transformed sources into a single
# XML document.
"""
import sys
from fault.xml import lxml, libfactor
from fault.xml import library as libxml

def transform(document, parameters):
	"""
	# Load the given &route as an XML document and perform any necessary processing.
	"""

	# Remove elements ctl:include-if
	libxml.Control.filter(document, parameters)

	# Perform xinclude here so that the source location
	# is leveraged for relative paths.
	document.xinclude()

def integrate(document):
	"""
	# Load the given &route as an XML document and perform any necessary processing.
	"""

	# Perform inclusions (again) for root.xml.
	document.xinclude()

	# Create elements (post xincludes) and attributes from fault.io/xml/control
	libxml.Control.materialize(document)

	# Cleanup the namespaces after materialize (create elements/attributes)
	lxml.etree.cleanup_namespaces(document)

	# Remove ctl namespace and any ctl:namespaces elements.
	libxml.Control.eliminations(document)

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
