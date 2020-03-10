"""
# Stored context implementation version 1.
"""
import os
import functools
import typing
import copy

from fault import routes
from fault.system import files

from . import data
from . import core

class Context(object):
	"""
	# A collection of mechanism sets and parameters used to construct processing instructions.

	# [ Engineering ]
	# This class is actually a Context implementation and should be relocated
	# to make room for a version that interacts with an arbitrary context
	# for use in scripts that perform builds. Direct use is not actually
	# intended as it's used to house the mechanisms.
	"""

	@staticmethod
	def systemfactors(ifactors) -> typing.Iterator[core.SystemFactor]:
		"""
		# Load the system factors in the parameters file identified by &sf_name.
		"""

		for domain, types in ifactors.items():
			for ft, sf in types.items():
				for sf_int in sf:
					if sf_int is not None:
						sf_route = files.Path.from_absolute(sf_int)
					else:
						sf_route = None

					for sf_name in sf[sf_int]:
						yield core.SystemFactor(
							domain = domain,
							type = ft,
							integral = sf_route,
							name = sf_name
						)

	def __init__(self, sequence, symbols):
		self.sequence = sequence or ()
		self.symbols = symbols
		self._languages = {}

		self.index = dict()
		for mid, slots in self.sequence:
			for name, mdata in slots.items():
				data.merge(self.index, mdata)

		syntax = self.index.get('syntax')
		if syntax:
			s = syntax.get('target-file-extensions')
			for pl, exts in s.items():
				for x in exts.split(' '):
					self._languages[x] = pl

	def variants(self, domain, ftype):
		"""
		# Get the variants associated with the domain using the cached view provided by &select.
		"""
		return self.select(domain)[0]

	@functools.lru_cache(8)
	def groups(self, environment) -> typing.Sequence[typing.Sequence[str]]:
		return [['system', 'architecture'], ['name','intention']]

	def language(self, extension):
		"""
		# Syntax domain query selecting the language associated with a file extension.
		"""
		return self._languages.get(extension, 'void')

	@property
	def name(self):
		"""
		# The context name identifying the target architectures.
		"""
		return self.index['context']['name']

	@property
	def intention(self):
		return self.index['context']['intention']

	def default_type(self, domain, key='default-factor-type'):
		"""
		# Select the default factor type of the given domain.
		# Used indirectly by project protocols to select a type
		# for factors that only have identified a domain.
		"""
		if domain in self.index:
			return self.index[domain].get(key, 'library')
		else:
			return None

	@functools.lru_cache(8)
	def select(self, fdomain):
		# Scan the paths (loaded data sets) for the domain.
		variants = {'intention': self.intention}

		if fdomain in self.index:
			mechdata = copy.deepcopy(self.index[fdomain])
			variants.update(mechdata.get('variants', ()))

			if 'inherit' in mechdata:
				# Recursively merge inherit's.
				inner = mechdata['inherit']
				ivariants, imech = self.select(inner)
				data.merge(mechdata, imech.descriptor)
				variants.update(ivariants)
				mechdata['path'] = [fdomain] + mechdata['path']
			else:
				mechdata['path'] = [fdomain]

			mech = core.Mechanism(mechdata)
		else:
			# Unsupported domain.
			mech = core.Mechanism(self.index['void'])
			mech.descriptor['path'] = [fdomain]

		return variants, mech

	@functools.lru_cache(16)
	def field(self, path, prefix):
		"""
		# Retrieve a field from the set of mechanisms.
		"""
		domain, *start = prefix.split('/')
		variants, cwd = self.select(domain)
		cwd = cwd.descriptor

		for key in start:
			cwd = cwd[key]

		if path is not None:
			for key in path.split('/'):
				cwd = cwd[key]

		return cwd

	def __bool__(self):
		"""
		# Whether the Context has any mechanisms.
		"""
		return bool(self.sequence)

	@staticmethod
	def load(route:files.Path):
		for x in route.files():
			yield x.identifier, data.load(x)

	@classmethod
	def from_environment(Class, environ=os.environ, envvar='FPI_MECHANISMS', ctxvar='CONTEXT'):
		mech_refs = environ.get(envvar, '').split(os.pathsep)
		seq = []
		for mech in mech_refs:
			mech = files.Path.from_absolute(mech)
			seq.extend(list(Class.load(mech)))

		ctx = files.Path.from_absolute(environ.get(ctxvar))
		r = Class(seq, dict(Class.load(ctx/'symbols')))
		return r

	@classmethod
	def from_directory(Class, route):
		syms = (route / 'symbols')
		mechs = Class.load(route/'mechanisms')

		return Class(list(mechs), dict(Class.load(syms)))
