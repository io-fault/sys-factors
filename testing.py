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

	def __init__(self, mapping):
		self.redirects = mapping

	@classmethod
	def invalidate_caches(self):
		pass

	def find_spec(self, name, path, target=None):
		spec = self.SupportingFinder.find_spec(name, path, target=target)
		if spec is None:
			return None

		if spec.name in self.redirects:
			spec.cached = str(self.redirects[spec.name])
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
		redirects = {}
		redirects_files = [x for x in paths.split(os.path.pathsep) if x.strip() != '']

		for path in redirects_files:
			with open(path) as f:
				redirects.update(pickle.load(f))

		finder = Class(redirects)
		finder.redirection().__enter__()
		return finder

	@classmethod
	@contextlib.contextmanager
	def root(Class, mapping):
		"""
		# Create and install the &RedirectFinder along with a temporary file
		# noted in (system/environ)`PYTHONIMPORTREDIRECTS` for subprocesses
		# to inherit.
		"""

		import pickle
		suppress = False
		finder = Class(mapping)

		with libroutes.File.temporary() as tmpdir:
			f = tmpdir/'import-redirects.pickle'
			f.store(pickle.dumps({k:str(v) for k,v in mapping.items()}))

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
		self.extensions = collections.defaultdict(list)

	def module_test(self, test):
		"""
		# Method used to implement the root module test that divides
		# into the set of tests defined therein.
		"""
		module = importlib.import_module(test.identity)
		test/module.__name__ == test.identity

		for x in self.extensions.get(test.identity, ()):
			mod = self.preload_extension(test.identity, x)

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

		# Preload all extensions inside the package.
		# Empty when .intent is None
		if not self.imports:
			for x in self.extensions.get(tid, ()):
				mod = self.preload_extension(tid, x)
				self.imports.add(mod)

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

	def preload_extension(self, test_id, route):
		"""
		# Given a Python extension, &route, import the module using
		# the configured &self.context.

		# Used by the harness to import extensions that are being tested in a fashion
		# that allows for coverage and profile data to be collected and for injection
		# dependent tests.
		"""

		env = os.environ

		f = cc.Factor(route, None, None)
		vars, mech = self.context.select(f.domain)
		refs = cc.references(f.dependencies())
		(sp, (vl, key, loc)), = f.link(dict(vars), self.context, mech, refs, ())

		dll = loc['integral'] / 'pf.lnk'

		name = libfactor.extension_access_name(str(route))

		# Get the loader for the extension file.
		loader = importlib.machinery.ExtensionFileLoader(name, str(dll))
		current = sys.modules.pop(name, None)
		mod = loader.load_module()

		# Update containing package dictionary and sys.modules
		sys.modules[name] = mod
		route = libroutes.Import.from_fullname(name)
		parent = importlib.import_module(str(route.container))
		setattr(parent, route.identifier, mod)

		return mod

	@staticmethod
	def _collect_targets(route):
		for pkg in route.tree()[0]:
			if libfactor.composite(pkg):
				yield pkg

	def root(self, route):
		"""
		# Generate the root test from the given route.

		# This creates a pseudo-module that holds the selected test modules
		# to run. Using &Harness.root allows &Harness to operate the initial
		# stage identically to how divisions are handled at later stages.
		"""

		self.imports = set()
		self.project = None

		# pseudo-module for absolute root; the initial divisions are built
		# here and placed in test.root.
		tr = types.ModuleType("test.root")

		module = route.module()
		ft = getattr(module, '__factor_type__', 'python')

		if ft == 'project':
			extpkg = route / 'extensions'
			if extpkg.exists() and self.intent is not None:
				self.extensions[str(route)].extend(self._collect_targets(extpkg))

			tr.__tests__ = [(route.fullname + '.test', self.package_test)]
		elif ft == 'context':
			pkg, mods = route.subnodes()
			if self.intent is not None:
				for x in pkg:
					extpkg = x / 'extensions'
					if extpkg.exists():
						self.extensions[str(x)].extend(self._collect_targets(extpkg))

			tr.__tests__ = [
				(str(x) + '.test', self.package_test)
				for x in pkg
				if ((x/'test').module() is not None)
			]
		else:
			# Presume specific test module
			extpkg = route.floor() / 'extensions'
			if extpkg.exists():
				self.extensions[str(route)].extend(self._collect_targets(extpkg))

			tr.__tests__ = [(str(route), self.module_test)]

		return tr
