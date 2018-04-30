"""
# Validate a project by performing its tests.
"""
import os
import sys
import functools
import collections
import signal

from fault.system import corefile
from fault.system import library as libsys
from fault.routes import library as libroutes
from fault.test import library as libtest

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
	cd = (ir.floor() / 'test').directory()

	return cd / 'failures', test.identity

class Harness(libtest.Harness):
	"""
	# The collection and execution of a series of tests for the purpose
	# of validating a configured build.

	# This harness executes many tests in parallel. Validation should be quick
	# and generally quiet.
	"""
	concurrently = staticmethod(libsys.concurrently)
	Divide = libtest.Divide
	intent = 'validation'

	def __init__(self, package, status):
		super().__init__(package)
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

		if isinstance(test.fate, self.Divide):
			# Descend. Clear in case of subdivide.
			self.metrics.clear()
			del self.tests[:]

			# Divide returned the gathered tests,
			# dispatch all of them and wait for completion.

			divisions = test.fate.content
			self.process(divisions, ())
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
				rf, fail_id = failure_report_file(test)
				try:
					rf.init('directory')
					sig = rf / '.validation'
					sig.store(b'libtest\n')
				except:
					pass
				fail = rf / fail_id
				fail.store(''.join(fex), 'w')
			return {test.fate.impact: 1}

def main(inv:libsys.Invocation) -> libsys.Exit:
	packages = inv.args
	timeout = int(inv.environ.get('TEST_TIMEOUT', 6))
	log=sys.stderr
	sys.dont_write_bytecode = True

	# Project name coloring after all tests have been ran.
	red = lambda x: '\x1b[38;5;196m' + x + '\x1b[0m'
	green = lambda x: '\x1b[38;5;46m' + x + '\x1b[0m'

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
		cdr = pkg.directory() / 'test' / 'failures'
		if cdr.exists() and (cdr/'.validation').exists():
			cdr.void()

		log.write(str(pkg) + ': ^')
		log.flush()

		h = Harness(str(pkg), log)
		h.process(h.test_root(pkg), [])
		for x in h.tests:
			h.complete(x)

		f = h.metrics.get(-1, 0)
		log.write(';\r')
		if not f:
			log.write(green(str(pkg)))
		else:
			log.write(red(str(pkg)))

		log.write('\n')
		log.flush()

		failures += f

	if failures:
		log.write("\nFailure reports are placed into the project ")
		log.write("package's `test/failures` directory.\n")
		log.write("Subsequent runs will overwrite past reports.\n")

	raise SystemExit(min(failures, 201))

if __name__ == '__main__':
	try:
		os.nice(10)
	except:
		# Ignore nice() failures.
		pass

	with corefile.constraint():
		libsys.control(main, libsys.Invocation.system(environ=('TEST_TIMEOUT',)))
