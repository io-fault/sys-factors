"""
# Validate a project as functioning by performing its tests against the *active variant*.
"""
import os
import sys
import functools
import collections
import signal

from ...system import corefile
from ...system import library as libsys
from ...routes import library as libroutes

from .. import testing

# The escapes are used directly to avoid dependencies.
exits = {
	'explicit': '\x1b[38;5;237m' 'x' '\x1b[0m',
	'skip': '\x1b[38;5;237m' 's' '\x1b[0m',
	'return': '\x1b[38;5;235m' '.' '\x1b[0m',
	'pass': '\x1b[38;5;235m' '.' '\x1b[0m',
	'divide': '\x1b[38;5;237m' '/' '\x1b[0m',
	'fail': '\x1b[38;5;196m' '!' '\x1b[0m',
	'core': '\x1b[38;5;202m' '!' '\x1b[0m',
	'expire': '\x1b[38;5;202m' '!' '\x1b[0m',
}

def failure_report_file(test):
	"""
	# Return the route to the failure report for the given test.
	"""
	ir, rpath = libroutes.Import.from_attributes(test.identity)
	cd = ir.floor().directory() / '__pycache__'
	rf = cd / 'failures' / test.identity

	return rf

class Harness(testing.Harness):
	"""
	# The collection and execution of a series of tests for the purpose
	# of validating a configured build.

	# This harness executes many tests in parallel. Validation should be quick
	# and generally quiet.
	"""
	concurrently = staticmethod(libsys.concurrently)

	def __init__(self, package, status):
		super().__init__(None, package)
		self.status = status
		self.metrics = collections.Counter() # For division.
		self.tests = []

	def dispatch(self, test):
		# Run self.seal() in a fork
		seal = self.concurrently(lambda: self.seal(test))
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
			try:
				os.kill(pid, signal.SIGKILL)
			except OSError:
				pass

		self.metrics.update(result)

	def seal(self, test):
		self.status.write('\x1b[38;5;234m' '>' '\x1b[0m')
		self.status.flush() # Clear local buffers before fork.

		try:
			signal.signal(signal.SIGALRM, test.timeout)
			signal.alarm(8)

			with test.exits:
				test.seal()
		finally:
			signal.alarm(0)
			signal.signal(signal.SIGALRM, signal.SIG_IGN)

		if isinstance(test.fate, self.libtest.Divide):
			# Descend. Clear in case of subdivide.
			self.metrics.clear()
			del self.tests[:]

			# Divide returned the gathered tests,
			# dispatch all of them and wait for completion.

			divisions = test.fate.content
			self.execute(divisions, ())
			for x in self.tests:
				self.complete(x)

			self.status.write(exits['divide'])
			return dict(self.metrics)
		else:
			fate = test.fate.__class__.__name__.lower()
			self.status.write(exits[fate])
			if test.fate.impact < 0:
				fe = test.fate
				import traceback
				fex = traceback.format_exception(fe.__class__, fe, fe.__traceback__)
				rf = failure_report_file(test)
				rf.store(''.join(fex), 'w')
			return {test.fate.impact: 1}

def main(packages):
	red = lambda x: '\x1b[38;5;196m' + x + '\x1b[0m'
	green = lambda x: '\x1b[38;5;46m' + x + '\x1b[0m'

	sys.dont_write_bytecode = True
	pkgset = []
	for package in packages:
		root = libroutes.Import.from_fullname(package)

		ft = getattr(root.module(), '__factor_type__', None)
		if ft == 'context':
			pkgset.extend(root.subnodes()[0])
		else:
			pkgset.append(root)
	pkgset.sort()

	failures = 0

	for pkg in pkgset:
		if not pkg.exists():
			raise FileNotFoundError(str(pkg))
		cdr = pkg.directory() / '__pycache__' / 'failures'
		if cdr.exists():
			cdr.void()

		sys.stderr.write(str(pkg) + ': ^')
		sys.stderr.flush()

		p = Harness(str(pkg), sys.stderr)
		p.execute(p.root(pkg), [])
		for x in p.tests:
			p.complete(x)

		f = p.metrics.get(-1, 0)
		sys.stderr.write(';\r')
		if not f:
			sys.stderr.write(green(str(pkg)))
		else:
			sys.stderr.write(red(str(pkg)))

		sys.stderr.write('\n')
		sys.stderr.flush()

		failures += f

	if failures:
		sys.stderr.write("\nFailure reports are placed into the project ")
		sys.stderr.write("package's `__pycache__` directory.\n")
		sys.stderr.write("Subsequent runs will overwrite past reports.\n")
		sys.stderr.write("`dev report` for quick pager based access.\n")

	raise SystemExit(min(failures, 201))

if __name__ == '__main__':
	command, *packages = sys.argv
	try:
		os.nice(10)
	except:
		# Ignore nice() failures.
		pass

	with corefile.constraint():
		libsys.control(main, packages)
