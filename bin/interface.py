"""
# Command interface to a Materialized Construction Context.
"""
import sys
import os
from fault.system import library as libsys
from fault.routes import library as libroutes
from .. import fs

flags = {
	'q': 'quiet',
	'R': 'rebuild',
}

assignments = {
	'O': ('intention', 'optimal'),
	'g': ('intention', 'debug'),
	't': ('intention', 'test'),
	'M': ('intention', 'metrics'),
	'H': ('name', 'host'),
	'W': ('name', 'web'),
	'I': ('name', 'inspect'),
}

def main(inv:libsys.Invocation):
	typ, path, *args = inv.args
	typ = typ.capitalize()
	Imp = getattr(fs, typ) # get class for specified directory protocol
	i = Imp(libroutes.File.from_path(path))

	parameters = {
		'python': sys.executable,
		'prefix': __package__,
		'intention': 'optimal',
		'rebuild': False,
		'quiet': False,
	}

	os.environ['PYTHON'] = sys.executable
	entry_point = inv.parameters['system']['name']

	index = 0
	for opt in args:
		if opt[0:1] != '-':
			# Options don't take parameters.
			# No need to push or pop anything.
			break
		elif opt == '--help':
			sys.stderr.write(entry_point + " [-HWI] [-OgtM]\n")
			return inv.exit(64)

		index += 1
		for char in opt[1:]:
			if char in flags:
				parameters[flags[char]] = True
			elif char in assignments:
				field, setting = assignments[char]
				parameters[field] = setting
			else:
				sys.stderr.write("unknown option %r\n" %(char,))
				return inv.exit(64) # EX_USAGE

	x = i.mechanisms(('intent.xml', 'static.xml'))
	os.environ['FPI_MECHANISMS'] = ':'.join(map(str, x))

	# Initialize imaginary for subcommands.
	ifactors = os.environ.get('FPI_PARAMETERS', '')
	if ifactors.strip():
		prefix = ':'
	else:
		prefix = ''
		ifactors = ''
	os.environ['FPI_PARAMETERS'] = ifactors + prefix + str(i.route/'parameters')

	# Usually factors.
	command = args[index:]
	if not command:
		sys.stderr.write('no command specified\n')
		return inv.exit(64) # EX_USAGE

	if parameters['rebuild']:
		os.environ['FPI_REBUILD'] = '1'

	if command[0] in ('reconstruct', 're'):
		command[0] = 'construct'
		os.environ['FPI_REBUILD'] = '1'

	if command[0] in ('python', 'py'):
		os.execv(parameters['python'], command)
	else:
		os.execv(parameters['python'], [
			parameters['python'], '-m', parameters['prefix'] + '.' + command[0]] + command[1:]
		)

	return inv.exit(1)

if __name__ == '__main__':
	libsys.control(main, libsys.Invocation.system())
