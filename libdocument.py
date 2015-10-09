"""
Extract the documentation and index of Python objects.
"""
import sys
import os
import os.path
import inspect
import functools
import itertools
import hashlib
import types

from ..routes import library as routes
from .xml import library as xml

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

	def is_class_method(self, obj,
		getfullargspec = inspect.getfullargspec,
		checks = (
			inspect.ismethod,
			inspect.isbuiltin,
			inspect.isfunction,
			inspect.ismethoddescriptor,
		)
	):
		try:
			getfullargspec(obj)
		except TypeError:
			return False

		return any(x(obj) for x in checks)

	def is_class_property(self, obj,
		checks = (
			inspect.isgetsetdescriptor,
			inspect.isdatadescriptor,
		)
	):
		return any(x(obj) for x in checks)

	def is_module_class(self, obj, module, isclass=inspect.isclass):
		"""
		The given object is a plainly defined class that belongs to the module.
		"""
		return isclass(obj) and module.__name__ == obj.__module__

	def is_module_function(self, obj, module, isroutine=inspect.isroutine):
		"""
		The given object is a plainly defined function that belongs to the module.
		"""
		return isroutine(obj) and module.__name__ == obj.__module__

	def addressable(obj,
		ismodule=inspect.ismodule,
		getmodule=inspect.getmodule,
	):
		"""
		Whether the object is independently addressable.
		Specifically, it is a module or inspect.getmodule() not return None
		*and* can `obj` be found within the module's objects.

		The last condition is used to prevent broken links.
		"""
		return ismodule(obj) or (
			getmodule(obj) is not None and \
			id(obj) in [id(v) for v in getmodule(obj).__dict__.itervalues()]
		)

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
			# try Route.project() as there is no pkg_distribution
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

def _xml_object(name, obj):
	yield from xml.element(name, xml.object(obj))

def _xml_argument(aspec, index, argname, defaults_start):
	if argname in aspec.annotations:
		yield from _xml_object('annotation', aspec.annotations[argname])

	if index >= defaults_start:
		yield from _xml_object('default', aspec.defaults[index - defaults_start])

def _xml_keywords(aspec):
	for k in aspec.kwonlyargs:
		yield from xml.element('keyword',
			itertools.chain(
				_xml_object('annotation', aspec.annotations[k]),
				_xml_object('default', aspec.kwonlydefaults[k]),
			),
			('name', k),
		)

def _xml_signature_arguments(aspec, nargs, defaults_start):
	for i in range(nargs):
		argname = aspec.args[i]
		if argname in aspec.annotations or i >= defaults_start:
			has_content = True
		else:
			has_content = False

		yield from xml.element('positional',
			_xml_argument(aspec, i, argname, defaults_start) if has_content else None,
			('name', argname),
			('index', str(i)),
		)

def _xml_call_signature(obj):
	try:
		aspec = inspect.getfullargspec(obj)
		nargs = len(aspec.args)

		if aspec.defaults is not None:
			defaults_start = nargs - len(aspec.defaults)
		else:
			defaults_start = nargs

		if aspec.annotations:
			yield from _xml_object('annotation', aspec.annotations['return'])

		yield from xml.element('signature',
			itertools.chain(
				_xml_signature_arguments(aspec, nargs, defaults_start),
			),
			('varargs', aspec.varargs),
			('varkw', aspec.varkw),
		)
	except TypeError:
		# unsupported callable
		pass

def _xml_type(obj):
	yield from xml.element('type', None,
		('name', obj.__name__),
		('module', obj.__module__),
		('path', obj.__qualname__),
	)

def _xml_doc(obj):
	doc = inspect.getdoc(obj)
	if doc is not None:
		yield from xml.element('doc', xml.escape_element_string(doc),
			('xml:space', 'preserve')
		)

def _xml_import(module, *path):
	if False:
		pkgtype = 'project-local'
	elif 'site-packages' in module.__name__:
		# *normally* distutils or distutils compliant package.
		pkgtype = 'distutils'
	else:
		pkgtype = 'builtin'

	return xml.element("import", None,
		('identifier', path[-1]),
		('name', module.__name__),
		('xml:id', '.'.join(path)),
		('source', pkgtype),
	)

def _xml_source_range(obj):
	try:
		lines, lineno = inspect.getsourcelines(obj)
		end = lineno + len(lines)

		return xml.element('source', None,
			('unit', 'line'),
			('start', str(lineno)),
			('stop', str(end)),
		)
	except TypeError:
		return xml.empty('source')

def _xml_function(method):
	yield from _xml_source_range(method)
	yield from _xml_doc(method)
	yield from _xml_call_signature(method)

def _xml_class_content(module, obj, *path):
	yield from _xml_source_range(obj)
	yield from _xml_doc(obj)

	for x in obj.__bases__:
		yield from xml.element('bases', _xml_type(x))

	for x in inspect.getmro(obj):
		yield from xml.element('order', _xml_type(x))

	aliases = []
	class_dict = obj.__dict__
	class_names = list(class_dict.keys())
	class_names.sort()
	nested_classes = []

	for k in sorted(dir(obj)):
		qn = '.'.join(path + (k,))

		if k in class_ignore:
			continue

		v = getattr(obj, k)

		if is_class_method(v):
			if v.__name__.split('.')[-1] != k:
				# it's an alias to another method.
				aliases.append((qn, k, v))
				continue
			if k not in class_names:
				# not in the immediate class' dictionary? ignore.
				continue

			# Identify the method type.
			if isinstance(v, classmethod) or k == '__new__':
				mtype = 'class'
			elif isinstance(v, staticmethod):
				mtype = 'static'
			else:
				# regular method
				mtype = None

			yield from xml.element('method', _xml_function(v),
				('xml:id', qn),
				('identifier', k),
				('type', mtype),
			)
		elif is_class_property(v):
			yield from xml.element(
				'property', _xml_doc(v),
				('xml:id', qn),
				('identifier', k),
			)
		elif inspect.ismodule(v):
			# handled the same way as module imports
			yield from _xml_import(v, k)
		else:
			pass

	for qn, k, v in aliases:
		yield from xml.element('alias', None,
			('xml:id', qn),
			('identifier', k),
			('address', v.__name__),
		)

	# _xml_class will populated nested_classes for processing
	while nested_classes:
		c = nested_classes[-1]
		del nested_classes[-1]
		yield from _xml_class(module, c, c.__qualname__)

def _xml_class(module, obj, *path):
	yield from xml.element('class',
		_xml_class_content(module, obj, *path),
		('xml:id', '.'.join(path)),
		('identifier', path[-1]),
	)

def _xml_module(module):
	with open(module.__file__, mode='rb') as src:
		h = hashlib.sha512()

		data = src.read(512)
		h.update(data)
		while len(data) == 512:
			data = src.read(512)
			h.update(data)

		hash = h.hexdigest()

	yield from xml.element('source',
		xml.element('hash',
			xml.escape_element_string(hash),
			('type', 'sha512'),
			('format', 'hex'),
		),
		('path', module.__file__),
	)

	yield from _xml_doc(module)

	# accumulate nested classes for subsequent processing
	documented_classes = set()

	for k in sorted(dir(module)):
		if k.startswith('__'):
			continue
		v = getattr(module, k)

		if is_module_function(v, module):
			yield from xml.element('function', _xml_function(v),
				('xml:id', k),
				('identifier', k),
			)
		elif inspect.ismodule(v):
			yield from _xml_import(module, k)
		elif is_module_class(v, module):
			yield from _xml_class(module, v, k)
		else:
			yield from xml.element('data', xml.object(v),
				('xml:id', k),
				('identifier', k),
			)

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

	yield from xml.element('factor',
		itertools.chain(
			xml.element('module',
				_xml_module(module),
				('xml:id', module.__name__),
				('identifier', route.basename),
			),
		),
		('domain', 'python'),
		('xmlns', 'https://fault.io/xml/documentation'),
	)

	for typ, l in zip((b'package"', b'module"'), route.subnodes()):
		for x in l:
			yield from xml.element('submodule', None,
				('type', typ),
				('identifier', x.basename),
			)

def document(path):
	"""
	Document an entire project package placing the XML files in the project's
	project:[documentation/xml] directory.
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
		raise
		e = sys.exc_info()
		import pdb
		pdb.post_mortem(e[2])

