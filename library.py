import contextlib
from .abstract import ToolError

class Project(object):
	"""
	A unit containing targets to be constructed or processed.
	Provides access to project information.
	"""
	from ..routes import library as routeslib

	def __init__(self, route):
		self.route = route
		self.directory = self.route.file().container

	@classmethod
	def from_module(Class, module):
		r = routeslib.Import.from_module(module)
		return Class(r.bottom())

class Context(object):
	"""
	Context used to manage the data needed by Execution instances in order to construct a
	target.
	"""
	python_cache = '__pycache__'
	developer_cache = '__dev__'

	def __init__(self, role):
		self.role = role

