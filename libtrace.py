"""
Code coverage and profiling for use with &.libtest and &..factors.

The serialization process accounts for two perspectives: the test, and the factor.
This allows &..factors to provide actual dependents of a given factor.
"""
import sys
import operator
import collections
import functools
import typing

try:
	from . import trace # C based collector.
except ImportError:
	trace = None

class Collector(object):
	"""
	Python collector. &trace.Collector is used when available.
	"""

	def __init__(self, endpoint, time_delta):
		self.endpoint = endpoint
		self.delta = time_delta
		self._partial = functools.partial(self._collect, endpoint, self.delta)

	# append and time_delta are provided in partial.
	def _collect(self,
			append, time_delta,
			frame, event, arg,
			event_map=None,
			isinstance=isinstance,
		):
		co = frame.f_code

		append((
			(co.co_filename, co.co_firstlineno, frame.f_lineno, co.co_name),
			event, time_delta(),
		))

		# None return cancels the trace.
		return self._partial

	def __call__(self, *args):
		# __call__ methods aren't particularly efficient, so we return self._partial
		# in the future.
		return self._partial(*args)

	def subscribe(self):
		"Subscribe to all events."
		sys.settrace(self)

	def profile(self):
		"Subscribe to profile data only."
		sys.setprofile(self)

	def cancel(self):
		"Cancel the collection of data in the current thread."
		sys.settrace(None)

sequence = (
	'cumulative',
	'resident',
	'count',
	'cmin',
	'cmax',
	'cdst',
	'cvar',
	'rmin',
	'rmax',
	'rdst',
	'rvar',
)

def prepare(
		Queue=collections.deque,
		Chronometer=None,
		Collector=(Collector if trace is None else trace.Collector),
	):
	"""
	Construct trace event collection using a &collections.deque instance
	as the destination.

	[ Return ]

	Returns a pair containing the &Collector instance and the events instance
	of the configured &Queue type.
	"""

	if Chronometer is None:
		# import here to avoid import-time dependency.
		from ..chronometry.kernel import Chronometer

	events = Queue()
	chronometer = Chronometer()
	collector = Collector(events.append, chronometer.__next__)

	return collector, events

def measure(
		events:collections.deque,

		TRACE_LINE = trace.TRACE_LINE,

		TRACE_CALL = trace.TRACE_CALL,
		TRACE_RETURN = trace.TRACE_RETURN,
		TRACE_EXCEPTION = trace.TRACE_EXCEPTION,

		TRACE_C_CALL = trace.TRACE_C_CALL,
		TRACE_C_RETURN = trace.TRACE_C_RETURN,
		TRACE_C_EXCEPTION = trace.TRACE_C_EXCEPTION,

		getitem=operator.itemgetter(0),
		list=list, str=str,
		map=map, max=max, abs=abs, len=len,
		deque=collections.deque,
		defaultdict=collections.defaultdict,
		Counter=collections.Counter,
	) -> (dict, dict, dict):
	"""
	Measure exact line count and group call times.

	Coverage events and profile events should be processed here.

	[ Return ]

	A triple consisting of the call times, exact call times, and the line counts.
	Each item in the tuple is a mapping. The line counts is a two-level dictionary
	keyed with the filename followed with the line number. The line number is a key
	of a &collections.Counter instance.
	"""
	call_state = deque((0,))
	subcall_state = deque((0,))

	call_times = defaultdict(Counter)
	line_counts = defaultdict(Counter)
	exact_call_times = defaultdict(list)

	# Do everything here.
	# It's a bit complicated because we are actually doing a few things:
	# 1. Line counts
	# 2. N-Function Calls, Cumulative Time and resident time of said calls.
	get = events.popleft
	path = collections.deque()
	while events:
		x = get()
		(filename, func_lineno, lineno, func_name), event, delta = x
		call = (filename, func_lineno, func_name)

		call_state[-1] += delta
		subcall_state[-1] += delta

		if event == TRACE_LINE:
			line_counts[filename][lineno] += 1
		elif event in {TRACE_CALL, TRACE_C_CALL}:
			if path:
				parent = path[-1]
			else:
				parent = None
			path.append(call)

			line_counts[filename][lineno] += 1
			call_times[(parent, call)]['count'] += 1
			# push call state
			call_state.append(0)
			subcall_state.append(0)
		elif event in {TRACE_RETURN, TRACE_C_RETURN}:
			parent = None
			if path:
				path.pop()
				if path:
					parent = path[-1]

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

			timing = call_times[(parent, call)]
			timing['cumulative'] += sum
			timing['resident'] += inner

			# Counter() defaults to zero, so explicitly check for existence.
			if 'rmin' not in timing or timing['rmin'] > inner:
				timing['rmin'] = inner
			if 'cmin' not in timing or timing['cmin'] > inner:
				timing['cmin'] = sum

			timing['rmax'] = max(inner, timing['rmax'])
			timing['cmax'] = max(sum, timing['cmax'])

			exact_call_times[(parent, call)].append((sum, inner))

	return call_times, exact_call_times, line_counts

def profile_aggregate(
		call_times:dict,
		exact_call_times:dict,

		median:bool=False,
		mode:bool=False,

		abs=abs, len=len, list=list,
		Counter=collections.Counter,
		get0=operator.itemgetter(0),
		get1=operator.itemgetter(1),
	):
	"""
	Update the &call_times dictionary with data from
	&exact_call_times. Adds distance from average and variance
	fields.

	The &median and &mode keywords can be used to enable the
	calculation of those statistics.
	"""

	# perform the calculations
	for key, agg in call_times.items():
		xct = exact_call_times[key]
		n = len(xct)
		if not n:
			continue

		cfreq = Counter()
		rfreq = Counter()

		caverage = agg['cumulative'] / n
		raverage = agg['resident'] / n
		for cumulative, resident in xct:
			agg['cdst'] += abs(cumulative - caverage)
			agg['rdst'] += abs(resident - raverage)
			agg['cvar'] += (cumulative - caverage) ** 2
			agg['rvar'] += (resident - raverage) ** 2
			cfreq[cumulative] += 1
			rfreq[resident] += 1

		# mode and median does't seem to be particularly useful,
		# so don't bother calculating them for the report.
		if mode or median:
			cfreq = list(cfreq.items())
			rfreq = list(rfreq.items())

		if mode:
			# modes
			cfreq.sort(key=get1)
			rfreq.sort(key=get1)
			agg['cmode'] = cfreq[0]
			agg['rmode'] = rfreq[0]

		# medians
		if median:
			cfreq.sort(key=get0)
			rfreq.sort(key=get0)
			index, remainder = divmod(n, 2)
			agg['cmedian'] = cfreq[n//2]
			agg['rmedian'] = rfreq[n//2]
