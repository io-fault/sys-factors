"""
Terminal test execution for libtest.
"""
import os
import sys
import contextlib
import signal
import functools
import types
import importlib

from ...routes import library as libroutes
from ...fork import library as libfork

from .. import library as libdev
from .. import libtest
from .. import libcore
from .. import libmeta
from .. import libtrace
from .. import coverage

from .. import libharness

def color(color, text):
	return text

def color_identity(identity):
	parts = identity.split('.')
	parts[0] = color('0x1c1c1c', parts[0])
	parts[:-1] = [color('gray', x) for x in parts[:-1]]
	return color('red', '.').join(parts)

open_fate_message = color('0x1c1c1c', '|')
close_fate_message = color('0x1c1c1c', '|')
top_fate_messages = color('0x1c1c1c', '+' + ('-' * 10) + '+')
working_fate_messages = color('0x1c1c1c', '+' + ('/\\' * 5) + '+')
bottom_fate_messages = color('0x1c1c1c', '+' + ('-' * 10) + '+')

class Harness(libharness.Harness):
	"""
	The collection and execution of a series of tests.
	"""
	concurrently = staticmethod(libfork.concurrently)

	def __init__(self, package, status):
		self.package = package
		self.status = status
		self.selectors = []
		self.cextensions = []
		self.fimports = {}

	def _status_test_sealing(self, test):
		self.status.write('{working} {tid} ...'.format(
			working = working_fate_messages,
			tid = color_identity(test.identity),
		))
		self.status.flush() # need to see the test being ran right now

	def _report_core(self, test):
		self.status.write('\r{start} {fate!s} {stop} {tid}                \n'.format(
			fate = color(test.fate.color, 'core'.ljust(8)), tid = color_identity(test.identity),
			start = open_fate_message,
			stop = close_fate_message
		))

	def _handle_core(self, corefile):
		if corefile is None:
			return

		if os.path.exists(corefile):
			self.status.write("CORE: Identified, {0!r}, loading debugger.\n".format(corefile))
			libcore.debug(corefile)
			self.status.write("CORE: Removed file.\n".format(corefile))
			os.remove(corefile)
		else:
			self.status.write("CORE: File does not exist: " + repr(corefile) + '\n')

	def execute(self, container, modules, division = None):
		if division is None:
			self.status.write(top_fate_messages + '\n')

		super().execute(container, modules, division=division)

		if division is None:
			self.status.write(bottom_fate_messages + '\n')

def main(package, modules):
	# Set test role. Per project?
	# libconstruct.role = 'test'
	p = Harness(package, sys.stderr)
	p.execute(p.root(libdev.Factor.from_fullname(package)), modules)

	raise SystemExit(0)

if __name__ == '__main__':
	package, *modules = sys.argv[1:]
	with libcore.dumping():
		libfork.control(functools.partial(main, package, modules))
