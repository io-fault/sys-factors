"""
# Instantiate a development template.
"""
import sys
from ...system import library as libsys
from ...routes import library as libroutes
from ...xml import lxml
from ...text import library as libtxt
from ...system import libfactor
from .. import templates

namespaces = {
	'txt': 'http://fault.io/xml/text'
}

def emit(route, elements):
	element = None

	for element in elements:
		name = element.name

		if name == 'dictionary':
			for e, eid, values in element.select('txt:item', 'txt:key/text()', 'txt:value'):
				emit(route/eid, values.select('*'))
		elif name == 'literals':
			lines = [x[0] if x else '' for x in [x.text() for x in element]]
			lines = ('\n'.join(lines).encode('utf-8'))
			route.init('file')
			route.store(lines)
		elif name == 'paragraph':
			print(repr(element))
		else:
			pass

def process(document, route, target):
	element = lxml.Query(document, namespaces)
	chapter = element.first('/txt:chapter')

	p = "/txt:chapter/txt:section[@identifier='%s']" %(target[0],)
	section, = element.select(p)
	emit(route, section.select('txt:dictionary'))

def main(invocation:libsys.Invocation) -> None:
	try:
		route, template, *path = invocation.args
	except:
		invocation.exit(libsys.Exit.exiting_from_bad_usage)

	route = libroutes.File.from_path(route)
	if route.exists():
		sys.stderr.write("ERROR: path %s already exists.\n" %(str(route),))
		invocation.exit(libsys.Exit.exiting_from_output_inaccessible)

	r = libfactor.selected(libroutes.Import.from_module(templates))
	document = r / (template + '.xml')
	doc = lxml.etree.parse(str(document), lxml.parser)

	process(doc, route, path)
	invocation.exit(libsys.Exit.exiting_from_success)

if __name__ == '__main__':
	libsys.control(main, libsys.Invocation.system())
