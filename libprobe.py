"""
Probe the C environment with Python.
"""
import sys
import os
import os.path
import collections
import tempfile
import contextlib
import pickle

from .sysconfig import Toolset

include_template = """
#ifndef {1}
#include <{0}>
#define {1}
#endif
"""
def render_includes(headers, template = include_template):
	return '\n'.join([
		template.format(x, '_py_header_filter_' + x.replace('.', '_').replace('/', '__'))
		for x in headers
	])
del include_template

module_template = """

#define _pybool_(X) (X ? Py_True : Py_False); Py_INCREF(ob)
#define _str_(X) #X
#define _pass_(X) X
#define _static_data_(D) PyBytes_FromStringAndSize((char *) &(D), sizeof(D))

METHODS() = {
	{NULL}
};

static PyObject * _module_body(PyObject *mod);
INIT("A Probe")
{
	return(_module_body(CREATE_MODULE()));
}
PyObject *_module_body(PyObject *mod) /* generated body concatenated */

"""
def render_module(context, main, template = module_template):
	return ''.join((context, template, main))

#: Type Mappings for extracting the constructed object to be consumed.
types = {
	"bool" : {
		'api': '_pybool_',
	},
	"bytes" : {
		'api': '_static_data_',
		'cast': '',
	},
	"string" : {
		'api' : 'PyUnicode_FromString',
		'cast': '',
	},
	"bytestring" : {
		'api' : 'PyBytes_FromString',
		'cast': '',
	},
	"long" : {
		'api' : 'PyLong_FromLong',
		'cast': '(long)',
	},
	"unsigned long" : {
		'api' : 'PyLong_FromUnsignedLong',
		'cast': '(unsigned long)',
	},
	"long long" : {
		'api' : 'PyLong_FromLongLong',
		'cast': '(PY_LONG_LONG)',
	},
	"unsigned long long" : {
		'api' : 'PyLong_FromUnsignedLongLong',
		'cast': '(unsigned PY_LONG_LONG)',
	},
	"size_t" : {
		'api' : 'PyLong_FromSize_t',
		'cast': '(size_t)',
	}
}

# varying depth defaultdict, essentially.
class Report(object):
	__slots__ = ('tree',)

	def __init__(self, initial = None):
		if initial is None:
			self.tree = {}
		else:
			self.tree = initial

	def get(self, *path, default = None):
		d = self.tree
		for x in path:
			d = d.get(x)
			if d is None:
				return default
		return d

	def update(self, sequence):
		# a bit slow, but let's keep it simple
		root = self.tree
		for *path, tailkey, subject in sequence:
			d = root
			for x in path:
				if x in d:
					d = d[x]
				else:
					d[x] = {}
					d = d[x]
			d[tailkey] = subject

class Sensor(object):
	"""
	A Sensor is a collection of tests that are used to collect information
	about the C environment with respect to a sequence of headers. The facets
	detected by the set.
	"""

	# pure compilation check
	has_type = """
{type} n;
	PyList_Append(payload, Py_BuildValue("ssO", "type", {typestr}, Py_True));
"""

	is_macro = """
#ifdef {macro}
	ob = Py_True;
#else
	ob = Py_False;
#endif
	PyList_Append(payload, Py_BuildValue("ssO", "macro", {macrostr}, ob));
"""

	select_template = """
ob = {api}({cast} {selection});
PyList_Append(payload, Py_BuildValue("ssO", "select", {selectionstr}, ob));"
"""

	struct_field_query_template = """
{struct} structure;
PyObject *size, PyObject *position
size = PyLong_FromSize_t(sizeof(structure.{field}));
position = PyLong_FromUnsignedLong((unsigned long) (&(structure.{field}) - &(structure)));
ob = PyTuple_New(2);
PyTuple_SET_ITEM(ob, 0, size);
PyTuple_SET_ITEM(ob, 1, position);
PyList_Append(payload, Py_BuildValue("sssO", "struct", {structstr}, {fieldstr}, ob));"
"""

	main = """
	PyObject *payload = PyList_New();
"""

	def __init__(self,
		headers,
		macros = [],
		struct = {},
		select = {},
		arbitrary = {},
	):
		self.headers = headers
		self.struct = struct
		self.select = select
		self.macros = set()
		self.arbitrary = arbitrary

class Probe(object):
	"""
	A collection of :py:class:`Sensor` instances used within a particular configuration.
	"""
	# XXX: Cross probe header check cache?

	def __init__(self, **sensors):
		self.sensors = sensors

	def construct(self, name, path):
		from .loader import CLoader
		return CLoader(None, name, path, type = self.type)

	def readings(self, loader):
		# Compilation Successful, now import in a child process.
		# This helps to avoid dlopen() leaks as unloads are not performed,
		# and allows us to compensate for segfaults.
		pid = os.fork()
		r, w = os.pipe()
		if pid == 0:
			try:
				os.close(r)
				try:
					import faulthandler
					faulthandler.disable()
				except ImportError:
					# no faulthandler
					pass

				with open(w, 'wb', closefd=True) as writer:
					mod = loader.load()
					pickle.dump(writer, mod.payload)
					writer.close()
			except:
				import traceback
				traceback.print_exc()
				os._exit(1)
			finally:
				os._exit(0)
		else:
			os.close(w)
			with open(r, 'rb', closefd=True) as reader:
				rob = pickle.load(reader)
				reader.close()
				status = os.waitpid(pid)
			return rob

	def absence(self, workdir, join = os.path.join):
		i = 0
		hset = set()
		hlist = list()
		for sensor in self.sensors.values():
			for h in sensor.headers:
				if h in hset:
					continue
				# filter already listed
				hset.add(h)
				# maintain order
				hlist.append(h)
		del hset

		missing_headers = set()
		# converge to a single column matrix filtering successes
		# essentially we're bisecting the header list until we
		# find a culprit.

		if len(hlist) < 8:
			# don't bother grouping and bisecting when there are a small number of headers.
			divisions = [(x,) for x in hlist]
		else:
			divisions = [hlist]

		while divisions:
			removals = []
			for n in range(len(divisions)):
				headers = divisions[n]

				# next name
				i += 1
				name = '_probing__headers' + str(i)
				path = join(workdir, name + '.py.' + self.type)

				with open(path, 'w') as src:
					src.write(render_includes(headers))
					src.write(render_module('', "{ return(mod); }"))

				loader = self.construct(name, path)
				try:
					loader.build()
					removals.append(n)
				except Toolset.ToolError as exc:
					# failed
					if len(headers) == 1:
						missing_headers.add(headers[0])
						removals.append(n)
					# otherwise allow subsequent division
					# to isolate the headers from each other
					# to track down the exact failure.

			# filter successes
			for x in reversed(removals):
				del divisions[x]

			nextset = []
			for x in divisions:
				former, latter = x[:len(x)//2], x[len(x)//2:]
				if former:
					nextset.append(former)
				if latter:
					nextset.append(latter)
			divisions = nextset
		return (set(hlist) - missing_headers), missing_headers

	def deploy(self, context, join = os.path.join):
		"""
		deploy()

		Deploy the Probe and return Sensor information.
		"""
		# module name rendering
		i = 0
		prefix = 'probing__' # not a valid identifier (on purpose)
		suffix = '.py.' + self.type

		report = Report()

		# prior to reading our sensors, a full sweep across the headers
		# is performed in order to quickly identify which headers are missing
		# missing headers allow us to quickly skip dependent probes

		# discover any missing headers.
		with context.environment() as d:
			present, absent = self.absence(d)
			report.update([
				('headers', 'present', present),
				('headers', 'absent', absent),
			])

			for sensor_name, sensor in self.sensors.items():
				if set(sensor.headers).intersection(absent):
					# sensor dependency is absent
					continue

				for spath in ():
					if spath is None:
						continue
					i += 1
					name = prefix + sensor_name + str(i)
					path = join(d, name + suffix)

					# compile the probe
					loader = self.construct(name, path)
					loader.build()

					# read the sensors
					report.update(self.readings(loader))
		return report
