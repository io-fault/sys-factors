"""
# Corpus and Context management.

# Materialized Construction Contexts and Corpuses requires some software to control
# the stored concepts. This module provides classes for both as they are often
# related
"""
from ..filesystem import library as libfs

class Corpus(libfs.Protocol):
	"""
	# Directory representing a Software Corpus.

	# The Corpus contains a reference to a &Context and a set of root factors.
	# The parts of a Corpus on the file system may be completely made up from
	# symbolic links allowing the use of shared Contexts and factor instances.
	"""
	pass

class Context(libfs.Protocol):
	"""
	# Directory representing a Construction Context for performing builds.

	# A Construction Context is the primary focus of &..development.
	# It provides the adaptors necessary for processing Factors for
	# use by the Context's target system for a particular intention.
	"""
	pass
