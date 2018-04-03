"""
# Instantiate a development template.
"""
import sys
from ...system import library as libsys
from ...routes import library as libroutes
from ...xml import lxml
from ...text import library as libtxt
from ...text import xml as txtxml
from ...system import libfactor
from .. import templates

def emit(route, elements, context=None):
	element = None

	for element in elements:
		name = element.name

		if name == 'dictionary':
			for e, eid, values in element.select('txt:item', 'txt:key/text()', 'txt:value'):
				emit(route/eid, values.select('*'))
		elif name == 'literals':
			lines = [x if x else '' for x in [x.first('text()') for x in element]]
			lines = ('\n'.join(lines).encode('utf-8'))
			route.init('file')
			route.store(lines)
		else:
			pass

def process(document, route, target):
	element = lxml.Query(document, txtxml.namespaces)
	chapter = element.first('/txt:chapter')

	p = "/txt:chapter/txt:section[@identifier='%s']" %(target[0],)
	section, = element.select(p)
	emit(route, section.select('txt:dictionary'))

def main(invocation:libsys.Invocation) -> None:
	try:
		route, template, *path = invocation.args
	except:
		return invocation.exit(libsys.Exit.exiting_from_bad_usage)

	route = libroutes.File.from_path(route)
	if route.exists():
		sys.stderr.write("ERROR: path %s already exists.\n" %(str(route),))
		return invocation.exit(libsys.Exit.exiting_from_output_inaccessible)

	r = libfactor.selected(libroutes.Import.from_module(templates))
	document = r / (template + '.xml')
	doc = lxml.readfile(str(document))

	process(doc, route, path)
	return invocation.exit(libsys.Exit.exiting_from_success)

if __name__ == '__main__':
	libsys.control(main, libsys.Invocation.system())
