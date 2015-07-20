"""
Extract retrace XML from a sequence of frames.
"""
import dis
import inspect
import linecache
import itertools

from . import xml

def traceback_frames(tb, getinnerframes=inspect.getinnerframes):
	return getinnerframes(tb)

def stack_frames(level=2, stack=inspect.stack):
	s = stack()
	del s[:-level]
	return s

def frame(frame, attribute=xml.attribute):
	lineno = frame.f_lineno
	lasti = frame.f_lasti
	locals = frame.f_locals
	code = frame.f_code

	file = code.co_filename
	lines = ""
	#instructions = dis.get_instructions(code, lineno)

	yield from xml.element("frame",
		itertools.chain.from_iterable([
			xml.element("source", xml.escape_element_string(lines),
				('xlink:href', ""),
				absolute=lineno,
				relative=-1,
				file=file),
			xml.element("instructions", None, type="pythong-bytecode")
		]),
		identifier=code.co_name
	)

def traceback(frames):
	yield from xml.element("traceback",
		itertools.chain.from_iterable((frame(x[0]) for x in frames))
	)

def snapshot(stacks, filter=None):
	"Yield out a snapshot of the current frames."
	yield b'<snapshot>'
	for x in stacks:
		yield from traceback(x)
	yield b'</snapshot>'

if __name__ == '__main__':
	import sys

	try:
		cause_exception()
	except:
		exc, val, tb = sys.exc_info()

	frames = traceback_frames(tb)

	try:
		for x in snapshot([frames]):
			sys.stdout.buffer.write(x)
	except:
		print('error')
		raise

	sys.stdout.buffer.write(b'\n')
	sys.stdout.flush()
