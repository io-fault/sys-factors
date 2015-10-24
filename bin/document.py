"""
Document the entire package tree into a
&fault.filesystem.library.Dictionary instance.
"""

import sys
import itertools
import os.path

from .. import libdocument
from ...filesystem import library as fslib

def main(target, package):
	docs = fslib.Dictionary.create(fslib.Hash(), os.path.realpath(target))
	root, (packages, modules) = libdocument.hierarchy(package)

	for x in itertools.chain(packages, modules):
		key = x.fullname.encode('utf-8')
		r = docs.route(key)
		r.init('file')
		with r.open('wb') as f:
			f.write(b'<?xml version="1.0" encodint="utf-8"?>')
			f.write(b''.join(libdocument.python(x)))
	return 0

if __name__ == '__main__':
	sys.exit(main(*sys.argv[1:]))
