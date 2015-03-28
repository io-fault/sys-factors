import contextlib
from .abstract import ToolError

class Context(object):
	"""
	Context used to manage and control development build and testing processes.
	"""
	standard_roles = set([
		'test',
		'debug',
		'profile',
		'coverage',
		'factor',
	])

	def __init__(self, role):
		self.role = role
