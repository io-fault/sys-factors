"""
Package files metadata interface.

This module provides easy access to updating and getting test metadata out of the
meta directories that populate the package after a project integrity run.
"""
from . import libpython
from . import slot

from ..routes import library as routeslib

crossed_name = 'crossed-lines'
crossable_name = 'possible-lines'

def coverage(package):
	ir = routeslib.Import.from_fullname(package)
	pkg, mods = ir.tree()
	pl = []
	ml = []

	missing = {}
	for x in pkg + mods:
		f = x.file()
		path = f.fullpath
		xl = slot.route(path) / crossed_name
		xb = slot.route(path) / crossable_name

		# crossable
		if xb.exists():
			# lines file exists, use this to identify crossable.
			with xb.open() as fxb:
				data = fxb.read()

			before, after = data.split('--', 1)

			lines = set([
				int(x.split()[-1])
				for x in before.split('\n')
				if x.startswith('++')
			])

			ignored = set([
				int(x.split()[-1])
				for x in after.split('\n')
				if x.startswith('++')
			])
		else:
			lines = libpython.lines(path)
			ignored = set()

		# crossed
		if xl.exists():
			with xl.open() as fo:
				xlines = [x for x in fo.read().split('\n') if x.startswith('++')]
				crossed = set([
					int(x.split()[1])
					for x in xlines
				])
				yield x.fullname, crossed, lines, ignored

def append(type, filepath, records,
	from_abs=routeslib.File.from_absolute,
	channel=':1', str=str, map=map):
	"""
	/type
		String describing the records that will be written.

	/filepath
		The absolute path of the file that the data is regarding.

	/records
		A sequence of field sequences to write to the file.
		The fields will be stored in a tab separated form and should not contain tabs.

	Append the given records to the meta data file identified by the &type and &filepath.
	"""
	metadir = slot.route(filepath)
	meta = metadir/type

	with meta.open(mode='a') as f:
		for k, v in records:
			f.write(':1 %s\n' % (k,))
			for s in v:
				f.write('++ ' + '\t'.join(map(str, s)) + '\n')
		f.write('--\n')

def creport(package):
	for module, lines, total_lines, ignored in coverage(package):
		# cover cases where crosses are reported, but
		# the analyzer filtered.
		total_lines = total_lines - ignored
		extras = lines - total_lines
		total_lines.update(extras)
		total_lines = total_lines

		missing = list(total_lines - lines)
		tn = len(total_lines)
		cn = len(lines)
		missing.sort()
		print('%s: %f %r' %(module, ((cn / (tn or 1)) * 100), missing))

if __name__ == '__main__':
	import sys
	creport(sys.argv[1])
