"""
# Corpus and Context management.

# Materialized Construction Contexts and Corpuses requires some software to control
# the stored concepts. This module provides classes for both as they are often
# related
"""
import typing
from ..filesystem import library as libfs

class Corpus(libfs.Protocol):
	"""
	# Directory containing a Software Corpus.
	"""
	pass

class Product(libfs.Protocol):
	"""
	# Directory containing a set of factors.
	"""

	def factors(self) -> typing.Sequence[str]:
		"""
		# Return the set of root factors that make up the corpus.
		"""
		return set([
			x for x in os.listdir(str(self.route / 'factors'))
			if x[0:1] != '.'
		])

class Context(libfs.Protocol):
	"""
	# Directory representing a Construction Context for performing builds.

	# A Construction Context is the primary focus of &..development.
	# It provides the adaptors necessary for processing Factors for
	# use by the Context's target system for a particular intention.
	"""

	def mechanisms(self, names:typing.Sequence[str]):
		"""
		# Return the routes to the mechanisms with the given &names.
		# Usually, &names contains `'host'`, `'static'`.
		"""

		return [
			self.route / 'mechanisms' / x
			for x in names
		]
