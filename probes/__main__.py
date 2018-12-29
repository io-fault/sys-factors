"""
# Instantiate the standard set of construction context probes.
"""
import sys

from fault.system import process
from fault.system import libfactor
from fault.system import files
from fault.system import python

from fault.xml import lxml
from fault.text import library as libtxt
from fault.text import xml as txtxml

def emit(route, elements):
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

def process(document, route):
	element = lxml.Query(document, txtxml.namespaces)
	chapter = element.first('/txt:chapter')
	if not chapter:
		return
	(route / '__init__.py').store(b'')

	p = "/txt:chapter/txt:section[@identifier]"
	for section in element.select(p):
		sid, = section.select('@identifier')
		emit(route / sid, section.select('txt:dictionary'))

def main(inv:process.Invocation) -> process.Exit:
	try:
		route, *ignored = inv.args
	except:
		inv.exit(process.Exit.exiting_from_bad_usage)

	route = files.Path.from_path(route)
	documents = libfactor.selected(python.Import.from_fullname(__name__))

	dirs, files = documents.tree()
	for f in files:
		doc = lxml.readfile(str(f))
		bname = f.identifier[:-(len(f.extension)+1)]
		process(doc, route / bname)

	inv.exit(process.Exit.exiting_from_success)

if __name__ == '__main__':
	process.control(main, process.Invocation.system())
