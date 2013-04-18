"""
Package files metadata interface.

This module provides easy access to updating and getting test metadata out of the
dot-meta directories that populate the package after a developer test run.
"""
import routes.lib
from . import libpython

meta_name = '.meta'
crossed_name = 'xlines'
crossable_name = 'lines'

def route(filepath, meta_records_name = None, from_abs = routes.lib.File.from_absolute):
	"""
	route(filepath, meta_records_name = None)

	Return the Route to the file's meta entry of `meta_records_name` or the route
	to the meta directory for the given file.
	"""
	f = from_abs(filepath)
	metadir = f.container/meta_name/f.identity
	if meta_records_name is None:
		return metadir
	meta = metadir/meta_records_name
	return meta

def void(route):
	"""
	Destroy all the .__meta__ directories in the tree of the given path.
	"""
	meta = route/meta_name
	assert meta.fullpath.endswith(meta_name)
	meta.void()

	for fr in route.subnodes()[0]:
		void(fr)

def void_package(package):
	ir = routes.lib.Import.from_fullname(package)
	void(ir.package.file().container)

def void_path(path):
	fr = routes.lib.File.from_path(path)
	void(fr)

def coverage(package):
	ir = routes.lib.Import.from_fullname(package)
	pkg, mods = ir.tree()
	pl = []
	ml = []

	missing = {}
	for x in pkg + mods:
		f = x.file()
		path = f.fullpath
		xl = route(path, crossed_name)
		xb = route(path, crossable_name)

		# crossable
		if xb.exists():
			# lines file exists, use this to identify crossable.
			with xb.open() as fxb:
				lines = set([
					int(x.split()[-1])
					for x in fxb.read().split('\n')
					if x.startswith('++')
				])
		else:
			lines = libpython.lines(path)

		# crossed
		if xl.exists():
			with xl.open() as fo:
				xlines = [x for x in fo.read().split('\n') if x.startswith('++')]
				crossed = set([
					int(x.split()[1])
					for x in xlines
				])
				yield x.fullname, crossed, lines

def append(type, filepath, settings, from_abs = routes.lib.File.from_absolute):
	"""
	append(type, filepath, settings)
	"""
	f = from_abs(filepath)
	metadir = f.container/meta_name/f.identity
	meta = metadir/type

	with meta.open(mode='a') as f:
		for k, v in settings:
			f.write(':1 %s\n' % (k,))
			for s in v:
				f.write('++ ' + '\t'.join(map(str, s)) + '\n')
		f.write('--\n')

def creport(package):
	for module, lines, total_lines in coverage(package):
		missing = list(total_lines - lines)
		tn = len(total_lines)
		cn = len(lines)
		missing.sort()
		print('%s: %f %r' %(module, ((cn / (tn or 1)) * 100), missing))
