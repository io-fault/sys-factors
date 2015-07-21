"Internal module for supporting XML serialization"
import itertools
import inspect

def escape_element_bytes(data):
	"Escape text for storage inside an XML element."

	if len(data) < 256:
		# Small content, replace sensitive characters.
		data = data.replace(b'&', b'&#38;')
		data = data.replace(b'<', b'&#60;')
		yield data
	else:
		c = 0
		i = data.find(b']]>')
		while i != -1:
			yield b'<![CDATA['
			yield data[c:i]
			# once for CDATA end and another for the literal
			yield b']]>]]>'
			c = i
			i = data.find(b']]>', c)

		if c == 0 and i == -1:
			# there were no CDATA end sequences in the data.
			yield b'<![CDATA['
			yield data
			yield b']]>'

def escape_element_string(string):
	"Escape arbitrary data for storage inside an XML element body"
	yield from escape_element_bytes(string.encode('utf-8'))

def escape_attribute_string(string, quote='"'):
	"Escape the given string for inclusion in an attribute value. Returns &str."

	string = string.replace('&', '&#38;')

	if quote == '"':
		string = string.replace('"', '&#34;')
	elif quote == "'":
		string = string.replace("'", '&#39;')
	else:
		raise ValueError("invalid quote parameter")

	string = string.replace('<', '&#60;')
	return string

def attribute(identifier, value, quote='"', str=str):
	"Construct an XML attribute from the identifier and its value."

	att = identifier + '=' + quote
	att += escape_attribute_string(str(value)) + quote
	return att

def element(element_identifier, content, *attribute_sequence, **attributes):
	"Generate an entire element populating the body by yielding from the given content."

	att = ""
	if attribute_sequence:
		att = " "
		att += " ".join(itertools.starmap(attribute, attribute_sequence))

	if attributes:
		att += " "
		att += " ".join(itertools.starmap(attribute, attributes.items()))

	if content is not None:
		element_start = "<%s%s>" %(element_identifier, att)
		element_stop = "</%s>" %(element_identifier,)

		yield element_start.encode('utf-8')
		yield from content
		yield element_stop.encode('utf-8')
	else:
		yield ("<%s%s/>" %(element_identifier, att)).encode('utf-8')

def object(obj,
	constants={None: b'<none/>', True: b'<true/>', False: b'<false/>'},
	isbuiltin=inspect.isbuiltin,
	getmodule=inspect.getmodule,
	isinstance=isinstance,
):
	"Serialize an arbitrary Python object"

	if isinstance(obj, str):
		yield b'<string xml:space="preserve">'
		yield from escape_element_string(obj)
		yield b'</string>'
	elif isinstance(obj, int):
		yield b'<integer>'
		yield str(obj).encode('utf-8')
		yield b'</integer>'
	elif obj.__hash__ is not None and obj in constants:
		# int check needs to proceed this condition as hash(1) == hash(True)
		yield constants[obj]
	elif isinstance(obj, (bytes, bytearray)):
		yield b'<bytes xml:space="preserve">'
		yield from escape_element_bytes(obj)
		yield b'</bytes>'
	elif isinstance(obj, float):
		yield b'<real>'
		yield str(obj).encode('utf-8')
		yield b'</real>'
	elif isinstance(obj, tuple):
		yield b'<tuple>'
		for x in obj:
			yield from object(x)
		yield b'</tuple>'
	elif isinstance(obj, list):
		yield b'<list>'
		for x in obj:
			yield from object(x)
		yield b'</list>'
	elif isinstance(obj, dict):
		yield b'<dictionary>'
		for k, v in obj.items():
			yield b'<item>'
			yield from object(k)
			yield from object(v)
			yield b'</item>'
		yield b'</dictionary>'
	elif isinstance(obj, set):
		yield b'<set>'
		for x in obj:
			yield from object(x)
		yield b'</set>'
	elif isbuiltin(obj) or inspect.isroutine(obj):
		om = getmodule(obj)
		yield b'<function name="' + (om.__name__ + '.' + obj.__name__).encode('utf-8') + b'">'
		yield b'</function>'
	else:
		yield b'<object>'
		yield from escape_element_string(repr(obj))
		yield b'</object>'

def frame(frame, attribute=attribute, chain=itertools.chain.from_iterable):
	lineno = frame.f_lineno
	lasti = frame.f_lasti
	locals = frame.f_locals
	code = frame.f_code

	file = code.co_filename
	lines = ""
	#instructions = dis.get_instructions(code, lineno)

	yield from element("frame",
		chain([
			element("source", escape_element_string(lines),
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

def test(fate):
	"Yield out a fate description."
	t = fate.test
	f = fate.name
	i = fate.impact
	c = fate.code
	color = fate.color
	pass

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
