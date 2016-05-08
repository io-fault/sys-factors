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
import contextlib
import signal
import functools
import types
import importlib
import importlib.machinery
import imp
import collections

from ..routes import library as libroutes
from . import libcore
from . import library as libdev

class Harness(object):
	"""
	The collection and execution of a set of tests.

	Harness provides overridable actions for the execution of Tests.
	Simple test runners subclass &Harness in order to manage the execution
	and status display of an evaluation.

	[ Properties ]

	/role
		The role to use when importing extensions.
		&None if extensions are *not* to be loaded by a role.
	"""
	from . import libtest # class attribute for general access.

	def __init__(self, package, role = None):
		global collections

		self.package = package
		self.role = role
		self.extensions = collections.defaultdict(list)

	gather = staticmethod(libtest.gather)

	def module_test(self, test):
		"""
		Method used to implement the root module test that divides
		into the set of tests defined therein.
		"""
		module = importlib.import_module(test.identity)
		test/module.__name__ == test.identity

		for x in self.extensions.get(test.identity, ()):
			self.preload_extension(x)

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
		ir = libroutes.Import.from_fullname(module.__name__)

		# Preload all extensions inside the package.
		for x in self.extensions.get(str(ir.bottom()), ()):
			self.preload_extension(x)

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
		test.seal()

	def execute(self, container, modules):
		"""
		Execute the tests of the given container.
		"""
		for tid, tcall in getattr(container, '__tests__', ()):
			test = self.libtest.Test(tid, tcall)
			self.dispatch(test)

	def preload_extension(self, import_object:libroutes.Import):
		"""
		Given an extension route, &import_object, import the module using
		the configured &role. 

		Used by the harness to import extensions that are being tested in a fashion
		that allows for coverage and profile data to be collected and for injection
		dependent tests.
		"""
		global importlib, sys

		target_module = import_object.module()
		dll = target_module.output(self.role)
		name = target_module.extension_name()

		# Get the loader for the extension file.
		loader = importlib.machinery.ExtensionFileLoader(name, str(dll))
		mod = sys.modules[name] = loader.load_module()
		print('preloaded', name, mod)

	@staticmethod
	def _collect_targets(route):
		for pkg in route.tree()[0]:
			if isinstance(pkg.module(), libdev.Sources):
				yield pkg

	def root(self, factor):
		"""
		Generate the root test from the given route.
		"""

		# pseudo-module for absolute root; the initial divisions are built
		# here and placed in test.root.
		m = types.ModuleType("test.root")

		f = factor
		base_route = f.route

		if f.type == 'project':
			extpkg = base_route / 'extensions'
			if extpkg.exists():
				self.extensions[str(base_route)].extend(self._collect_targets(extpkg))
				print(self.extensions)

			m.__tests__ = [(f.route.fullname + '.test', self.package_test)]
		elif f.type == 'context':
			pkg, mods = base_route.subnodes()
			for x in pkg:
				extpkg = x / 'extensions'
				if extpkg.exists():
					self.extensions[str(x)].extend(self._collect_targets(extpkg))

			m.__tests__ = [
				(str(x) + '.test', self.package_test)
				for x in pkg
				if ((x/'test').module() is not None)
			]

		return m
