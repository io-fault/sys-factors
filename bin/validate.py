"""
Validate a project as functioning by performing its tests against the configured role.
"""
import os
import sys
import functools
import collections

from ...system import library as libsys
from ...system import libcore
from .. import libharness
from .. import library as libdev

# The escapes are used directly to avoid dependencies.
exits = {
	'explicit': '\x1b[38;5;237m' 'x' '\x1b[0m',
	'skip': '\x1b[38;5;237m' 's' '\x1b[0m',
	'return': '\x1b[38;5;235m' '.' '\x1b[0m',
	'pass': '\x1b[38;5;235m' '.' '\x1b[0m',
	'divide': '\x1b[38;5;237m' '/' '\x1b[0m',
	'fail': '\x1b[38;5;196m' '!' '\x1b[0m',
	'core': '\x1b[38;5;202m' '!' '\x1b[0m',
}

class Harness(libharness.Harness):
	"""
	The collection and execution of a series of tests for the purpose
	of validating a configured build.

	This harness executes many tests in parallel. Validation should be quick
	and generally quiet.
	"""
	concurrently = staticmethod(libsys.concurrently)

	def __init__(self, package, status, role='optimal'):
		super().__init__(package, role=role)
		self.status = status
		self.metrics = collections.Counter() # For division.
		self.tests = []

	def dispatch(self, test):
		# Run self.seal() in a fork
		seal = self.concurrently(functools.partial(self.seal, test))
		self.tests.append(seal)

	def complete(self, test):
		l = []
		result = test(status_ref = l.append)

		if result is None:
			result = {-1: 1}

		pid, status = l[0]

		if os.WCOREDUMP(status):
			result = {-1: 1}
			fate = 'core'
		elif not os.WIFEXITED(status):
			# redrum
			import signal
			try:
				os.kill(pid, signal.SIGKILL)
			except OSError:
				pass

		self.metrics.update(result)

	def seal(self, test):
		self.status.write('\x1b[38;5;234m' '>' '\x1b[0m')
		self.status.flush() # Clear local buffers before fork.
		test.seal()

		if isinstance(test.fate, self.libtest.Divide):
			# Descend. Clear in case of subdivide.
			self.metrics.clear()
			del self.tests[:]

			# Divide returned the gathered tests,
			# dispatch all of them and wait for completion.
			self.execute(test.fate.content, ())
			for x in self.tests:
				self.complete(x)

			self.status.write(exits['divide'])
			return dict(self.metrics)
		else:
			fate = test.fate.__class__.__name__.lower()
			self.status.write(exits[fate])
			return {test.fate.impact: 1}

def main(package, modules, role='optimal'):
	sys.dont_write_bytecode = True
	sys.stderr.write('^')
	sys.stderr.flush()

	p = Harness(package, sys.stderr, role=role)
	p.execute(p.root(libdev.Factor.from_fullname(package)), modules)
	for x in p.tests:
		p.complete(x)

	sys.stderr.write(';\n')
	sys.stderr.flush()

	failures = p.metrics.get(-1, 0)
	raise SystemExit(min(failures, 201))

if __name__ == '__main__':
	command, package, *modules = sys.argv
	with libcore.constraint():
		libsys.control(main, package, modules)
