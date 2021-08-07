"""
# Construction Context implementation using vector compositions.
"""
import sys
import functools
import itertools
import typing
import collections

from fault.system import files
from fault.system import execution
from fault.project import system as lsf

from . import core
from . import vc

class Mechanism(object):
	"""
	# A section of a construction context that can formulate adapters for factor processing.
	"""

	def __init__(self, context, semantics):
		self.context = context
		self.semantics = semantics
		self._cache = {}

	def __repr__(self):
		return repr((self.context.route, self.semantics))

	def _cc(self, phase, section, variants, itype, xtype):
		k = (phase, section, variants, itype, xtype)
		if k in self._cache:
			return self._cache[k]

		c = self.context.cc_compose(phase, section, variants, itype, xtype)
		self._cache[k] = c
		return c

	def variants(self, intentions):
		"""
		# Generate the full combinations of sections and variants
		# for the given intentions.
		"""
		return self.context.cc_variants(self.semantics, intentions)

	def unit_name_delta(self, section, variants, itype):
		"""
		# Identify the prefix and suffix for the unit file.
		"""
		return self.context.cc_unit_name_delta(section, variants, itype)

	def prepare(self, section, variants, itype, srctype):
		"""
		# Construct the command constructor for source preparation.
		"""
		return self._cc('Prepare', section, variants, itype, srctype)

	def translate(self, section, variants, itype, srctype):
		"""
		# Construct the command constructor for translating sources.
		"""
		return self._cc('Translate', section, variants, itype, srctype)

	def render(self, section, variants, itype):
		"""
		# Construct the command constructor for rendering the factor's image.
		"""
		return self._cc('Render', section, variants, itype, None)

class Context(object):
	"""
	# Vectors Composition based Mechanism set.
	"""

	@classmethod
	def from_directory(Class, route:files.Path, intention:str='optimal'):
		"""
		# Create instance using a directory. Defaults depending intention to (id)`optimal`.
		"""
		return Class(route, intention)

	def __init__(self, route:files.Path, intention:str):
		self.route = route
		# Requirement intention for metadata contexts.
		self.intention = intention
		self.projects = lsf.Context()

		# Projection mappings. semantics -> project
		self._idefault = None
		self._icache = {}
		self._vcache = {}

		# Initialization Context for loading projections and variants.
		self._vinit = vc.Context(set(), {
			'r-intention': intention
		})

	def _intentions(self, factor):
		# Read the full set of system-architecture pairs from a variants factor.
		return self._cat(self._lv(factor), '[intentions]')

	def _variants(self, factor):
		# Read the full set of system-architecture pairs from a variants factor.
		v = self._lv(factor)
		for system in self._cat(v, '[systems]'):
			for arch in self._cat(v, '[' + system + ']'):
				yield (system, arch)

	def cc_unit_name_delta(self, section, variants, itype):
		# Unit name adjustments.
		exe, adapter, idx = self._read_merged(
			self._vinit,
			section, variants,
			'Render', itype, None
		)

		try:
			unit_prefix = list(self._cat(idx, "[unit-prefix]"))[0]
		except KeyError:
			unit_prefix = ""

		try:
			unit_suffix = list(self._cat(idx, "[unit-suffix]"))[0]
		except KeyError:
			unit_suffix = ""

		return unit_prefix, unit_suffix

	def cc_variants(self, semantics, intentions):
		"""
		# Identify the variant combinations to use for the given &semantics and &intentions.
		"""
		fvp = list()

		# Identify the set of variants.
		for section in self._idefault[semantics]:
			vfactor = (section @ 'variants')
			try:
				vi = set(self._intentions(vfactor))
			except KeyError:
				vi = intentions

			spec = [
				(section, lsf.types.Variants(x[0], x[1], i, ''))
				for i, x in itertools.product(intentions, self._variants(vfactor))
				if i in vi
			]
			fvp.extend(spec)

		return fvp

	def _constants(self, section, variants, itype, xtype, **kw):
		if xtype:
			fmt = xtype.format
			kw.update({'language': fmt.language, 'dialect': fmt.dialect})

		kw['null'] = '/dev/null'
		kw['factor-integration-type'] = str(itype.factor)
		kw['fv-intention'] = variants.intention
		kw['fv-system'] = variants.system
		kw['fv-architecture'] = variants.architecture
		kw['fv-form'] = variants.form

		from fault.system import identity
		kw['host-system'], kw['host-architecture'] = identity.root_execution_context()
		kw['host-python'] = identity.python_execution_context()[1]

		return kw

	def _conclusions(self, section, variants, itype, xtype):
		if xtype and xtype.isolation:
			fmt = xtype.format
			l = {'language-' + fmt.language, 'dialect-' + (fmt.dialect or '')}
		else:
			l = set()

		return l | {
			'it-' + itype.factor.identifier,
			'cc-' + str(section),
			'fv-i' + variants.intention,

			# Generally unused as conclusions,
			# but acceptable in cases where it's known consistent.
			'fv-system-' + variants.system,
			'fv-architecture-' + variants.architecture,
			'fv-intention-' + variants.intention,
			'fv-form-' + (variants.form or 'void'),
		}

	def _compose(self, vctx, section, composition, itype, name, fallback):
		idx = {}
		for c in composition:
			idx.update(self._lv(section @ c).items())

		idx.update(self._lv(section @ itype.factor.identifier).items())

		# Catenate the vectors selected in index using _vinit.
		if name in idx:
			return vctx.chain(self._iq, idx, name)
		else:
			return vctx.chain(self._iq, idx, fallback)

	def _load_descriptor(self, vctx, section, variants, phase, itype, xtype):
		k = (phase, variants, itype, xtype)

		if itype.isolation is not None:
			prefix = (itype.isolation,)
		else:
			prefix = ('type',)

		if k not in self._vcache:
			fall = phase
			if xtype:
				name = phase + '-' + xtype.isolation.split('.', 1)[0]
			else:
				name = phase
				if itype.isolation:
					name += '-' + itype.isolation

			self._vcache[k] = list(self._compose(vctx, section, prefix, itype, name, fall))

		return self._vcache[k]

	def _read_merged(self, vctx, section, variants, phase, itype, xtype):
		exeref, adapter, *composition = self._load_descriptor(
			vctx, section, variants, phase, itype, xtype
		)

		idx = {}
		for x in composition:
			vects = (section @ x)
			idx.update(self._v(vects))

		return exeref, adapter, idx

	def cc_compose(self, phase, section, variants, itype, xtype):
		vctx = vc.Context(
			self._conclusions(section, variants, itype, xtype),
			self._constants(section, variants, itype, xtype)
		)
		exeref, adapter, idx = self._read_merged(vctx, section, variants, phase, itype, xtype)

		# Compose command constructor.
		vr = vctx.compose(idx, adapter)
		def Adapt(query, Format=list(vr), Chain=itertools.chain.from_iterable):
			return Chain(x(query) for x in Format)

		return self._ls(exeref), Adapt

	def load(self):
		"""
		# Load the product indicies.
		"""
		self.projects.connect(self.route)
		self.projects.load()
		self.projects.configure()
		return self

	def configure(self, context=(lsf.types.factor@'vectors')):
		"""
		# Load the default factor semantics.
		"""
		self._idefault = self._map_factor_semantics(context)
		return self

	def _read_cell(self, factor):
		# Load vector.
		product, project, fp = self.projects.split(factor)
		for (name, ft), fd in project.select(fp.container):
			if name == fp:
				syms, srcs = fd
				first, = srcs #* Cell
				return first

	def _lv(self, factor):
		# Load vector.
		typ, src = self._read_cell(factor)
		return vc.parse(src.fs_load().decode('utf-8'))

	def _ls(self, factor):
		# Load system command.
		typ, src = self._read_cell(factor)
		return execution.parse_sx_plan(src.fs_load().decode('utf-8'))

	def _iq(self, name):
		# Vector Reference Query method used during initialization.
		return ()

	def _cat(self, index, name, fallback=None):
		# Catenate the vectors selected in index using _vinit.
		if name in index:
			return self._vinit.chain(self._iq, index, name)
		else:
			return self._vinit.chain(self._iq, index, fallback)

	def _v(self, factor):
		if factor not in self._vcache:
			self._vcache[factor] = self._lv(factor)

		return self._vcache[factor]

	def _map_factor_semantics(self,
			context:lsf.types.FactorPath,
			Projections='context.projections'
		):
		"""
		# Identify the projects providing adapters for the listed semantics.
		"""

		idx = collections.defaultdict(list)
		f = context @ Projections

		# Load ctx.context.projections vectors.
		# project name -> factor semantics
		pvector = self._v(f)
		if pvector is None:
			return None

		# Map semantics identifier to the adapter projects in cc.
		for project in pvector.keys():
			v = self._cat(pvector, project)
			for i in v:
				idx[i].append(context @ project)

		return idx

if __name__ == '__main__':
	r = {
		'input': ['file.o'],
		'output': ['file.exe'],
	}
	ctx = Context.from_directory(files.root@sys.argv[1]).load().configure()

	fit = 'executable'
	itype = lsf.types.Reference(
		'http://if.fault.io/factors', lsf.types.factor@'system.executable',
		'integration-type', None
	)
	stype = lsf.types.Reference(
		'http://if.fault.io/factors', lsf.types.factor@'system.type',
		'type', 'c.1999'
	)
	mech = Mechanism(ctx, 'http://if.fault.io/factors/system')
	print(repr(mech))
	for i in range(1):
		for section, variants in mech.variants(['debug', 'optimal']):
			print('-->', section, variants)
			plan, vcon = mech.render(section, variants, itype)
			outv = list(vcon(lambda x: r.get(x, ())))
			print(outv)
			print(plan)
