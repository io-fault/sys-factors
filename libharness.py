"""
Test execution management and status control.

libharness provides management tools for the execution of tests and
the destination of their resulting status. Status being both the fate
of the test and any collected coverage or profile data.

! DEVELOPER:
	Future model: run tests with a specified concurrency level,
	failures are enqueued and processed by the (human) controller.
	Tests are not ran when queue is full; developer chooses to exit
	or pop/debug the failure.
	Concise failure is reported to the text log.
"""
import os
import sys
import types
import importlib
import importlib.machinery
import collections

from ..routes.library import Import
from ..system import libfactor

from . import libconstruct

class Harness(object):
	"""
	The collection and execution of a set of tests.

	Harness provides overridable actions for the execution of Tests.
	Simple test runners subclass &Harness in order to manage the execution
	and status display of an evaluation.

	[ Properties ]

	/contexts
		The construction contexts that will be referenced to identify
		the builds to test.
	"""
	from . import libtest # class attribute for general access.
	Test = libtest.Test
	gather = staticmethod(libtest.gather)

	def __init__(self, package, role=None):
		self.package = package
		self.role = role
		self.extensions = collections.defaultdict(list)

	def module_test(self, test):
		"""
		Method used to implement the root module test that divides
		into the set of tests defined therein.
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
		Method used to implement the test package test that divides
		into the set of &module_test executions.
		"""
		# The package module
		module = importlib.import_module(test.identity)
		test/module.__name__ == test.identity
		ir = Import.from_fullname(module.__name__)
		tid = str(ir.floor())

		# Preload all extensions inside the package.
		# Empty when .role is None
		for x in self.extensions.get(tid, ()):
			mod = self.preload_extension(tid, x)

		if 'context' in dir(module):
			module.context()

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
		Execute the test directly using &test.seal.

		This method is often overwritten in subclasses to control execution.
		"""
		test.seal()

	def execute(self, container, modules):
		"""
		Execute the *tests* of the given container.

		Construct the Test instances for the tests gathered in &container
		and perform them using &dispatch.
		"""
		for tid, tcall in getattr(container, '__tests__', ()):
			test = self.Test(tid, tcall)
			self.dispatch(test)

	def preload_extension(self, test_id, route:Import):
		"""
		Given an extension route, &route, import the module using
		the configured &role. 

		Used by the harness to import extensions that are being tested in a fashion
		that allows for coverage and profile data to be collected and for injection
		dependent tests.
		"""

		env = os.environ

		f = libconstruct.Factor(route, None, None)
		contexts = libconstruct.contexts(env.get('FPI_PURPOSE', 'test'), environment=env.get('FPI_CONTEXT_DIRECTORY', ()))

		mech, fp, *ignored = libconstruct.initialize(contexts, f, collections.defaultdict(set), list(libconstruct.collect(f)))
		variants = fp['variants']

		dll = libconstruct.reduction(route, variants) / 'pf.lnk'
		name = libfactor.extension_access_name(str(route))

		# Get the loader for the extension file.
		loader = importlib.machinery.ExtensionFileLoader(name, str(dll))
		current = sys.modules.pop(name, None)
		mod = loader.load_module()

		# Update containing package dictionary and sys.modules
		sys.modules[name] = mod
		route = Import.from_fullname(name)
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
		Generate the root test from the given route.

		This creates a pseudo-module that holds the selected test modules
		to run. Using &Harness.root allows &Harness to operate the initial
		stage identically to how divisions are handled at later stages.
		"""

		# pseudo-module for absolute root; the initial divisions are built
		# here and placed in test.root.
		tr = types.ModuleType("test.root")

		module = route.module()
		ft = getattr(module, '__factor_type__', 'python')

		if ft == 'project':
			extpkg = route / 'extensions'
			if extpkg.exists() and self.role is not None:
				self.extensions[str(route)].extend(self._collect_targets(extpkg))

			tr.__tests__ = [(route.fullname + '.test', self.package_test)]
		elif ft == 'context':
			pkg, mods = route.subnodes()
			if self.role is not None:
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
			tr.__tests__ = [(str(route), self.module_test)]

		return tr
