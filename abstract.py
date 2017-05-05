"""
# Abstract Base Classes
"""
import abc
import typing

class Factor(metaclass=abc.ABCMeta):
	"""
	# Interface requirements for describing a processable Factor.
	"""

	@property
	@abc.abstractmethod
	def reflection(self) -> bool:
		"""
		# Whether the Factor is a pure reflection; a factor whose
		# sources are the integral.
		"""
		pass

	@property
	@abc.abstractmethod
	def domain(self):
		"""
		# The factor type used to identify the mechanism that is to be
		# used to process the factor's sources.
		"""
		pass

	@property
	@abc.abstractmethod
	def type(self):
		"""
		# The use of the integral; usually one of four possibilities:

		# /executable
			# A collection of resources that are invoked to perform some task.
		# /library
			# A collection of resources that will be used as a dependency.
		# /extension
			# A collection of resources that will be used by an executable
			# during its runtime.
		# /fragment
			# A collection of resources that augments other factors during the
			# build process.
		"""
		pass

	@abc.abstractmethod
	def sources(self) -> typing.Iterable[str]:
		"""
		# A method providing an iterable producing the source
		# files used as input to the Factor Processing Instructions.

		# Sources should be cached locally prior to construction.
		"""

	@abc.abstractmethod
	def integral(self) -> str:
		"""
		# The filesystem location of the collection of resources
		# that were produced by the Integration procedure.
		"""
		pass

class Mechanism(metaclass=abc.ABCMeta):
	"""
	# Opaque class for describing how a factor can be processed.
	"""

	def transform(self, factor):
		"""
		# Produce the Processing Instructions necessary for transforming
		# the factor's sources into a format that can be processed by &integrate.
		"""

	def integrate(self, factor):
		"""
		# Produce the Processing Instructions necessary for combining
		# the transformed sources into the format that the Mechanism
		# was designed to produce.
		"""

class Context(metaclass=abc.ABCMeta):
	"""
	# Interface for construction contexts.
	"""

	@abc.abstractmethod
	def select(self, factor_type:typing.Hashable) -> Mechanism:
		"""
		# Primary method of &Context implementations returning
		# a &Mechanism for processing the given &Factor.
		"""
		pass
