"""
# Vector Compositions for constructing system commands.
"""
import collections
import itertools
import functools

from fault.context.string import ilevel

class Functions(object):
	"""
	# The default tool set for vector expansion transformations.
	"""
	def __init__(self, environ, quotation='"', open='[', close=']'):
		self._environ = environ
		self._quotation = quotation
		self._open = open
		self._close = close

	def Select(self, fields):
		"""
		# Compose a vector generator from the expansion fields.
		"""
		for f in fields:
			if f.capitalize() == f:
				continue

			name, *args = f.split('.')
			method = getattr(self, name.replace('-', '_'))
			op = functools.partial(method, *args)
			yield op

	def env(self, name, default):
		"""
		# Override the fields with the identified environment variable.
		"""
		if name in self._environ:
			return self._environ[name]
		else:
			return default

	def quoted(self, string):
		"""
		# Surround the string with quotations and replace any occurrence with two.
		"""
		escaped = string.replace(self._quotation, self._quotation*2)
		return self._quotation + escaped + self._quotation

	def bracketed(self, string):
		"""
		# Surround the string with brackets.
		"""
		return self._open + string + self._close

	def resuffix(self, replacement, string):
		"""
		# Replace the dot-suffix at the end of the string with the designated replacement.
		"""

		i = string.rfind('.')
		if i < 0:
			s = string
		else:
			s = string[:i]

		return '.'.join((s, replacement))

	def suffix(self, extension, string):
		"""
		# Append a dot-suffix to the string.
		"""
		return '.'.join((string, extension))

	def prefix(self, prefix, string):
		"""
		# Force the string to have the given &prefix.
		"""
		return prefix + string if not string.startswith(prefix) else string

class Reference(object):
	"""
	# Placeholder object used to defer parameter resolution.
	"""

	@classmethod
	def from_name(Class, name):
		return Class('', name, '')

	def __init__(self, prefix, name, suffix):
		self.prefix = prefix
		self.suffix = suffix
		self.name = name

	def __repr__(self):
		return f"{self.__class__.__name__}({self.prefix!r}, {self.name!r}, {self.suffix!r})"

	def __iadd__(self, operand):
		self.suffix += operand
		return self

	def __add__(self, operand):
		return self.__class__(self.prefix, self.name, self.suffix + operand)

	def __radd__(self, operand):
		return self.__class__(operand + self.prefix, self.name, self.suffix)

	def rstrip(self, s):
		suffix = self.suffix.rstrip(s)
		if suffix == self.suffix:
			return self
		return self.__class__(self.prefix, self.name, suffix)

	def lstrip(self, s):
		prefix = self.prefix.lstrip(s)
		if prefix == self.prefix:
			return self
		return self.__class__(prefix, self.name, self.suffix)

class Context(object):
	"""
	# Composition data structure holding the conclusions and constants.

	# Primarily providing the &compose interface for producing the
	# final command constructors.
	"""

	def __init__(self, conclusions, constants, tools:Functions=None):
		"""
		# Initialize the context identifying the set of available conditions.
		"""
		self.conclusions = frozenset(conclusions)
		self.constants = dict(constants)
		self.tools = (tools or Functions({}))

	def constraint(self, cset, matches, vparam):
		if not cset:
			# Never; special case.
			return False, 0

		# If the set is empty after discarding the empty conclusion,
		# it's an unconditional expression.
		cset.discard('')
		if not cset:
			# Always. Only successful condition with a zero match count.
			return True, 0

		# Check for reference production.
		if '&' in cset:
			cset.discard('&')
			cset.update(vparam.keys())

		# Check for traps, normal subset, and exceptions.
		if cset == {'!'}:
			# Trap. Match count must be zero for inclusion;
			# Also, zero count must be returned for subsequent traps.
			return (matches == 0), 0
		elif cset.issubset(self.conclusions):
			# Regular Match
			return True, len(cset)
		else:
			# Exception matches.
			for c in cset:
				negative = (c[:1] == '!')
				if negative:
					if c[1:] in self.conclusions:
						return False, 0
				elif c not in self.conclusions:
					return False, 0
			else:
				# All conclusions passed.
				return True, len(cset)

		return False, 0

	@classmethod
	def resolve(Class, vf, vq, vi, index, slices, field=''):
		# As the vector's fields are processed, it is necessary
		# to know if the adjacent quotations need to be
		# concatenated or not.
		latters = [not x[:1].isspace() for x in vf]

		# Terminating condition. This causes the final record
		# to be emitted after adding the implied, empty, quotation.
		latters.append(False)

		for i, v in enumerate(vf):
			q_join_former = (not v[-1:].isspace())
			q_join_latter = latters[i+1]

			# The complexity offered here stems from the need
			# to concatenate adjacent substitutions.
			offset = 0

			for s, comp, name in slices[i]:
				prefix = v[offset:s.start]
				if prefix.isspace():
					continue

				sep_former = prefix[:1].isspace()

				# Substitute name.
				sub = vi[name](index)
				for op in comp:
					sub = op(sub)
				fields = prefix.split()
				if sep_former and field:
					yield field
					field = ''

				if not fields:
					fields.insert(0, field)
				else:
					fields[0] = field + fields[0]

				field = fields[-1].rstrip('[') + sub
				yield from fields[:-1]
				del fields

				# Prepare for next slice.
				offset = s.stop + 1

			if q_join_former and q_join_latter:
				# Carry field. No yields.
				field += vq[i]
			else:
				if not q_join_former and field:
					# Only emit if it's not empty and it's not joining with the quotation.
					yield field
					field = ''

				field += vq[i]

				if not q_join_latter:
					# Includes quotation, unconditionally
					# emit regardless of it being empty.
					yield field
					field = ''

	def production(self, index, vf, vq, vp, vs, query):
		quantity = 0
		vi = {}

		# Collect arguments.
		for pname in vp.keys():
			if pname and pname[:1] == '*':
				repeated = True
				name = pname[1:]
			else:
				repeated = False
				name = pname

			if name is None:
				# No vector references case.
				arg = [None]
			elif name in self.constants:
				arg = self.constants[name]
				if isinstance(arg, (str, bytes)):
					arg = [arg]
			elif name[:1] == '-':
				if name not in index:
					arg = []
				else:
					arg = list(
						itertools.chain.from_iterable(
							x(query) for x in self.compose(index, name)
						)
					)
			else:
				arg = query(pname)
				if arg is None:
					# Productions require non-nil for all substitutions.
					return
				elif not isinstance(arg, collections.abc.Sequence):
					arg = [arg]

			if repeated:
				def repeated_field(index, Sequence=arg, Length=len(arg)):
					return Sequence[index%Length]
				vi[pname] = repeated_field
			else:
				if arg is None:
					return
				quantity = len(arg) if not quantity else min(len(arg), quantity)
				vi[pname] = arg.__getitem__

		slices = []
		for vsp in vs:
			s = list()
			slices.append(s)

			for index, composition, name in vsp:
				fdelta = list(self.tools.Select(composition))
				s.append((index, fdelta, name,))

		# Number of times the expression will be produced.
		vi[None] = (lambda x: '')
		for idx in range(quantity):
			yield from self.resolve(vf, vq, vi, idx, slices)

	def compose(self, index, selection, *argv, negative='!', repeat='.'):
		"""
		# Compose a command constructor with respect to &self.
		"""
		root = index[selection]
		level = 0
		matches = 0 # Number of matches at this &level.
		# Support for '.' conclusions referring to the previous (successful) match set.
		last_cs = {'[never]'}
		last_match = None
		inherited = False

		for il, vexpr in root:
			if il > level:
				# Descent.
				if last_match:
					level = il
					matches = 0
				else:
					# skip until il == level
					continue
			elif il < level:
				# ascended, maintain positive match count to filter exceptions/traps.
				matches = 1
				level = il
				# Reset recall.
				last_cs = {'[never]'}

			# Interpret instruction.
			for lineno, cset, vpair, vparam, vslices in vexpr:
				cset = set(cset) # Avoid updating original.

				if repeat in cset:
					cset.discard(repeat)
					cset.update(last_cs)

				if cset != {negative}:
					# Only carry non-trap sets.
					last_cs = cset

				conditions, count = self.constraint(cset, matches, vparam)
				if conditions:
					# Match.
					last_match = True
					matches += count

					vf, vq = vpair
					yield functools.partial(self.production, index, vf, vq, vparam, vslices)
				else:
					# Mismatch. Ignore.
					last_match = False

	def chain(self, query, index, selection):
		"""
		# Compose and command constructor and evaluate it with respect to &query.
		"""
		return itertools.chain.from_iterable(
			x(query) for x in self.compose(index, selection)
		)

def parameters(string, start='[', stop=']'):
	"""
	# Identify bracketed areas for substitution.
	"""
	i = 0
	k = 0

	while True:
		i = string.find(start, k)
		if i == -1:
			return
		k = string.find(stop, i)
		if k == -1:
			return

		sl = slice(i+1, k)
		yield sl

def quotations(args, quote='"'):
	"""
	# Isolate quotations within a vector expression.
	# Quotations have the highest precedence and must be isolated first.
	"""
	delta = args[:1]
	parts = args.strip().split(quote)

	# Usual condition does not apply at the start.
	# If initial field is empty, it's not an escape.
	fields = parts[:1]
	quotes = parts[1:2]

	for n, q in zip(parts[2::2], parts[3::2]):
		if not n:
			quotes[-1] += quote + q
		else:
			quotes.append(q)
			fields.append(n)

	nparts = len(parts)
	if nparts > 2 and nparts % 2 != 0 and parts[-1]:
		# Loop stopped short on the zip.
		fields.append(parts[-1])

	return delta, fields, quotes

def instruction(lineno, line):
	"""
	# Recognize the vector instruction present on a given line.
	"""
	vector = None
	vparameters = None
	vparamslices = None

	constr, vector = line.split(':', 1)

	# line.split(':')
	conclusions = frozenset(constr.strip().split('/'))

	# Keep fields separated from quotations so isolated
	# processing can be performed without weaving about.
	if not vector or vector.isspace():
		vd = []
		vf = []
		vq = []
	else:
		vd, vf, vq = quotations(vector)

	# Collect parameters used by their name and
	# remember their positioning along with the composition symbols.
	vparameters = collections.defaultdict(list)
	vparamslices = []
	for i, v in enumerate(vf):
		slices = list()
		vparamslices.append(slices)

		for p in parameters(v):
			name, *compose = v[p].split() if v[p] else ('',)
			vparameters[name].append((i, p, compose))
			slices.append((p, compose, name))

		if not vparameters:
			# Force the invariant here.
			vparameters[None] = []

		slices.append((slice(None, len(v), None), (), None))

	if len(vf) > len(vq):
		vq.append('')
	vector = (vf, vq)

	return lineno, conclusions, vector, vparameters, vparamslices

def segments(lines, start=1, newline='\n', indentation='\t', comment='#'):
	"""
	# Isolate the given &lines into segments identified by the unindented line
	# leading an indentation of text. The segments contain the indentations
	# in the order presented by the iterator.
	"""
	i = ((offset, ilevel(line), line) for offset, line in zip(itertools.count(start), lines))

	origin = None
	title = None
	seg = list()

	# Find the first title.
	for lineno, il, line in i:
		if not line or line.isspace() or line.lstrip()[:1] == comment:
			continue

		title, unused = line.split(':', 1) # First title.
		assert il == 0 # first declaration not at zero indentation?
		origin = lineno
		break

	for lineno, il, line in i:
		if not line or line.isspace() or line.lstrip()[:1] == comment:
			continue
		elif il == 0:
			yield origin, title, seg
			seg = list()
			title, unused = line.split(':', 1)
			origin = lineno
			continue

		# Indented line.
		seg.append((il - 1, lineno, line[1:]))
		# Record latest and include with origin and title

	# Emit final.
	yield origin, title, seg

def structure(origin, iterlines):
	"""
	# Structure the formatted vector expressions into a mapping
	# identifying the distinct sequences.
	"""

	return dict([
		(title,
			list(
				(il, list(instruction(y[1], y[2].strip()) for y in x))
				for il, x in itertools.groupby(seq, key=(lambda k: k[0]))
			)
		)
		for lineno, title, seq in segments(iterlines)
	])

def parse(text, origin=None):
	"""
	# Split the &text into lines and return the &structure form.
	"""

	rlines = text.split('\n')
	return structure(origin, rlines)

if __name__ == '__main__':
	import sys
	vectors = sys.argv[1]
	conditions = set()
	params = {'factor-name': ['composition'], '[single]': [None]}

	vslots = collections.defaultdict(list)
	slot = None
	i = 0
	for i, x in enumerate(sys.argv[2:]):
		if x == '--':
			if slot is not None:
				slot = None
				continue
			else:
				break

		if x[:2] == '--':
			if x[-1:] == ':':
				slot = x[2:-1]
			elif '=' in x:
				k, v = x.split('=', 1)
				k = k.lstrip('-')
				del vslots[k][:]
				vslots[k].append(v)
			else:
				conditions.add(x)
				slot = None
		elif slot is not None:
			vslots[slot].append(x)
		else:
			break

	ctx = Context({'fv-idebug', 'it-executable'} | conditions, {'intention': 'debug'})
	with open(vectors) as f:
		d = f.read()

	from pprint import pprint

	params['__arguments__'] = sys.argv[i+2:]
	params['language'] = ['iso-c']
	params['dialect'] = ['1999']
	params['project-name'] = ['system']
	params['architecture'] = ['x86_64']
	params['intention'] = ['debug']
	params.update(vslots)
	itc = itertools.chain.from_iterable
	vidx = parse(d)

	print(list(itc(x(params.get) for x in ctx.compose(vidx, '-cc-compile-1'))))
	print(vidx['-debug'])
	print(list(itc(x(params.get) for x in ctx.compose(vidx, '-cc-compile-1'))))
	print(vidx['-debug'])
