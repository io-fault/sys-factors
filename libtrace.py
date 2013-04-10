"""
Code coverage and profiling for use with libtest.
"""
import collections
import rhythm.kernel
import functools
import sys
import routes.lib
import os.path
import configparser

class Trace(object):
	"""
	Package scoped tracing.

	Trace the execution within a particular package. The trace will only report
	information on frames that were produced by these packages.
	"""
	def __init__(self, package, cause):
		self.cause = cause # test path, normally
		self.package = package
		self.records = collections.deque()
		self.chronometer = rhythm.kernel.Chronometer()
		self.endpoint = functools.partial(self.collect, self.records.append, self.chronometer.__next__)

	def collect(self, append, time_delta, frame, event, arg):
		"""
		"""
		co = frame.f_code
		append((
			frame.f_globals['__name__'],
			co.co_filename, co.co_firstlineno, frame.f_lineno,
			co.co_name,
			event, arg, time_delta(),
		))
		return self.endpoint

	def __enter__(self):
		sys.settrace(self.endpoint)

	def __exit__(self, typ, val, tb):
		sys.settrace(None)

	def aggregate(self):
		"""
		Aggergate the data and write the meta data into associated trace directories.
		"""
		_realpath = os.path.realpath
		recs = self.records
		pop = recs.popleft

		pkg = routes.lib.Import.from_fullname(self.package)
		path = pkg.file().container

		pkgname = pkg.fullname
		prefix = path.fullpath

		line_counts = collections.defaultdict(collections.Counter)

		while recs:
			x = pop()
			modname, filename, func_lineno, lineno, func_name, event, arg, delta = x
			if event == "line":
				line_counts[filename][func_lineno] += 1

		for filename, lines in line_counts.items():
			evpath = _realpath(filename)
			if evpath.startswith(prefix):
				f = routes.lib.File.from_absolute(evpath)
				metadir = f.container/'__meta__'/f.identity
				linetrace = metadir/'lines.ini'
				conf = configparser.ConfigParser()

				with linetrace.open(mode='r+') as f:
					conf.read_file(f)
					for k, v in lines.items():
						if not conf.has_section(self.cause):
							conf.add_section(self.cause)
						conf.set(self.cause, 'L' + str(k), str(v))
					f.seek(0)
					conf.write(f)
