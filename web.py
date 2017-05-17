"""
# Web context support for &.library.

# Provides command constructors for the (dev:context)`web` context.

# [Index]
# /&<https://www.npmjs.com/package/uglify-js>
	# &javascript_uglify
# /&<https://www.npmjs.com/package/clean-css>
	# &css_cleancss
# /&<https://www.npmjs.com/package/less>
	# &lessc
# /&<https://xmlsoft.org>
	# &xinclude
"""
import operator
import itertools

def xinclude(
		build, adapter, o_type, output, i_type, inputs,
		fragments, libraries,
		verbose=None,
		filepath=str,
		module=None
	):
	"""
	# Command constructor for (system/command)`xmllint` based XInclude processing.
	"""

	input, = inputs
	cmd = ['xmllint', '--nsclean', '--xmlout', '--noblanks', '--xinclude',]
	cmd.append(filepath(input))

	return cmd

def xml(
		build, adapter,
		o_type, output, i_type, inputs,
		*factors,
		verbose=None,
		filepath=str,
		module=None
	):
	"""
	# &..xml based processor for XML targets.
	"""
	vars = list(build.variants.items())
	vars.sort()

	cmd = ['xml', adapter['name'], filepath(output), filepath(inputs[0])]
	cmd.extend(itertools.chain.from_iterable(vars))

	return cmd

def xml_link(
		build, adapter,
		otype, output,
		itype, inputs,
		*factors,
		verbose=None,
		filepath=str,
		module=None
	):
	"""
	# Interface to &..xml.bin.ld.
	"""
	assert adapter['name'] == 'integrate'
	assert otype == 'library'

	ciri = None
	if build.factor.module:
		ciri = build.factor.module.__dict__.get('canonical')

	if ciri is None:
		ciri = '<>'

	psd = build.locations['output'] # processed source directory
	rpaths = ['/'.join(x.relative) for x in inputs]

	# xml.bin.ld works relative to a root directory.
	# relative paths imply their path setting.
	return [None, ciri, str(output), str(psd)] + rpaths

def lessc(
		build, adapter, o_type, output, i_type, inputs,
		verbose=None, filepath=str,
		source_map_root=None, module=None
	):
	"""
	# Command constructor for (system/command)`lessc`.
	"""

	cmd = ['https://www.npmjs.com/package/less', '--source-map']
	cmd.extend((filepath(inputs[0]), filepath(output)))
	return cmd

def css_cleancss(
		build, adapter, o_type, output, i_type, inputs,
		fragments, libraries,
		verbose=None,
		filepath=str,
		source_map_root=None, module=None
	):
	"""
	# Command constructor for (system/command)`cleancss`.
	"""

	assert build.factor.type == 'library'
	output = filepath(output)

	command = ['cleancss',]

	# cleancss strips the imports entirely, so this is not currently usable.
	#command.extend(('--skip-import-from', 'remote'))
	command.append('--source-map')
	command.extend(('-o', output))

	command.extend((map(filepath, sorted(inputs, key=operator.attrgetter('identifier')))))

	return command

def javascript_uglify(
		build, adapter, o_type, output, i_type, inputs,
		fragments, libraries,
		verbose=None,
		filepath=str,
		source_map_root=None, module=None
	):
	"""
	# Command constructor for (system/command)`uglifyjs`.
	"""
	factor = build.factor
	basename = factor.route.identifier

	typ = factor.domain
	output = filepath(output)

	command = ['uglifyjs']
	extend = command.extend
	append = command.append

	extend(map(filepath, sorted(inputs, key=operator.attrgetter('identifier'))))
	extend(('-o', output))
	extend(('--source-map', output+'.map'))
	extend(('--prefix', 'relative', '-c', '-m'))

	mapurl = basename + '.map'
	extend(('--source-map-url', mapurl))

	if typ == 'library':
		extend(('--wrap', basename, '--export-all'))

	if build.parameters:
		append('--define')
		append(','.join([
			'='.join((k,v)) for k, v in build.parameters
		]))

	if source_map_root:
		extend(('--source-map-root', source_map_root))

	if verbose:
		command.append('-v')

	return command
