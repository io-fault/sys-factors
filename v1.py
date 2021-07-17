"""
# Stored context implementation version 1.
"""
import os
import functools
import typing
import copy
import importlib

from fault.context import tools
from fault.system import files
from fault.system import python
from fault.project import system as lsf

from . import data
from . import core

def context_interface(path):
	"""
	# Get the command constructor identified by &path.
	"""

	# Avoid at least one check as it is known there is at least
	# one attribute in the path.
	leading, final = path.rsplit('.', 1)
	mod, apath = python.Import.from_attributes(leading)
	obj = importlib.import_module(str(mod))

	for x in apath:
		obj = getattr(obj, x)

	return getattr(obj, final)

class Mechanism(object):
	"""
	# The mechanics used to produce an Integral from a set of Sources associated
	# with a Factor. &Mechanism instances are usually created by &Context instances
	# using &Context.select.

	# [ Properties ]

	# /descriptor/
		# The data structure referring to the interface used
		# to construct processing instructions for the selected mechanism.
	# /cache/
		# Mapping of resolved adapters. Used internally for handling
		# adapter inheritance.
	"""

	def __init__(self, intentions, descriptor):
		self.intentions = intentions
		self.descriptor = descriptor
		self.cache = {}

	def variants(self, intentions, /, _vc=tools.cachedcalls(8)(lsf.types.Variants)):
		v = self.descriptor['variants']
		for i in intentions:
			yield None, _vc(v['system'], v['architecture'], i, '')

	def integrates(self):
		ints = self.descriptor.get('integrations')
		if ints:
			return True
		else:
			return False

	@staticmethod
	def combine(aset, key):
		# Process inheritance.
		lmech = aset[key]
		layers = [lmech]
		while 'inherit' in (lmech or ()):
			basemech = lmech['inherit']
			layers.append(aset[basemech]) # mechanism inheritance
			lmech = aset[basemech]
		layers.reverse()

		cmech = {}
		for x in layers:
			if x is not None:
				data.merge(cmech, x)
		cmech.pop('inherit', None)
		return cmech

	def adaption(self, build, ftype, source, phase='transformations'):
		"""
		# Select the adapter of the mechanism for the given source.

		# Adapters with inheritance will be cached by the mechanism.
		"""
		aset = self.descriptor[phase]

		# Mechanisms support explicit inheritance.
		if (phase, ftype) in self.cache:
			return self.cache[(phase, ftype)]

		key = None
		if str(ftype) in aset:
			key = str(ftype)

		# cache merged mechanism
		cmech = self.cache[(phase, ftype)] = self.combine(aset, key)
		return cmech

	def translate(self, build, filtered):
		"""
		# Transform the sources using the mechanisms defined in &context.
		"""

		f = build.factor
		ftype = f.type
		loc = build.locations

		mechanism = build.mechanism.descriptor
		commands = []
		for srcfmt, src in f.sources():
			fmt = srcfmt.format
			obj = files.Path(loc['output'], src.points)

			if filtered((obj,), (src,)):
				continue

			logfile = files.Path(loc['log'], src.points)

			adapter = self.adaption(build, fmt.language, src)
			if 'interface' not in adapter:
				continue

			# Translation command.
			xf = context_interface(adapter['interface'])
			seq = list(xf(build, adapter, obj, fmt, (src,)))

			yield self.formulate(obj, (src,), logfile, adapter, seq)

	def formulate(self, route, sources, logfile, adapter, sequence):
		"""
		# Convert a generated instruction into a form accepted by &Construction.
		"""

		method = adapter.get('method')
		command = adapter.get('command')
		redirect = adapter.get('redirect')

		# Adapter interface leaves this as None or a relative name.
		# Update to absolute path entered into adapter.
		sequence[0] = command

		if redirect == 'io':
			return ('execute-stdio', sequence, logfile, (sources, route))
		elif redirect:
			return ('execute-redirection', sequence, logfile, (sources, route))
		else:
			# No redirect.
			return ('execute', sequence, logfile, (sources, route))

	def render(self, build, filtered):
		"""
		# Construct the operations for reducing the transformations.
		"""

		f = build.factor
		loc = build.locations
		mech = self.descriptor

		if 'integrations' not in mech:# or f.reflective: XXX
			# warn/note?
			return

		# Discover the known sources in order to identify which objects should be selected.
		objdir = loc['output']
		sources = set([
			x.points for srcfmt, x in f.sources()
			if x.extension not in mech.get('ignore-extensions', ())
		])
		objects = [objdir.__class__(objdir, x) for x in sources]

		# XXX: does not account for partials
		if filtered((loc['factor-image'],), objects):
			return

		adapter = self.adaption(build, f.type, objects, phase='integrations')

		# Mechanisms with a configured root means that the
		# transformed objects will be referenced by the root file.
		root = adapter.get('root')
		if root is not None:
			objects = [objdir / root]

		xf = context_interface(adapter['interface'])
		seq = xf(build, adapter, loc['factor-image'], objects)
		logfile = loc['log'] / 'Integration'

		yield self.formulate(loc['factor-image'], objects, logfile, adapter, seq)

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

		for types in ifactors.items():
			for ft, sf in types.items():
				for sf_int in sf:
					if sf_int is not None:
						sf_route = files.Path.from_absolute(sf_int)
					else:
						sf_route = None

					for sf_name in sf[sf_int]:
						yield core.SystemFactor(
							type = ft,
							image = sf_route,
							name = sf_name
						)

	def __init__(self, sequence, symbols):
		self.sequence = sequence or ()
		self.symbols = symbols
		self._languages = {}
		self._cache = {}

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

	def variants(self, ftype):
		"""
		# Get the variants associated with the domain using the cached view provided by &select.
		"""
		return self.select(ftype)[0]

	@property
	def name(self):
		"""
		# The context name identifying the target architectures.
		"""
		return self.index['context']['name']

	@property
	def required(self):
		"""
		# The intention used to resolve dependencies.
		"""
		return self.index['context'].get('requirement')

	@property
	def overrides(self):
		"""
		# Variant overrides for &.core.Target.image.
		"""
		return self.index['context'].get('override-variants')

	@property
	def intention(self):
		"""
		# The intention of target images.
		"""
		return self.index['context']['intention']

	@property
	def path(self):
		return self.index['context']['path']

	@functools.lru_cache(8)
	def identify(self, ftype) -> str:
		"""
		# Identify the domain for the given factor type.
		"""
		for domain in self.path:
			if domain not in self._cache:
				record = self._cache[domain] = self._build(domain, self.intention)
			else:
				record = self._cache[domain]

			if record is None:
				continue

			if str(ftype) in record[1].descriptor['integrations']:
				return domain

		# No domain holds that factor type.
		return None

	def _build(self, domain, intention):
		# Scan the paths (loaded data sets) for the domain.
		variants = {'intention': intention}

		if domain not in self.index:
			return None

		mechdata = copy.deepcopy(self.index[domain])
		variants.update(mechdata.get('variants', ()))

		if 'inherit' in mechdata:
			# Recursively merge inherit's.
			inner = mechdata['inherit']
			ivariants, imech = self.select(inner)
			data.merge(mechdata, imech.descriptor)
			variants.update(ivariants)
			mechdata['path'] = [domain] + mechdata['path']
		else:
			mechdata['path'] = [domain]

		mech = Mechanism([self.intention], mechdata)
		return variants, mech

	def select(self, ftype):
		domain = self.identify(ftype)
		if domain is None:
			return None
		entry = self._cache[domain]
		variants, mech = entry
		return (dict(variants), mech)

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

	@staticmethod
	def _load_mech(route:files.Path):
		for x in route.fs_iterfiles(type='data'):
			yield x.identifier, data.load(x)

	@classmethod
	def from_directory(Class, route):
		syms = (route / 'symbols')
		mechs = Class._load_mech(route/'mechanisms')

		return Class(list(mechs), dict(Class._load_mech(syms)))
