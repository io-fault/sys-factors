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

class Harness(object):
	"""
	# The collection and execution of a set of tests.

	# Harness provides overridable actions for the execution of Tests.
	# Simple test runners subclass &Harness in order to manage the execution
	# and status display of an evaluation.

	# [ Properties ]

	# /contexts
		# The construction contexts that will be referenced to identify
		# the builds to test.
	"""
	from fault.test import library as libtest

	Test = libtest.Test
	gather = staticmethod(libtest.gather)

	def __init__(self, context, package, intent=None):
		self.context = context
		self.package = package
		self.intent = intent

	def module_test(self, test):
		"""
		# Method used to implement the root module test that divides
		# into the set of tests defined therein.
		"""
		module = importlib.import_module(test.identity)
		test/module.__name__ == test.identity

		module.__tests__ = self.gather(module)
		if '__test__' in dir(module):
			# allow module to skip the entire set
			module.__test__(test)
		raise self.libtest.Divide(module)

	def package_test(self, test):
		"""
		# Method used to implement the test package test that divides
		# into the set of &module_test executions.
		"""

		# The package module
		module = importlib.import_module(test.identity)
		test/module.__name__ == test.identity
		ir = libroutes.Import.from_fullname(module.__name__)
		tid = str(ir.floor())

		# Initialize the project attribute and imports set.
		self.project = tid

		if 'context' in dir(module):
			module.context(self)

		module.__tests__ = [
			(x.fullname, self.module_test)
			for x in ir.subnodes()[1] # modules only; NO packages.
			if x.identifier.startswith('test_') and (
				not test.constraints or x.identifier in test.constraints
			)
		]

		raise self.libtest.Divide(module)

	def dispatch(self, test):
		"""
		# Execute the test directly using &test.seal.

		# This method is often overwritten in subclasses to control execution.
		"""
		test.seal()

	def execute(self, container, modules):
		"""
		# Execute the *tests* of the given container.

		# Construct the Test instances for the tests gathered in &container
		# and perform them using &dispatch.
		"""

		for tid, tcall in getattr(container, '__tests__', ()):
			test = self.Test(tid, tcall)
			self.test = tid
			self.dispatch(test)

	def root(self, route):
		"""
		# Generate the root test from the given route.

		# This creates a pseudo-module that holds the selected test modules
		# to run. Using &Harness.root allows &Harness to operate the initial
		# stage identically to how divisions are handled at later stages.
		"""

		self.project = None

		# pseudo-module for absolute root; the initial divisions are built
		# here and placed in test.root.
		tr = types.ModuleType("test.root")

		module = route.module()
		ft = getattr(module, '__factor_type__', 'python')

		if ft == 'project':
			tr.__tests__ = [(route.fullname + '.test', self.package_test)]
		elif ft == 'context':
			pkg, mods = route.subnodes()

			tr.__tests__ = [
				(str(x) + '.test', self.package_test)
				for x in pkg
				if ((x/'test').module() is not None)
			]
		else:
			# Presume specific test module
			tr.__tests__ = [(str(route), self.module_test)]

		return tr
