"""
Extract the documentation and index of a given Python object.

doc-strings
argument spec - callables
type (with references)
imports
base classes and mro - classes
"""
import sys
import os
import os.path
import inspect
import functools
import hashlib
import types

from ..routes import library as routes
from . import xml

# If pkg_resources is available, use it to identify explicit namespace packages.
try:
	import pkg_resources
	def is_namespace(path):
		return path in pkg_resources._namespace_packages

	def pkg_distribution(loader):
		return pkg_resources.Distribution.from_filename(loader.archive)
except ImportError:
	# no namespace concept without pkg_resources
	def is_namespace(path):
		return False

	def pkg_distribution(loader):
		return None

class Query(object):
	"""
	Documentation query object maintaining parameters and functions for extraction.
	"""
	class_ignore = {
		'__doc__',     # Extracted explicitly.
		'__weakref__', # Runtime specific information.
		'__dict__',    # Class content.
		'__module__',  # Supplied by context.

		# Exception subclasses will have these attributes.
		'__cause__',
		'__context__',
		'__suppress_context__',
		'__traceback__',
	}

	method_order = (
		'__init__',
		'__new__',
		'__call__',
	)

	def is_class_method(self, obj):
		try:
			inspect.getfullargspec(obj)
		except TypeError:
			return False

		return \
			inspect.ismethod(obj) or \
			inspect.isbuiltin(obj) or \
			inspect.isfunction(obj) or \
			inspect.ismethoddescriptor(obj)

	def is_class_property(self, obj):
		return \
			inspect.isgetsetdescriptor(obj) or \
			inspect.isdatadescriptor(obj)

	def is_module_class(self, obj, module):
		"""
		The given object is a plainly defined class that belongs to the module.
		"""
		return \
			inspect.isclass(obj) and \
			module.__name__ == obj.__module__

	def is_module_function(self, obj, module):
		"""
		The given object is a plainly defined function that belongs to the module.
		"""
		return \
			inspect.isroutine(obj) and \
			module.__name__ == obj.__module__

class_ignore = {
	'__doc__',     # Extracted explicitly.
	'__weakref__', # Runtime specific information.
	'__dict__',    # Class content.
	'__module__',  # Supplied by context.

	# Exception subclasses will have these attributes.
	'__cause__',
	'__context__',
	'__suppress_context__',
	'__traceback__',
}

method_order = (
	'__init__',
	'__new__',
	'__call__',
)

def normalize_string(s):
	return ' '.join((x for x in s.split() if x))

def is_class_method(obj):
	try:
		inspect.getfullargspec(obj)
	except TypeError:
		return False

	return \
		inspect.ismethod(obj) or \
		inspect.isbuiltin(obj) or \
		inspect.isfunction(obj) or \
		inspect.ismethoddescriptor(obj)

def is_class_property(obj):
	return \
		inspect.isgetsetdescriptor(obj) or \
		inspect.isdatadescriptor(obj)

def is_module_class(obj, module):
	"""
	The given object is a plainly defined class that belongs to the module.
	"""
	return \
		inspect.isclass(obj) and \
		module.__name__ == obj.__module__

def is_module_function(obj, module):
	"""
	The given object is a plainly defined function that belongs to the module.
	"""
	return \
		inspect.isroutine(obj) and \
		module.__name__ == obj.__module__

@functools.lru_cache(32)
def project(module, _get_route = routes.Import.from_fullname):
	"""
	Return the project information about a particular module.

	Returns `None` if a builtin, an unregistered package, or package without a project
	module relative to the bottom.
	"""
	route = _get_route(module.__name__)

	project = None
	if hasattr(module, '__loader__'):
		d = None
		try:
			d = pkg_distribution(module.__loader__)
		except (AttributeError, ImportError):
			pass
		finally:
			if d is not None:
				return {
					'name': d.project_name,
					'version': d.version,
				}

	return getattr(route.project(), '__dict__', None)

def addressable(obj):
	"""
	Whether the object is independently addressable.
	Specifically, it is a module or inspect.getmodule() not return None
	*and* can `obj` be found within the module's objects.

	The last condition is used to prevent broken links.
	"""
	return inspect.ismodule(obj) or (
		inspect.getmodule(obj) is not None and \
		id(obj) in [id(v) for v in inspect.getmodule(obj).__dict__.itervalues()]
	)

def hierarchy(package, _get_route = routes.Import.from_fullname):
	"""
	Return a (root, (packages_list, modules_list)) tuple of the contents of the given package.
	"""
	root = _get_route(package)
	return (root, root.tree())

def _xml_escape_element_bytes(data):
	if len(data) < 256:
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
			# there were not CDATA end sequences in the data.
			yield b'<![CDATA['
			yield data
			yield b']]>'

def _xml_escape_element_string(string):
	yield from _xml_escape_element_bytes(string.encode('utf-8'))

def _xml_escape_attribute_data(string):
	string = string.replace('&', '&#38;')
	# unconditionally escape both quotations
	string = string.replace("'", '&#39;')
	string = string.replace('"', '&#34;')
	string = string.replace('<', '&#60;')
	return string.encode('utf-8')

def _xml_attribute(identifier, value):
	return identifier + b'="' + _xml_escape_attribute_data(value) + b'"'

def _xml_call_signature(obj):
	aspec = inspect.getfullargspec(obj)
	nargs = len(aspec.args)

	if aspec.defaults is not None:
		defaults_start = nargs - len(aspec.defaults)
	else:
		defaults_start = nargs

	if aspec.annotations:
		yield b'<annotation>'
		yield from xml.object(aspec.annotations['return'])
		yield b'</annotation>'

	yield b'<signature '
	if aspec.varargs is not None:
		yield b' varargs="' + aspec.varargs.encode('utf-8') + b'"'
	if aspec.varkw is not None:
		yield b' varkw="' + aspec.varkw.encode('utf-8') + b'"'
	yield b'>'

	for i in range(nargs):
		argname = aspec.args[i]
		yield b'<positional name="' + argname.encode('utf-8')
		yield b'" index="' + str(i).encode('utf-8') + b'"'

		if argname in aspec.annotations or i >= defaults_start:
			yield b'>'
			if argname in aspec.annotations:
				yield b'<annotation>'
				yield from xml.object(aspec.annotations[argname])
				yield b'</annotation>'

			if i >= defaults_start:
				yield b'<default>'
				yield from xml.object(aspec.defaults[i - defaults_start])
				yield b'</default>'

			yield b'</positional>'
		else:
			# be tidy about it being an empty element
			yield b'/>'

	for k in aspec.kwonlyargs:
		yield b'<keyword name="' + k.encode('utf-8') + b'">'

		if k in aspec.annotations:
			yield b'<annotation>'
			yield from xml.object(aspec.annotations[k])
			yield b'</annotation>'

		if aspec.kwonlydefaults:
			yield b'<default>'
			yield from xml.object(aspec.kwonlydefaults[k])
			yield b'</default>'

	yield b'</signature>'

def _xml_type(obj):
	yield b'<type name="' + obj.__name__.encode('utf-8') + b'"'
	yield b' module="' + obj.__module__.encode('utf-8') + b'"'
	yield b' path="' + obj.__qualname__.encode('utf-8') + b'"'
	yield b'/>'

def _xml_doc(obj):
	doc = inspect.getdoc(obj)
	if doc is None:
		yield b''
	else:
		yield b'<doc xml:space="preserve">'
		yield from _xml_escape_element_string(doc)
		yield b'</doc>'

def _xml_import(module, *path):
	if False:
		pkgtype = b'project-local'
	elif 'site-packages' in module.__name__:
		# *normally* distutils or distutils compliant package.
		pkgtype = b'distutils'
	else:
		pkgtype = b'builtin'

	return b''.join((
		b'<import identifier="', path[-1].encode('utf-8'), b'"',
		b' name="', _xml_escape_attribute_data(module.__name__), b'"',
		b' xml:id="', '.'.join(path).encode('utf-8'), b'"',
		b' source="', pkgtype, b'"',
		b'/>',
	))

def _xml_source_range(obj):
	try:
		lines, lineno = inspect.getsourcelines(obj)
		end = lineno + len(lines)
		return b'<source unit="line" start="' + str(lineno).encode('utf-8') + b'" stop="' + str(end).encode('utf-8') + b'"/>'
	except TypeError:
		return b'<source/>'

@functools.lru_cache(32)
def _encode(s, encoding = 'utf-8'):
	return s.encode(encoding)

def _xml_class(route, module, obj, *path):
	yield b'<class '
	yield b' xml:id="' + '.'.join(path).encode('utf-8') + b'"'
	yield b' identifier="' + path[-1].encode('utf-8') + b'"'

	yield b'>'
	yield _xml_source_range(obj)

	yield from _xml_doc(obj)

	yield b'<bases>'
	for x in obj.__bases__:
		yield from _xml_type(x)
	yield b'</bases>'

	yield b'<order>'
	for x in inspect.getmro(obj):
		yield from _xml_type(x)
	yield b'</order>'

	aliases = []
	class_dict = obj.__dict__
	class_names = list(class_dict.keys())
	class_names.sort()

	for k in sorted(dir(obj)):
		if k in class_ignore:
			continue

		v = getattr(obj, k)

		if is_class_method(v):
			if v.__name__.split('.')[-1] != k:
				# it's an alias to another method.
				aliases.append((k, v))
				continue
			if k not in class_names:
				# not in the immediate class' dictionary? ignore.
				continue

			yield b'<method'
			yield b' xml:id="'
			yield '.'.join(path + (k,)).encode('utf-8')
			yield b'" identifier="'
			yield k.encode('utf-8')

			# Identify the method type.
			if isinstance(v, classmethod) or k == '__new__':
				mtype = 'class'
			elif isinstance(obj, staticmethod):
				mtype = 'static'
			else:
				# regular method
				mtype = None

			if mtype is not None:
				yield b'" type="'
				yield _encode(mtype)

			yield b'">'

			yield _xml_source_range(v)
			yield from _xml_doc(v)
			yield from _xml_call_signature(v)
			yield b'</method>'
		elif is_class_property(v):
			yield b'<property'
			yield b' xml:id="'
			yield '.'.join(path + (k,)).encode('utf-8')
			yield b'" identifier="'
			yield k.encode('utf-8')
			yield b'">'
			yield from _xml_doc(v)
			yield b'</property>'
		elif inspect.ismodule(v):
			# handled the same way as module imports
			yield _xml_import(v, k)
		else:
			pass

	for k, v in aliases:
		yield b'<alias xml:id="' + '.'.join(path + (k,)).encode('utf-8')
		yield b'" identifier="' + k.encode('utf-8')
		yield b'" address="' + v.__name__.encode('utf-8') + b'"/>'

	yield b'</class>'

def python(route):
	"""
	Yield out a module element for writing to an XML file exporting the documentation,
	data, and signatures of the module's content.
	"""
	module = route.module()
	modtype = b'package' if module.__file__.endswith('__init__.py') else b'module'

	bottom = route.bottom()
	prefix = bottom.container.fullname
	project_package = bottom.basename

	yield b''.join((
		b'<factor domain="python" xmlns="https://fault.io/xml/documentation">',
		b'<module',
		b' identifier="', route.basename.encode('utf-8'), b'"',
		b' xml:id="', module.__name__.encode('utf-8'), b'"',
		b'>'
	))

	yield b'<source path="'
	yield module.__file__.encode('utf-8')
	yield b'"><hash type="sha512" format="hex">'

	with open(module.__file__, mode='rb') as src:
		h = hashlib.sha512()

		data = src.read(512)
		h.update(data)
		while len(data) == 512:
			data = src.read(512)
			h.update(data)

		yield h.hexdigest().encode('utf-8')
	yield b'</hash></source>'

	yield from _xml_doc(module)

	for typ, l in zip((b'package"', b'module"'), route.subnodes()):
		for x in l:
			yield b'<submodule type="' + typ + b' identifier="' + x.basename.encode('utf-8')
			yield b'"/>'

	# accumulate nested classes for subsequent processing
	documented_classes = set()
	nested_classes = []

	for k in sorted(dir(module)):
		if k.startswith('__'):
			continue
		v = getattr(module, k)

		if is_module_function(v, module):
			yield b''.join((
				b'<function identifier="', k.encode('utf-8'),
				b'" xml:id="', k.encode('utf-8'),
				b'">',
			))
			yield _xml_source_range(v)
			yield from _xml_doc(v)
			yield from _xml_call_signature(v)
			yield b'</function>'
		elif inspect.ismodule(v):
			yield _xml_import(module, k)
		elif is_module_class(v, module):
			yield from _xml_class(route, module, v, k)
			# _xml_class will populated nested_classes for processing
			while nested_classes:
				c = nested_classes[-1]
				del nested_classes[-1]
				yield from _xml_class(route, module, c, c.__qualname__)
		else:
			ident = k.encode('utf-8')
			yield b''.join((
				b'<data identifier="', ident,
				b'" xml:id="', ident,
				b'">'
			))
			yield from xml.object(v)
			yield b'</data>'

	yield b'</module></factor>'

def document(path):
	"""
	Document an entire project package placing the XML files in the project's
	:file:`documentation/xml` directory.
	"""
	r = routes.Import.from_fullname(path)
	project = r.bottom()

	root = routes.File.from_path(project.module().__file__).container
	docs = root / 'documentation'
	xml = docs / 'xml'
	xml.init(type='directory')

	tree = project.hierarchy()

if __name__ == '__main__':
	import sys
	r = routes.Import.from_fullname(sys.argv[1])
	w = sys.stdout.buffer.write
	try:
		w(b'<?xml version="1.0" encoding="utf-8"?>')
		i = python(r)
		for x in i:
			w(x)
		sys.stdout.flush()
	except:
		e = sys.exc_info()
		import pdb
		pdb.post_mortem(e[2])

