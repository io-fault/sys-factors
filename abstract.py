"""
Abstract Base Classes
"""
import abc

# New Solution WIP
roles = set([
	'bootstrap',
	'debug',
	'profile',
	'coverage',
	'factor',
	'test',
	'documentation',
])

class ToolError(Exception):
	"""
	Exception raised by construction Tools.
	"""
	def __init__(self, stage, target, log):
		self.stage = stage
		self.target = target
		self.log = log

	def __str__(self):
		msg = "could not {0.stage} '{0.target}'\n".format(self)
		msg += "***\n  ".format(self)
		msg += '  '.join(self.log.splitlines(True))
		msg += '\n***'
		return msg

class Tool(object, metaclass = abc.ABCMeta):
	"""
	Tool interface. An object used to construct and process targets in a Project.
	"""

class Execution(object, metaclass = abc.ABCMeta):
	"""
	Tool interface. An object used to construct and process targets in a Project.
	"""

	@property
	@abc.abstractmethod
	def role(self):
		"""
		The configured role of the Toolset.
		"""

class Sensor(object, metaclass = abc.ABCMeta):
	pass

class Probe(object, metaclass = abc.ABCMeta):
	pass

class Toolset(object, metaclass = abc.ABCMeta):
	"""
	Toolset(role = 'factor')

	:param role: The role of the compilation.
	:type role: :py:class:`str`
	"""
	ToolError = ToolError

	@property
	@abc.abstractmethod
	def role(self):
		"""
		The configured role of the Toolset.
		"""

class Compiled(Toolset):
	"""
	Single-stage toolset. Compilation only.
	"""

	@abc.abstractmethod
	def compile(self, target, type, *filenames):
		"""
		compile(target, type, *filenames, ...)

		:param target: The path to the object file.
		:type target: :py:class:`str`
		:param type: The type of source: objc, c, c++
		:type type: :py:class:`str`
		:param filenames: The files to compile into the target file.
		:type filenames: :py:class:`str`
		"""

class Linked(Compiled):
	"""
	Two-stage toolset. Compilation and Linkage.
	"""

	@abc.abstractmethod
	def link(self, target, type, *filenames):
		"""
		link(target, type, *filenames)

		:param target: The path to the object file.
		:type target: :py:class:`str`
		:param type: The type of source: objc, c, c++
		:type type: :py:class:`str`
		:param filenames: The object files to link into the target file.
		:type filenames: :py:class:`str`
		"""
