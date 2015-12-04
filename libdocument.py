"""
Developer APIs extracting the documentation and structure of Python objects.
"""
import sys
import os
import os.path
import inspect
import functools
import itertools
import hashlib
import types
import lzma
import codecs
import contextlib

from ..routes import library as libroutes
from ..xml import library as libxml
from ..eclectic import library as libeclectic

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
	Query set for inspecting objects for documentation generation.
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

	@staticmethod
	def module_context(route:libroutes.Import):
		"""
		Given an import route, return the context package
		and the project module.
		"""
		bottom = route.bottom()
		if bottom is None:
			return None, route
		else:
			context = bottom.container

			if not context:
				# route is likely
				return None, bottom
			else:
				return context, bottom

	def __init__(self, route):
		# initialize the package context
		# used for identifying project local references.
		self.context, self.root = self.module_context(route)
		self.prefix = self.canonical((self.context or self.root).fullname)
		self.stack = []

	@contextlib.contextmanager
	def cursor(self, name, obj):
		self.stack += (name, obj)
		try:
			yield 
		finally:
			del self.stack[-1]

	def is_class_method(self, obj:object,
			getfullargspec=inspect.getfullargspec,
			checks = (
				inspect.ismethod,
				inspect.isbuiltin,
				inspect.isfunction,
				inspect.ismethoddescriptor,
			)
		):
		"""
		Determine if the given object is a class method.
		"""
		try:
			getfullargspec(obj)
		except TypeError:
			return False

		return any(x(obj) for x in checks)

	def is_class_property(self, obj:object,
			checks = (
				inspect.isgetsetdescriptor,
				inspect.isdatadescriptor,
			)
		):
		"""
		Determine if the given object is a property.
		Get-Set Descriptors are also identified as properties.
		"""
		return any(x(obj) for x in checks)

	def is_module(self, obj:object):
		"""
		Overrideable interface to &inspect.ismodule.
		"""
		return inspect.ismodule(obj)

	def is_module_class(self, module:types.ModuleType, obj:object, isclass=inspect.isclass):
		"""
		The given object is a plainly defined class that belongs to the module.
		"""
		return isclass(obj) and module.__name__ == obj.__module__

	def is_module_function(self,
			module:types.ModuleType,
			obj:object,
			isroutine=inspect.isroutine
		):
		"""
		The given object is a plainly defined function that belongs to the module.
		"""
		return isroutine(obj) and module.__name__ == obj.__module__

	def docstr(self, obj:object):
		"""
		Variant of &inspect.getdoc that favors tab-indentations.
		"""
		rawdocs = getattr(obj, '__doc__', None)

		if rawdocs is None:
			return None
		lines = rawdocs.split('\n')

		# first non-empty line is used to identify
		# the indentation level of the entire string.
		for fl in lines:
			if fl.strip():
				break

		if fl.startswith('\t'):
			indentation = len(fl) - len(fl.lstrip('\t'))
			return '\n'.join([
				x[indentation:] for x in lines
			])
		else:
			# assume no indentation and likely single line
			return rawdocs

	if hasattr(inspect, 'signature'):
		signature_kind_mapping = {
			inspect.Parameter.POSITIONAL_ONLY: 'positional',
			inspect.Parameter.POSITIONAL_OR_KEYWORD: None, # "default"
			inspect.Parameter.KEYWORD_ONLY: 'keyword',
			inspect.Parameter.VAR_POSITIONAL: 'variable',
			inspect.Parameter.VAR_KEYWORD: 'keywords',
		}

		def signature(self, obj:object, getsig=inspect.signature):
			"""
			Overridable accessor to &inspect.getfullargspec.
			"""
			return getsig(obj)
	else:
		def signature(self, obj:object, getsig=inspect.getfullargspec):
			"""
			Overridable accessor to &inspect.getfullargspec.
			"""
			sig = getsig(obj)

	def addressable(self, obj:object, getmodule=inspect.getmodule):
		"""
		Whether the object is independently addressable.
		Specifically, it is a module or inspect.getmodule() not return None
		*and* can `obj` be found within the module's objects.

		The last condition is used to prevent broken links.
		"""
		return self.is_module(obj) or getmodule(obj) is not None

	@functools.lru_cache(64)
	def canonical(self, name:str, Import=libroutes.Import.from_fullname):
		"""
		Given an arbitrary module name, rewrite it to use the canonical
		name defined by the package set (package of Python packages).

		If there is no canonical package name, return &name exactly.
		"""

		route = Import(name)
		if getattr(route.module(), '__type__', '') == 'chapter':
			# chapter module, resolve package's module cname
			prefix = self.canonical(route.container.fullname)
			return '.'.join((prefix, route.basename))

		context, root = self.module_context(route)

		pkg = (context or root).module()
		prefix = pkg.__name__
		canonical_prefix = getattr(pkg, '__pkg_cname__', prefix)

		if name == prefix or name.startswith(prefix+'.'):
			return canonical_prefix + name[len(prefix):]

		return name

	def address(self, obj:object, getmodule=inspect.getmodule):
		"Return the address of the given object; &None if unknown."

		if self.is_module(obj):
			# object is a module.
			module = obj
			path = (self.canonical(module.__name__), None)
		else:
			module = getmodule(obj)
			path = (self.canonical(module.__name__), getattr(obj, '__name__', repr(obj)))

		return path

	def origin(self, obj:object):
		"""
		Decide the module's origin; local to the documentation site, Python's
		site-packages (distutils), or a Python builtin.
		"""
		module, path = self.address(obj)

		if module == self.prefix or module.startswith(self.prefix+'.'):
			pkgtype = 'project-local'
		else:
			m = libroutes.Import.from_fullname(module).module()
			if 'site-packages' in getattr(m, '__file__', ''):
				# *normally* distutils; likely from pypi
				pkgtype = 'distutils'
			else:
				pkgtype = 'builtin'

		return pkgtype, module, path

	@functools.lru_cache(32)
	def project(self, module:types.ModuleType, _get_route = libroutes.Import.from_fullname):
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

def hierarchy(package, _get_route = libroutes.Import.from_fullname):
	"""
	Return a (root, (packages_list, modules_list)) tuple of the contents of the given package.
	"""

	root = _get_route(package)
	return (root, root.tree())

def _xml_object_or_reference(query, obj, encoding=None, prefix=''):
	if query.addressable(obj):
		# addressable? usually type or function: make reference.
		path = query.address(obj)

		if path[0].startswith(query.prefix) or path[0][:-1] == query.prefix:
			pkgtype = 'project-local'
		else:
			# if it's installed in site-packages, it's probably distutils/pypi
			module = libroutes.Import.from_fullname(path[0]).module()
			if 'site-packages' in getattr(module, '__file__', ''):
				# *normally* distutils or distutils compliant package.
				pkgtype = 'site-packages'
			else:
				# otherwise, it's known to be part of Python itself.
				pkgtype = 'builtin'

		yield from libxml.element('reference', (),
			('source', pkgtype),
			('module', path[0]),
			('name', path[1]),
		)
	else:
		# otherwise, xml representation
		p = functools.partial(_xml_object_or_reference, query, encoding=encoding)
		yield from libxml.object(obj, subcall=p)

def _xml_object(query, name, obj):
	with query.cursor(name, obj):
		yield from libxml.element(name, _xml_object_or_reference(query, obj))

def _xml_parameter(query, parameter):
	if parameter.annotation is not parameter.empty:
		yield from _xml_object(query, 'annotation', parameter.annotation)

	if parameter.default is not parameter.empty:
		yield from _xml_object(query, 'default', parameter.default)

def _xml_signature_arguments(query, signature, km = {}):
	if signature.return_annotation is not signature.empty:
		yield from _xml_object(query, 'product', signature.return_annotation)

	for p, i in zip(signature.parameters.values(), range(len(signature.parameters))):
		yield from libxml.element('parameter',
			_xml_parameter(query, p),
			('identifier', p.name),
			('index', str(i)),
			# type will not exist if it's a positiona-or-keyword.
			('type', query.signature_kind_mapping[p.kind]),
		)

def _xml_call_signature(query, obj):
	global itertools

	try:
		sig = query.signature(obj)
	except ValueError as err:
		# unsupported callable
		yield from libxml.element('exception',
				_xml_object(query, 'subject', getattr(obj, '__dict__', obj)),
				('type', err.__class__.__name__),
				('message', str(err)),
		)
	else:
		yield from _xml_signature_arguments(query, sig)

def _xml_type(query, obj):
	# type reference
	typ, module, path = query.origin(obj)
	yield from libxml.element('reference', (),
		('source', typ),
		('module', module),
		('name', path)
	)

def _xml_doc(query, obj, prefix):
	doc = query.docstr(obj)
	if doc is not None:
		if False:
			yield from libxml.element('doc', libxml.escape_element_string(doc),
				('xml:space', 'preserve')
			)
		else:
			yield from libxml.element('doc',
				libeclectic.XML.transform('e:', doc, identify=prefix.__add__),
			)

def _xml_import(query, context_module, imported, *path):
	mn = imported.__name__

	if 'site-packages' in getattr(imported, '__file__', ''):
		# *normally* distutils or distutils compliant package.
		pkgtype = 'distutils'
	else:
		pkgtype = 'builtin'

	return libxml.element("import", None,
		('xml:id', '.'.join(path)),
		('identifier', path[-1]),
		('name', query.canonical(mn)),
		('source', pkgtype),
	)

def _xml_source_range(query, obj):
	try:
		lines, lineno = inspect.getsourcelines(obj)
		end = lineno + len(lines)

		return libxml.element('source', None,
			('unit', 'line'),
			('start', str(lineno)),
			('stop', str(end)),
		)
	except (TypeError, SyntaxError, OSError):
		return libxml.empty('source')

def _xml_function(query, method, qname):
	yield from _xml_source_range(query, method)
	yield from _xml_doc(query, method, qname+'.')
	yield from _xml_call_signature(query, method)

def _xml_class_content(query, module, obj, name, *path,
		chain=itertools.chain.from_iterable
	):
	yield from _xml_source_range(query, obj)
	yield from _xml_doc(query, obj, name+'.')

	rtype = functools.partial(_xml_type, query)
	yield from libxml.element('bases',
		chain(map(rtype, obj.__bases__)),
	)

	yield from libxml.element('order',
		chain(map(rtype, inspect.getmro(obj))),
	)

	aliases = []
	class_dict = obj.__dict__
	class_names = list(class_dict.keys())
	class_names.sort()
	nested_classes = []

	for k in sorted(dir(obj)):
		qn = '.'.join(path + (k,))

		if k in query.class_ignore:
			continue

		try:
			v = getattr(obj, k)
		except AttributeError:
			# XXX: needs tests
			yield from libxml.element('exception',
				libxml.escape_element_string(
					"erroneous identifier present in object directory"
				),
				('context', 'class'),
				('identifier', k)
			)

		if query.is_class_method(v):
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

			with query.cursor(k, v):
				yield from libxml.element('method', _xml_function(query, v, qn),
					('xml:id', qn),
					('identifier', k),
					('type', mtype),
				)
		elif query.is_class_property(v):
			local = True
			vclass = getattr(v, '__objclass__', None)
			if vclass is None:
				# likely a property
				if k not in class_names:
					local = False
			else:
				if vclass is not obj:
					local = False

			if local:
				with query.cursor(k, v):
					yield from libxml.element(
						'property',
						_xml_doc(query, v, qn+'.'),
						('xml:id', qn),
						('identifier', k),
					)
		elif query.is_module(v):
			# handled the same way as module imports
			with query.cursor(k, v):
				yield from _xml_import(query, module, v, qn)
		else:
			# data
			pass

	for qn, k, v in aliases:
		with query.cursor(k, v):
			yield from libxml.element('alias', None,
				('xml:id', qn),
				('identifier', k),
				('address', v.__name__),
			)

	# _xml_class will populated nested_classes for processing
	while nested_classes:
		c = nested_classes[-1]
		del nested_classes[-1]
		yield from _xml_class(query, module, c, path + (c.__name__,))

def _xml_class(query, module, obj, *path):
	name = '.'.join(path)
	with query.cursor(path[-1], path[-1]):
		yield from libxml.element('class',
			_xml_class_content(query, module, obj, name, *path),
			('xml:id', name),
			('identifier', path[-1]),
		)

def _xml_context(query, package, project):
	if package and project:
		pkg = package.module()
		prj = project.module()
		yield from libxml.element('context', (),
			('context', query.prefix),
			('path', query.canonical(pkg.__name__)),
			('system.path', os.path.dirname(pkg.__file__)),
			('project', getattr(prj, 'name', None)),
			('identity', getattr(prj, 'identity', None)),
			('icon', getattr(prj, 'icon', None)),
			('fork', getattr(prj, 'fork', None)),
			('contact', getattr(prj, 'contact', None)),
			('controller', getattr(prj, 'controller', None)),
			('abstract', getattr(prj, 'abstract', '')),
		)

def _xml_module(query, module, compressed=False):
	lc = 0
	if compressed:
		with open(module.__file__, mode='rb') as src:
			h = hashlib.sha512()
			x = lzma.LZMACompressor(format=lzma.FORMAT_ALONE)
			cs = bytearray()

			data = src.read(512)
			lc += data.count(b'\n')
			h.update(data)
			cs += x.compress(data)
			while len(data) == 512:
				data = src.read(512)
				h.update(data)
				cs += x.compress(data)

			hash = h.hexdigest()
			cs += x.flush()
	else:
		file = getattr(module, '__file__', None)
		if file:
			with open(module.__file__, mode='rb') as src:
				cs = src.read()
				lc = cs.count(b'\n')
				hash = hashlib.sha512(cs).hexdigest()
		else:
			hash = ""
			cs = b""
			lc = 0

	yield from libxml.element('source',
		itertools.chain(
			libxml.element('hash',
				libxml.escape_element_string(hash),
				('type', 'sha512'),
				('format', 'hex'),
			),
			libxml.element('data',
				libxml.escape_element_bytes(codecs.encode(cs, 'base64')),
				('type', 'application/x-lzma'),
				('format', 'base64'),
			),
		),
		('path', file),
		# inclusive range
		('start', 1),
		('stop', str(lc)),
	)

	if getattr(module, '__type__', None) == 'chapter':
		yield from _xml_doc(query, module, '')
	else:
		yield from _xml_doc(query, module, 'factor..')

	# accumulate nested classes for subsequent processing
	documented_classes = set()

	for k in sorted(dir(module)):
		if k.startswith('__'):
			continue
		v = getattr(module, k)

		if query.is_module_function(module, v):
			yield from libxml.element('function', _xml_function(query, v, k),
				('xml:id', k),
				('identifier', k),
			)
		elif query.is_module(v):
			yield from _xml_import(query, module, v, k)
		elif query.is_module_class(module, v):
			yield from _xml_class(query, module, v, k)
		else:
			yield from libxml.element('data', _xml_object(query, 'object', v),
				('xml:id', k),
				('identifier', k),
			)

def _submodules(route, element='subfactor'):
	for typ, l in zip(('package', 'module'), route.subnodes()):
		for x in l:
			yield from libxml.element(element, (),
				('type', typ),
				('identifier', x.basename),
			)
	else:
		mods = getattr(route.module(), '__submodules__', ())
		for x in mods:
			yield from libxml.element(element, (),
				('type', 'module'),
				('identifier', x),
			)

	if element == 'subfactor' and route.container:
		# build out siblings
		yield from _submodules(route.container, 'cofactor')

class Error(Exception):
	"""
	Containing error noting the module and object that triggered the exception.
	"""

def python(query:Query, route:libroutes.Import, module:types.ModuleType):
	"""
	Yield out a module element for writing to an XML file exporting the documentation,
	data, and signatures of the module's content.
	"""

	package = route.bottom()
	if package is None:
		project = None
	else:
		project = package / 'project'

	try:
		cname = query.canonical(module.__name__)
		# take the basename from cname in case
		# the module is the context package.
		basename = cname.split('.')[-1]
		if getattr(module, '__type__', '') == 'chapter':
			ename = 'chapter'
		else:
			ename = 'module'

		yield from libxml.element('factor',
			itertools.chain(
				_xml_context(query, package, project),
				_submodules(route),
				libxml.element(ename,
					_xml_module(query, module),
					('identifier', basename),
					('name', cname),
				),
			),
			('domain', 'python'),
			('name', cname),
			('identifier', basename),
			('xmlns:xlink', 'http://www.w3.org/1999/xlink'),
			('xmlns:py', 'https://fault.io/xml/python'),
			('xmlns:e', 'https://fault.io/xml/eclectic'),
			('xmlns', 'https://fault.io/xml/factor'),
		)
	except Exception as failure:
		raise Error(route) from failure

def document(route:libroutes.Import):
	"""
	Document the given package rewriting the prefix using the containing package's
	"canonical" attribute. This allows reasonable documentation to be generated even
	if the root package has been renamed for development purposes.
	"""

	query = Query(route)
	module = route.module()

	if module is None:
		error = None
		try:
			pass
		except ImportError as error:
			pass
		return (query.canonical(route.fullname), ())
	else:
		return (query.canonical(module.__name__), python(query, route, module))

if __name__ == '__main__':
	# document a single module
	import sys
	r = libroutes.Import.from_fullname(sys.argv[1])
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
