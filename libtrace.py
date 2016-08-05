"""
Coverage and profiling data collection.

! WARNING:
	&Collector instances *must* be per-thread in order for &measure to
	properly calculate call timings.

Common usage:

#!/pl/python
	collector, events = libtrace.prepare()
	with collector:
		...
	aggregate = libtrace.measure(events)

[ Development Tasks ]

	- Refactor &measure as a stateful method that can be called during collection
		in order to reduce memory consumption during long runs.
	- Make use of interjection in order to perform collection maintenance
		for &measure; cancel collection, run measure, serialize new data(?), resume.

[ Properties ]

/Measurements
	A tuple of measured trace data.
"""
import sys
import collections
import functools
import typing

try:
	from . import trace # C based collector.
except ImportError:
	trace = None

# Measure uses the integer form.
event_integers = {
	'call': 0,
	'exception': 1,
	'line': 2,
	'return': 3,

	'c_call': 4,
	'c_exception': 5,
	'c_return': 6,
}

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
		global event_integers

		co = frame.f_code

		append((
			(co.co_filename, co.co_firstlineno, frame.f_lineno, co.co_name),
			event_integers[event], time_delta(),
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
		sys.setprofile(None)

	def __enter__(self):
		self.subscribe()

	def __exit__(self, *args):
		self.cancel()

sequence = (
	'total',
	'count',
	'minimum',
	'maximum',
	'median',
	'average',
	'distance',
	'variance',
	'modes',
)

def prepare(
		Sequence=list,
		Chronometer=None,
		Collector=(Collector if trace is None else trace.Collector),
	) -> typing.Tuple[Collector, typing.Sequence]:
	"""
	Construct trace event collection using a &list instance
	as the destination. This is the primary entry point for this module and should
	be used to create the necessary per-thread &Collector instances.

	[ Effects ]

	/product
		Returns a pair containing the &Collector instance and the events instance
		of the configured &Sequence type.
	"""

	if Chronometer is None:
		# import here to avoid import-time dependency.
		from ..chronometry.kernel import Chronometer

	events = Sequence()
	chronometer = Chronometer()
	collector = Collector(events.append, chronometer.__next__)

	return collector, events

Measurements = typing.Tuple[
	typing.Mapping[typing.Tuple, typing.Sequence],
	typing.Mapping[str, collections.Counter],
]

def measure(
		events:typing.Sequence,

		TRACE_LINE = trace.TRACE_LINE,

		TRACE_CALL = trace.TRACE_CALL,
		TRACE_RETURN = trace.TRACE_RETURN,
		TRACE_EXCEPTION = trace.TRACE_EXCEPTION,

		TRACE_C_CALL = trace.TRACE_C_CALL,
		TRACE_C_RETURN = trace.TRACE_C_RETURN,
		TRACE_C_EXCEPTION = trace.TRACE_C_EXCEPTION,

		IntegerSequence=list,
		deque=collections.deque,
		defaultdict=collections.defaultdict,
		Counter=collections.Counter,
	) -> Measurements:
	"""
	Measure line counts and call times from the collected trace data.

	Coverage events and profile events should be processed here.

	[ Parameters ]

	/events
		The sequence of events identified as the endpoint of a &Collector instance.
		Usually, a triple whose first key is the calling context, the second is
		the traced events, and the third is the time index.

	[ Effects ]

	/Product
		A pair consisting of the exact call times, cumulative and resident, and the line counts.

		Each item in the tuple is a mapping. The line counts is a two-level mapping
		keyed with the filename followed with the line number. The line number is a key
		to a &collections.Counter instance. The exact timings is a mapping whose keys
		are tuples whose contents are the calling context of the time measurements. The
		value of the mapping is a sequence of pairs describing the cumulative and resident
		times of the call context (key).
	"""

	call_state = deque((0,))
	subcall_state = deque((0,))

	counts = defaultdict(Counter)
	times = defaultdict(list)

	# Calculate timings and hit counts.
	path = deque()
	for x in events:
		(filename, func_lineno, lineno, func_name), event, delta = x
		call = (filename, func_lineno, func_name)

		call_state[-1] += delta
		subcall_state[-1] += delta

		if event == TRACE_LINE:
			counts[filename][lineno] += 1
		elif event in {TRACE_CALL, TRACE_C_CALL}:
			if path:
				parent = path[-1]
			else:
				parent = None
			path.append(call)

			counts[filename][lineno] += 1

			# push call state for timing measurements
			call_state.append(0)
			subcall_state.append(0)
		elif event in {TRACE_RETURN, TRACE_C_RETURN}:
			counts[filename][lineno] += 1

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

			# Record the cumulative and resident *parts*.
			# They need to be summed/aggregated for reporting purposes.
			times[(parent, call)].extend((sum, inner))

			# Pop parent.
			parent = None
			if path:
				path.pop()
				if path:
					parent = path[-1]

	return times, counts
