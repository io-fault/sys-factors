"""
# Initialize a Construction Context for processing factors into a form usable by a system.
"""
import os
import sys
import functools
import pickle

from fault.system import files
from fault.system import python
from fault.system import process
from fault.system import library as libsys

from .. import probe
from .. import cc

def select(paths, possibilities, preferences):
	"""
	# Select a file from the given &paths using the &possibilities and &preferences
	# to identify the most desired.
	"""

	# Override for particular version
	possible = set(possibilities)

	found, missing = probe.search(paths, tuple(possible))
	if not found:
		return None
	else:
		for x in preferences:
			if x in found:
				path = found[x]
				name = x
				break
		else:
			# select one randomly
			name = tuple(found)[0]
			path = found[name]

	return name, path

def factor_domain(paths):
	"""
	# Factor Library processing.
	# Generally only supports libraries which are directories of whole factors and composites.
	"""

	return {
		'target-file-extensions': {},

		'formats': {
			'library': 'directory',
		},

		'transformations': {
			'text': {
				'interface': cc.__name__ + '.transparent',
				'type': 'transparent',
				'command': '/bin/cp',
			},
		}
	}

def source_domain(paths):
	"""
	# Initialize (factor/domain)`source` for inclusion in a Context.
	"""

	mech = {
		'invariant': True,
		'variants': {
			'system': 'void',
			'architecture': 'sources',
		},

		'formats': {
			'executable': 'octets',
			'library': 'octets',
			'extension': 'octets',
			'partial': 'octets',
		},

		'transformations': {
			None: {
				'interface': cc.__name__ + '.transparent',
				'type': 'transparent',
				'command': '/bin/cp',
			},
		}
	}

	return mech

def resource_domain(paths):
	"""
	# Initialize a (factor/type)`resource` subject for inclusion in a context.
	"""

	mech = {
		'invariant': True,
		'variants': {
			'system': 'void',
			'architecture': 'fs',
		},

		'formats': {
			'library': 'octets',
		},

		'transformations': {
			None: {
				'interface': cc.__name__ + '.transparent',
				'type': 'transparent',
				'command': '/bin/cp',
			},
			'uri': {
				'interface': cc.__name__ + '.transparent',
				'method': 'python',
				'command': __package__ + '.stream',
				'redirect': 'stdout',
			}
		}
	}

	return mech

def skeleton(intention, paths):
	"""
	# Initialize a construction context for host targets.
	"""

	return {
		'context': {
			'intention': intention,
		},
		'factor': factor_domain(paths),
		'source': source_domain(paths),
		'resource': resource_domain(paths),

		# Trap domain that emits failure.
		'void': {
			'variants': {
				'system': 'void',
				'architecture': 'dataprofile',
			},
			'formats': {
				'library': 'void',
				'executable': 'void',
				'extension': 'void',
				'partial': 'void',
				'interfaces': 'void',
			},

			'transformations': {
				None: {
					'interface': cc.__name__ + '.void',
					'type': 'void',
					'method': 'python',
					'command': __package__ + '.void',
				}
			},
			'integration': {
				None: {
					'interface': cc.__name__ + '.void',
					'type': 'void',
					'method': 'python',
					'command': __package__ + '.void',
				}
			}
		}
	}

prefix = b"""
import sys
import os
import os.path
factors = os.environ.get('FACTORS')
if factors and factors != fpath:
	fpath = fpath + ':' + factors
ctx_path = os.path.realpath(os.path.dirname(sys.argv[0]))
ctx_lib = os.path.join(ctx_path, 'lib', 'python')
os.environ['CONTEXT'] = ctx_path
dev_bin = %s
""" %(repr(__package__).encode('utf-8'),)

ep_template = prefix + b"""
os.environ['PYTHONPATH'] = ctx_lib + ':' + fpath if fpath else ctx_lib
os.execv(sys.executable, [
		sys.executable, '-m', %s,
		'context', ctx_path,
	] + sys.argv[1:]
)
"""

def materialize_support_project(directory, name, fault='fault'):
	imp = python.Import.from_fullname(__package__).container
	tmpl_path = imp.file().container / 'templates' / 'context.txt'

	command = [
		"python3", "-m",
		fault+'.text.bin.ifst',
		str(directory), str(tmpl_path), name,
	]

	pid, status, data = libsys.effect(libsys.KInvocation(sys.executable, command))
	if status != 0:
		sys.stderr.write("! ERROR: adapter tool instantiation failed\n")
		sys.stderr.write("\t/command\n\t\t" + " ".join(command) + "\n")
		sys.stderr.write("\t/status\n\t\t" + str(status) + "\n")

		sys.stderr.write("\t/message\n")
		sys.stderr.buffer.writelines(b"\t\t" + x + b"\n" for x in data.split(b"\n"))
		raise SystemExit(1)

	return status

def context(route, intention, reference, symbols, options):
	ctx = route
	mechdir = ctx / 'mechanisms'
	lib = ctx / 'lib'
	syms = ctx / 'symbols'
	pylib = lib / 'python'

	for x in mechdir, lib, pylib, syms:
		x.init('directory')

	# Initialize entry point for context.
	initial = __package__.split('.')[0]
	kit = sys.modules[initial]
	pypath = os.path.dirname(os.path.dirname(kit.__file__))
	pypath = '\nfpath = ' + repr(pypath)

	dev = (ctx / 'execute')
	dev.init('file')
	src = ep_template % (
		repr(__package__ + '.interface').encode('utf-8'),
	)
	dev.store(b'#!' + sys.executable.encode('utf-8') + pypath.encode('utf-8') + src)
	os.chmod(str(dev), 0o744)

	cfg = (ctx / 'configure')
	cfg.init('file')
	src = ep_template % (
		repr(__package__ + '.configure').encode('utf-8'),
	)
	cfg.store(b'#!' + sys.executable.encode('utf-8') + pypath.encode('utf-8') + src)
	os.chmod(str(cfg), 0o744)

	if reference is not None:
		support = str(reference)
	else:
		support = ''

	paths = probe.environ_paths()

	coredata = skeleton(intention, paths)
	coredata['context']['options'] = options
	corefile = mechdir / 'core'
	corefile.store(pickle.dumps({'root': coredata}))

	materialize_support_project(pylib / 'f_intention', 'intention')

def main(inv:(process.Invocation)) -> process.Exit:
	refctx = None
	intention, target, *args = inv.args
	syms = {}

	if 'CONTEXT' in os.environ:
		refctx = files.Path.from_absolute(os.environ['CONTEXT'])

	target = files.Path.from_path(target)
	context(target, intention, refctx, syms, set(args))

	return inv.exit(0)

if __name__ == '__main__':
	process.control(main, process.Invocation.system())
