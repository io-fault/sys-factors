"""
Document the entire package tree into a
&..filesystem.library.Dictionary instance.
"""

import sys
import itertools
import os.path
import lzma
import types
import importlib.machinery

from .. import libdocument

from ...routes import library as libroutes
from ...eclectic import library as libeclectic
from ...xml import library as libxml
from ...filesystem import library as fslib

def main(target, package):
	docs = fslib.Dictionary.create(fslib.Hash(), os.path.realpath(target))
	root, (packages, modules) = libdocument.hierarchy(package)

	doc_modules = []
	# &.documentation packages are handled specially.
	# `.txt` files are processed in the context of their
	# containing project.
	for pkg in packages:
		td = pkg / 'documentation'
		if not td.exists():
			continue
		dr = td.directory()
		doc_pkg_module = td.module()

		dirs, files = dr.subnodes()
		rname = td.fullname
		subs = doc_pkg_module.__submodules__ = []

		# build libeclectic.Context for documentation
		for f in files:
			if f.extension != 'txt':
				continue

			# process text file
			basename = f.identity[:len(f.identity)-4]
			subs.append(basename)
			#path = '.'.join((qname, basename))
			#tr = docs.route(path.encode('utf-8'))

			dm = types.ModuleType(rname + '.' + basename)
			dm.__type__ = 'chapter' # note as chapter module
			dm.__package__ = rname
			dm.__file__ = f.fullpath
			doc_modules.append(dm.__name__)

			doc_pkg_module.__dict__[basename] = dm
			sys.modules[dm.__name__] = dm

			# @eclectic-serialization
			with f.open('r', encoding='utf-8') as input:
				dm.__doc__ = input.read()

				if False:
					with tr.open('wb') as output:
						deflate = lzma.LZMACompressor()

						output.write(deflate.compress(b''.join(
							libxml.element('factor',
								libxml.element('chapter',
									libeclectic.XML.transform('', dm.__doc__),
									('xmlns', 'https://fault.io/xml/eclectic'),
								),
							('xmlns', 'https://fault.io/xml/documentation')
						))))
						output.write(deflate.flush())

	iterdocs = map(libroutes.Import.from_fullname, doc_modules)
	for x in itertools.chain((root,), packages, modules, iterdocs):
		key, dociter = libdocument.document(x)
		key = key.encode('utf-8')

		r = docs.route(key)
		r.init('file')
		deflate = lzma.LZMACompressor()

		with r.open('wb') as f:
			# the xml declaration prefix is not written.
			# this allows stylesheet processing instructions
			# to be interpolated without knowning the declaration
			# size.
			f.write(deflate.compress(b''.join((dociter))))
			f.write(deflate.flush())

	return 0

if __name__ == '__main__':
	sys.exit(main(*sys.argv[1:]))
