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

from ..routes import library as libroutes
from . import libcore

class Harness(object):
	"""
	The collection and execution of a set of tests.

	Harness provides overridable actions for the execution of Tests.
	Simple test runners subclass &Harness in order to manage the execution
	and status display of an evaluation.
	"""
	from . import libtest
	exit_on_failure = False

	def __init__(self, package):
		self.package = package
		self.selectors = []
		self.cextensions = []
		self.fimports = {}
		self.tracing = libtrace.Tracing

	def module_test(self, test):
		"""
		Method used to implement the root module test that divides
		into the set of tests defined therein.
		"""
		module = importlib.import_module(test.identity)
		test/module.__name__ == test.identity

		module.__tests__ = self.libtest.gather(module)
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

		if 'context' in dir(module):
			module.context()

		ir = libroutes.Import.from_fullname(module.__name__)
		module.__tests__ = [
			(x.fullname, self.module_test)
			for x in ir.subnodes()[1] # modules only; NO packages.
			if x.identity.startswith('test_') and (
				not test.constraints or x.identity in test.constraints
			)
		]

		raise self.libtest.Divide(module)

	def execute(self, container, modules):
		"""
		Execute the tests of the given container.
		"""
		for tid, tcall in getattr(container, '__tests__', ()):
			test = self.libtest.Test(tid, tcall)
			self.dispatch(test)

	def root(self, factor):
		"""
		Generate the root test from the given route.
		"""

		m = types.ModuleType("test.root")
		f = factor

		if f.type == 'project':
			m.__tests__ = [(f.route.fullname + '.test', self.package_test)]
		elif f.type == 'context':
			pkg, mods = f.route.subnodes()
			m.__tests__ = [
				(str(x) + '.test', self.package_test)
				for x in pkg
				if ((x/'test').module() is not None)
			]

		return m
