"""
# Test execution management and status control.

# harness provides management tools for the execution of tests and
# the destination of their resulting status. Status being both the fate
# of the test and any collected metrics about the runtime.

# [ Engineering ]

# Future model should run tests with a specified concurrency level,
# failures are enqueued and processed by the (human) controller.
# Tests are not ran when queue is full; developer chooses to exit
# or pop/debug the failure.
# Concise failure is reported to the text log.
"""
import os
import sys
import types
import importlib
import importlib.machinery
import collections
import contextlib

from fault.routes import library as libroutes
from fault.system import libfactor, library as libsys

from . import cc

class RedirectFinder(object):
	"""
	# Redirect the import of a Python module to select an alternative bytecode file.
	"""
	SupportingFinder = importlib.machinery.PathFinder

	class Loader(importlib.machinery.SourceFileLoader):
		_bytecode_path = None
		_module_name = None

		def get_data(self, bytecode_path):
			return super().get_data(self._bytecode_path)

	def __init__(self, bytecodes, extensions):
		self.bytecode_redirects = bytecodes
		self.extension_redirects = extensions

	@classmethod
	def invalidate_caches(self):
		pass

	def find_spec(self, name, path, target=None):
		spec = self.SupportingFinder.find_spec(name, path, target=target)
		if spec is None:
			return None

		if spec.name in self.extension_redirects:
			spec.origin = spec.loader.path = str(self.extension_redirects[spec.name])
		elif spec.name in self.bytecode_redirects:
			spec.cached = str(self.bytecode_redirects[spec.name])
			spec.loader.__class__ = self.Loader
			spec.loader._bytecode_path = spec.cached
			spec.loader._module_name = spec.name

		return spec

	@contextlib.contextmanager
	def redirection(self):
		"""
		# Context manager installing import redirects for Python bytecode.
		# Allows the use of out-of-place constructed bytecode files with the executing tests.
		"""

		suppress = False
		ridx = sys.meta_path.index(self.SupportingFinder)
		sys.meta_path.insert(ridx, self)
		try:
			yield None
		except libsys.Fork:
			suppress = True
			raise
		finally:
			if not suppress:
				del sys.meta_path[sys.meta_path.index(self)]

	envvar = 'PYTHONIMPORTREDIRECTS'

	@classmethod
	def inherit(Class):
		"""
		# Permanently inherit import redirects from the environment.
		"""

		import pickle

		paths = os.environ[Class.envvar]
		r_bc = {}
		r_ext = {}
		redirects_files = [x for x in paths.split(os.path.pathsep) if x.strip() != '']

		import fault.routes.library as lr
		for path in redirects_files:
			f=lr.File.from_absolute(path)
			with open(path, 'rb') as f:
				bytecodes, extensions = pickle.load(f)
				r_bc.update(bytecodes)
				r_ext.update(extensions)

		finder = Class(r_bc, r_ext)
		return finder

	@classmethod
	@contextlib.contextmanager
	def root(Class, *mappings):
		"""
		# Create and install the &RedirectFinder along with a temporary file
		# noted in (system/environ)`PYTHONIMPORTREDIRECTS` for subprocesses
		# to inherit.
		"""

		import pickle
		suppress = False
		finder = Class(*mappings)

		tmp = libroutes.File.from_absolute(libroutes.tempfile.mkdtemp())
		f = tmp/'import-redirects.pickle'
		ser = []
		for x in mappings:
			ser.append({k:str(v) for k,v in x.items()})

		f.store(pickle.dumps(tuple(ser)))

		try:
			if Class.envvar in os.environ:
				r = os.environ[Class.envvar]
			else:
				r = None
				os.environ[Class.envvar] = ''
			os.environ[Class.envvar] += (os.path.pathsep + str(f))
			with finder.redirection():
				yield finder
		except libsys.Fork:
			suppress = True
			raise
		finally:
			if not suppress:
				tmp.void()
				if r is None:
					del os.environ[Class.envvar]
				else:
					os.environ[Class.envvar] = r
