"""
Module for working with Tracebacks and stacks of Frames.

Useful for Python crash reporting and debuggers.
"""

class Filter(object):
	__slots__ = ()

	def __new__(typ):
		return typ._x
Filter._x = object.__new__(Filter)
assert Filter() is Filter()

class Snapshot(object):
	"""
	A snapshot of a single Frame. Traceback and Frames should be converted
	to instances of this type.
	"""

	def __init__(self, name, classname, lineno, locals, globals):
		pass

	def __str__(self):
		"""
		String Representation for printing to simple display devices. (No style support)
		"""
		pass

	def __repr__(self):
		super().__repr__()

class Stack(object):
	"""
	A stack of Snapshots.
	"""

class Traceback(Stack):
	"""
	A stack derived from a Traceback.
	"""

	def __init__(self, traceback):
		super().__init__(frames)

class Frame(Stack):
	"""
	A stack derived from a Frame.
	"""

	def __init__(self, frame):
		pass
