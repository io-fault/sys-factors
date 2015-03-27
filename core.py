"""
Context Manager to inhibit core dumps.
"""
import contextlib

#: Default.
inhibit = contextlib.ExitStack

try:
	import resource

	@contextlib.contextmanager
	def inhibit(
		getrlimit = resource.getrlimit,
		setrlimit = resource.setrlimit,
		type = resource.RLIMIT_CORE
	):
		"""
		Deploy the Probe allowing queries against the C environment to be performed.
		"""
		# XXX: can we just setrlimit() in the child process after fork?
		soft, hard = getrlimit(type)
		try:
			# disable core dumps; probe deployments
			# have an increased likelihood of cores,
			# and we're not really interested in that information.
			setrlimit(type, (0, hard))
			yield d
		finally:
			setrlimit(type, (soft, hard))
except ImportError:
	pass
