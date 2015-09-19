"""
Project development interface for software engineers.
"""
import contextlib
from .core import ToolError
from .core import roles

class Project(object):
	"""
	A unit containing targets to be constructed or processed.
	Provides access to project information and common project operations.

	The project's outermost package module must identify itself as the bottom
	in order for &Project to function properly.
	"""

	def __init__(self, route):
		self.route = route
		self.directory = self.route.file().container

	from ..routes import library as routeslib

	@classmethod
	def from_module(Class, module, Import = routeslib.Import):
		"Return the &Project instance for the given module path."
		r = Import.from_module(module)
		return Class(r.bottom())

	del routeslib

	@property
	def information(self):
		"The package's project module. Provides branch information and identity."
		pim = self.route / 'project'
		return pim.module()

	@property
	def qid(self):
		"The package's qualified identity. Uniquely identifies the project and variant."
		pi = self.information
		return '#'.join((pi.identity, pi.fork))

	def initialize(self, role='factor'):
		"""
		Initialize the project so that it may be usable and ready for installation.

		This method will perform the necessary compilation tasks for a production installation.
		"""
		pass

	def validate(self):
		"""
		Validate the functionality of the project.

		This method initializes the project for a "test" role and performs all available tests.
		It does *not* perform coverage analysis.
		"""
		self.initialize('test')
		self.test('test')
		self.test()

	def test(self, role='factor'):
		"""
		Perform the project's tests for the given role.
		"""

	def release(self):
		"""
		Modify the package to become a release.
		"""

class Type():
	pass

class Factor(tuple):
	"""
	A build target of the project and the plan to prepare it.
	"""
	__slots__ = ()

	@property
	def type(self):
		"The type of factor; operation system executable, library, Python module, etc."
		return self[0]

	@property
	def path(self):
		"The Python module path of the target."
		return self[1]

	@property
	def plan(self):
		"The series of operations necessary for preparing the factor."
		return self[2]

	@property
	def files(self):
		"The files produced that represent the prepared factor."
		return self[3]

	def __new___(Class, type, path, plan, files):
		return super().__new__(Class, (type, path, plan, files))
