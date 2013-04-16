"""
Code coverage and profiling for use with libtest.

For a real coverage tool, please see coverage.py. libtrace only performs naive coverage
analysis.
"""
import sys
import os.path
import operator
import collections
import functools

import routes.lib
import rhythm.kernel

from . import libmeta
from . import trace

class Collector(object):
	def __init__(self, endpoint, time_delta):
		self.endpoint = endpoint
		self.delta = time_delta
		self._partial = functools.partial(self._collect, self.endpoint, self.delta)

	def _collect(self, append, time_delta, frame, event, arg):
		co = frame.f_code
		#if event == "line" and not relevant(co.co_filename):
			# the point of this is avoid accumulating massive of amount
			# of data that is of no interest to us.
			# yes, it costs, but the cost of not doing it....
			# XXX: alternatively, we could aggregate on the fly
		#	return self.endpoint

		s = None
		if co.co_argcount:
			name = co.co_varnames[0]
			if name in {'self', 'typ', 'type', 'Class', 'this', 'wolves'}:
				s = frame.f_locals[name]
				if not isinstance(s, type):
					s = s.__class__.__qualname__
				else:
					s = s.__qualname__

		append((
			frame.f_globals.get('__name__'), s,
			co.co_filename, co.co_firstlineno, frame.f_lineno,
			co.co_name,
			event, arg, time_delta(),
		))
		return self._partial

	def __call__(self, *args):
		# __call__ methods aren't particularly efficient, so we return self._partial
		# in the future.
		return self._partial(*args)

crealpath = functools.lru_cache(1024)(os.path.realpath)

class Trace(object):
	"""
	Package scoped tracing.
	"""
	def __init__(self, package, cause, Collector = trace.Collector):
		self.collector = None
		self.package = package
		self.cause = cause
		self.tracing = False
		self.pkgroute = routes.lib.Import.from_fullname(self.package).file().container
		self.directory = self.pkgroute.fullpath
		self.exopath = (self.pkgroute / '__exosource__').fullpath

	def __enter__(self):
		self.events = collections.deque()
		self.chronometer = rhythm.kernel.Chronometer()
		self.collector = trace.Collector(self.events.append, self.chronometer.__next__)
		#self.collector = Collector(self.events.append, self.chronometer.__next__.__call__)
		sys.settrace(self.collector)

	def __exit__(self, typ, val, tb):
		sys.settrace(None)
		self.collector = None
		self.chronometer = None
		events = self.events
		self.events = None
		self.aggregate(events)

	@functools.lru_cache(512)
	def relevant(self, path, crealpath = crealpath):
		return crealpath(path).startswith(self.directory)

	def aggregate(self, events, crealpath = crealpath):
		"""
		aggregate()

		Aggergate the data and write the meta data into associated trace directories.
		"""
		pkgdir = self.directory

		call_state = collections.deque((0,))
		subcall_state = collections.deque((0,))

		call_times = collections.defaultdict(collections.Counter)
		line_counts = collections.defaultdict(collections.Counter)
		exact_call_times = collections.defaultdict(list)

		# Do everything here.
		# It's a bit complicated because we are actually doing a few things:
		# 1. Line counts
		# 2. N-Function Calls, Cumulative Time and resident time.
		get = events.popleft
		while events:
			x = get()
			modname, Class, filename, func_lineno, lineno, func_name, event, arg, delta = x

			call_state[-1] += delta
			subcall_state[-1] += delta

			if event == "line":
				line_counts[filename][lineno] += 1
			elif event in {"call", "c_call"}:
				line_counts[filename][lineno] += 1
				call_times[(modname, filename, func_lineno, func_name)]['count'] += 1
				# push call state
				call_state.append(0)
				subcall_state.append(0)
			elif event in {"return", "c_return"}:
				line_counts[filename][lineno] += 1

				# pop call state, inherit total
				sum = call_state.pop()
				# subcall does not inherit
				call_state[-1] += sum

				# get our inner state; sometimes consistent with call_state
				inner = subcall_state.pop()

				timing = call_times[(modname, filename, func_lineno, func_name)]
				timing['cumulative'] += sum
				timing['resident'] += inner
				exact_call_times[(modname, filename, func_lineno, func_name)].append((sum, inner))

		for filename, lines in line_counts.items():
			evpath = crealpath(filename)
			if evpath.startswith(pkgdir):
				l = [
					('L' + str(k), str(v)) for (k, v) in lines.items()
				]
				libmeta.append('lines', evpath, [(self.cause, l)])
			# ignore lines outside of our package

		# group by file
		d = collections.defaultdict(list)
		for k, quantities in call_times.items():
			(modname, filename, func_lineno, func_name) = k
			c = quantities['cumulative']
			r = quantities['resident']
			n = quantities['count']

			# applies to package?
			evpath = crealpath(filename)
			if not evpath.startswith(pkgdir):
				# data regarding a file that is not in the package.
				evpath = self.exopath

			key = modname + '.' + func_name + '.L' + str(func_lineno)
			d[evpath].append((key, ','.join(map(str, (n, r, c)))))

		getitem = operator.itemgetter(0)
		# write
		for path, seq in d.items():
			seq.sort(key = getitem)
			libmeta.append('functions', path, [(self.cause, seq)])
