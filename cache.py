"""
# Interface for construction context build cache.
"""
from fault.context import tools
from fault.system import files

class Directory(object):
	"""
	# A filesystem directory managing the build cache of a project set.
	"""
	def __init__(self, route:files.Path):
		self.route = route

	def select(self, project, factor, key) -> files.Path:
		"""
		# Retrieve the route to the work directory for the project's factor.
		"""
		return self.route/project/factor/str(hash(key))

class Persistent(Directory):
	"""
	# Cache directory interface for builds whose cache is expected to be reused.

	# Uses a hashed-key path directory to store and recall entries.
	"""

	@tools.cachedproperty
	def hkp(self):
		"""
		# HKP addressing data.
		"""
		from fault.hkp import library
		return library.Hash('fnv1a_64', depth=1, length=4)

	@tools.cachedproperty
	def index(self):
		from fault.hkp import library
		return library.Dictionary.use(self.route, addressing=self.hkp)

	def select(self, project, factor, key):
		prefix = str(project) + '[' + str(factor) + ']:'
		return self.index.route(prefix.encode('utf-8') + key, filename=str)

class Transient(Directory):
	"""
	# Cache directory interface for builds whose cache is expected to be removed.

	# Uses an in memory index to recall positioning and counters to allocate new entries.
	"""

	@tools.cachedproperty
	def counters(self):
		import collections
		import itertools
		return collections.defaultdict(itertools.count)

	@tools.cachedproperty
	def index(self):
		return dict()

	def select(self, project, factor, key):
		project = str(project)
		factor = str(factor)

		if (project, factor, key) not in self.index:
			cid = next(self.counters[project])
			work = self.route/project/str(cid)
			self.index[(project, factor, key)] = work

		return self.index[(project, factor, key)]
