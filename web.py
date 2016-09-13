"""
Web context support for &..development.libconstruct.

Provides command constructors for the (libconstruct:context)`web` context.

[Index]
/&<https://www.npmjs.com/package/uglify-js>
	&javascript_uglify
/&<https://www.npmjs.com/package/clean-css>
	&css_cleancss
/&<https://www.npmjs.com/package/less>
	&lessc
/&<https://xmlsoft.org>
	&xinclude
"""
import operator

def xinclude(context, output, inputs,
		mechanism=None,
		language=None,
		format=None,
		verbose=None,
		filepath=str,
		module=None
	):
	"""
	Command constructor for (system:command)`xmllint` based XInclude processing.
	"""
	cmd = ['xmllint', '--nsclean', '--xmlout', '--noblanks', '--xinclude',]
	return cmd + [filepath(inputs[0])]

def lessc(context, output, inputs,
		mechanism=None,
		language=None,
		format=None,
		verbose=None,
		filepath=str,
		source_map_root=None, module=None
	):
	"""
	Command constructor for (system:command)`lessc`.
	"""
	cmd = ['https://www.npmjs.com/package/less', '--source-map']
	cmd.extend((filepath(inputs[0]), filepath(output)))
	return cmd

def css_cleancss(context, output, inputs,
		mechanism=None,
		language=None,
		format=None,
		verbose=None,
		filepath=str,
		source_map_root=None, module=None
	):
	"""
	Command constructor for (system:command)`cleancss`.
	"""
	css = context['css']
	typ = css.get('type', 'library')
	output = filepath(output)

	command = ['cleancss',]
	# cleancss strips the imports entirely, so this is not currently usable.
	#command.extend(('--skip-import-from', 'remote'))
	command.append('--source-map')
	command.extend(('-o', output))

	command.extend((map(filepath, sorted(inputs, key=operator.attrgetter('identifier')))))

	return command

def javascript_uglify(context, output, inputs,
		mechanism=None,
		language=None,
		format=None,
		verbose=None,
		filepath=str,
		source_map_root=None, module=None
	):
	"""
	Command constructor for (system:command)`uglifyjs`.
	"""
	basename = context['factor'].route.identifier

	js = context['javascript']
	typ = js.get('type', 'library')
	output = filepath(output)

	command = ['uglifyjs']

	command.extend(map(filepath, sorted(inputs, key=operator.attrgetter('identifier'))))
	command.extend(('-o', output))
	command.extend(('--source-map', output+'.map'))
	command.extend(('--prefix', 'relative', '-c', '-m'))

	mapurl = basename + '.map'
	command.extend(('--source-map-url', mapurl))

	if typ == 'library':
		command.extend(('--wrap', basename, '--export-all'))

	if js.get('source.parameters') is not None:
		command.append('--define')
		command.append(','.join([
			'='.join((k,v)) for k, v in js.get('source.parameters', ())
		]))

	if source_map_root:
		command.extend(('--source-map-root', source_map_root))

	if verbose:
		command.append('-v')

	return command
