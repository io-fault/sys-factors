"""
# Reference Parameter generator for LLVM coverage instrumentation libraries.
"""
import os
import sys
import subprocess

from fault.routes import library as libroutes
from fault.system import library as libsys
from fault.xml import library as libxml

def main(inv):
	path, *args = inv.args
	imp, objpath = libroutes.Import.from_attributes(path)
	module = imp.module(trap=False)
	method = getattr(module, objpath[0])
	fp = method(*args)

	params = {
		'factors': fp,
	}

	xml = libxml.Serialization()
	xmldata = libxml.Data.serialize(xml, params)
	oi = xml.root("ctx:reference", xmldata,
		('xmlns:ctx', 'http://fault.io/xml/dev/ctx'),
		namespace=libxml.Data.namespace,
	)

	sys.stdout.buffer.writelines(oi)
	inv.exit(0)

if __name__ == '__main__':
	libsys.control(main, libsys.Invocation.system())
