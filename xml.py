"Internal module for supporting XML serialization"
import itertools

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

def object(obj, constants = {None: b'<none/>', True: b'<true/>', False: b'<false/>'}):
	"Serialize an arbitrary Python object"

	if isinstance(obj, str):
		yield b'<string xml:space="preserve">'
		yield from _xml_escape_element_string(obj)
		yield b'</string>'
	elif isinstance(obj, int):
		yield b'<integer>'
		yield str(obj).encode('utf-8')
		yield b'</integer>'
	elif obj.__hash__ is not None and obj in constants:
		# int check needs to proceed this condition as hash(1) == hash(True)
		yield constants[obj]
	elif isinstance(obj, (bytes,bytearray)):
		yield b'<bytes xml:space="preserve">'
		yield from _xml_escape_element_bytes(obj)
		yield b'</bytes>'
	elif isinstance(obj, float):
		yield b'<real>'
		yield str(obj).encode('utf-8')
		yield b'</real>'
	elif isinstance(obj, tuple):
		yield b'<tuple>'
		for x in obj:
			yield from _xml_object(x)
		yield b'</tuple>'
	elif isinstance(obj, list):
		yield b'<list>'
		for x in obj:
			yield from _xml_object(x)
		yield b'</list>'
	elif isinstance(obj, dict):
		yield b'<dictionary>'
		for k, v in obj.items():
			yield b'<item>'
			yield from _xml_object(k)
			yield from _xml_object(v)
			yield b'</item>'
		yield b'</dictionary>'
	elif isinstance(obj, set):
		yield b'<set>'
		for x in obj:
			yield from _xml_object(x)
		yield b'</set>'
	elif inspect.isbuiltin(obj):
		om = inspect.getmodule(obj)
		yield b'<function name="' + (om.__name__ + '.' + obj.__name__).encode('utf-8') + b'">'
		yield b'</function>'
	else:
		yield b'<object>'
		yield from _xml_escape_element_string(repr(obj))
		yield b'</object>'
