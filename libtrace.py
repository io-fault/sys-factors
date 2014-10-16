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

try:
	try:
		import _thread as thread
	except ImportError:
		import thread
	import threading
except ImportError:
	pass

import routes.lib
import rhythm.kernel
import nucleus.lib

from . import libmeta
from . import trace

class Collector(object):
	def __init__(self, endpoint, time_delta):
		self.endpoint = endpoint
		self.delta = time_delta
		self._partial = functools.partial(self._collect, endpoint, self.delta)
		raise Exception("python collector needs an event-id mapping")

	def _collect(self, append, time_delta, frame, event, arg, event_map = None):
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
			event_map[event], arg, time_delta(),
		))
		return self._partial

	def __call__(self, *args):
		# __call__ methods aren't particularly efficient, so we return self._partial
		# in the future.
		return self._partial(*args)

	def install(self):
		sys.settrace(self)

crealpath = functools.lru_cache(1024)(os.path.realpath)

class Tracing(object):
	"""
	Manage the tracing of a Python process.
	"""
	def __init__(self, package, cause):
		self.collections = None
		self.package = package
		self.cause = cause
		self.tracing = False
		self.pkgroute = routes.lib.Import.from_fullname(self.package).file().container
		self.directory = self.pkgroute.fullpath
		self.exopath = (self.pkgroute / '__exosource__').fullpath

	def __enter__(self):
		self.collections = collections.deque()
		__builtins__['TRACE'] = self

		self._orig_start_new_threads = (thread.start_new_thread, threading._start_new_thread)
		thread.start_new_thread = threading._start_new_thread = self._start_new_thread_override

		nucleus.lib.fork_child_callset.add(self.truncate)
		self.trace()

	def __exit__(self, typ, val, tb):
		sys.settrace(None)
		del __builtins__['TRACE']
		nucleus.lib.fork_child_callset.remove(self.truncate)

		thread.start_new_thread, threading._start_new_thread = self._orig_start_new_threads

		while self.collections:
			self.aggregate(self.collections.popleft())

	def _thread(self, f, args, kwargs):
		self.trace()
		try:
			if kwargs:
				f(*args, **(kwargs[0]))
			else:
				f(*args)
		finally:
			sys.settrace(None)

	def truncate(self, _truncate = operator.methodcaller("clear")):
		"""
		Destroy all collected data.

		Usually this should be called after :manpage:`fork(2)` when tracing.
		"""
		if self.collections is not None:
			list(map(_truncate, self.collections))

	@staticmethod
	def _start_new_thread_override(f, args, *kwargs, _notrace = thread.start_new_thread):
		T = __builtins__.get('TRACE')
		if T:
			return T._orig_start_new_threads[0](T._thread, (f, args, kwargs))
		else:
			return _notrace(f, args, *kwargs)

	@functools.lru_cache(512)
	def relevant(self, path, crealpath = crealpath):
		return crealpath(path).startswith(self.directory)

	def aggregate(self, events,
		TRACE_LINE = trace.TRACE_LINE,

		TRACE_CALL = trace.TRACE_CALL,
		TRACE_RETURN = trace.TRACE_RETURN,
		TRACE_EXCEPTION = trace.TRACE_EXCEPTION,

		TRACE_C_CALL = trace.TRACE_C_CALL,
		TRACE_C_RETURN = trace.TRACE_C_RETURN,
		TRACE_C_EXCEPTION = trace.TRACE_C_EXCEPTION,
		crealpath = crealpath
	):
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

			if event == TRACE_LINE:
				line_counts[filename][lineno] += 1
			elif event in {TRACE_CALL, TRACE_C_CALL}:
				line_counts[filename][lineno] += 1
				call_times[(modname, filename, func_lineno, func_name)]['count'] += 1
				# push call state
				call_state.append(0)
				subcall_state.append(0)
			elif event in {TRACE_RETURN, TRACE_C_RETURN}:
				line_counts[filename][lineno] += 1

				# pop call state, inherit total
				sum = call_state.pop()
				if not call_state:
					call_state.append(0)
				# subcall does not inherit
				call_state[-1] += sum

				# get our inner state; sometimes consistent with call_state
				inner = subcall_state.pop()
				if not subcall_state:
					subcall_state.append(0)

				timing = call_times[(modname, filename, func_lineno, func_name)]
				timing['cumulative'] += sum
				timing['resident'] += inner
				exact_call_times[(modname, filename, func_lineno, func_name)].append((sum, inner))

		for filename, lines in line_counts.items():
			evpath = crealpath(filename)
			if evpath.startswith(pkgdir):
				counts = list(lines.items())
				counts.sort()
				libmeta.append(libmeta.crossed_name, evpath, [(self.cause, counts)])
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

	def trace(self, Queue = collections.deque, Collector = trace.Collector, Chronometer = rhythm.kernel.Chronometer):
		"""
		Construct event collection, add to the collections set, and set the trace.
		"""
		events = Queue()
		chronometer = Chronometer()
		collector = Collector(events.append, chronometer.__next__)
		self.collections.append(events)
		collector.install()
