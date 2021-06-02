"""
# Initialize a Construction Context for processing factors into a form usable by a system.
"""
import os
import sys
import pickle

from fault.system import files
from fault.system import python
from fault.system import process
from fault.system import execution as libexec
from fault.project import root

from .. import constructors

def source_domain():
	"""
	# Initialize (factor/domain)`source` for inclusion in a Context.
	"""

	return {
		'variants': {
			'system': 'void',
			'architecture': 'sources',
		},

		'formats': {
			'source-tree': 'directory',
			'factor-index': None,
			'image': None,
		},

		'transformations': {
			None: {
				'interface': constructors.__name__ + '.transparent',
				'type': 'transparent',
				'command': '/bin/cp',
			},
		}
	}

def skeleton(intention, requirement=None, variants={}):
	"""
	# Initialize a construction context for host targets.
	"""

	return {
		'context': {
			# The target intent.
			'intention': intention,
			# The requirement intent.
			'requirement': requirement,

			# The override variants.
			'overrides': variants,
		},
		'source': source_domain(),
	}

ep_template = b"""
import sys
import os
import os.path
ctx_path = os.path.realpath(os.path.dirname(sys.argv[0]))
ctx_lib = os.path.join(ctx_path, 'local')
fp = os.environ.get('FACTORPATH', '')
os.environ['PYTHONPATH'] = fpath
os.environ['FACTORPATH'] = fp + ':' + ctx_lib
os.execv(sys.executable, [
		sys.executable, '-m', %s, ctx_path,
	] + sys.argv[1:]
)
"""

project_info = {
	'identifier': "&<http://fault.io/engineering/context-support>",
	'name': "f_intention",
	'abstract': "Context support project.",
	'authority': "`fault.io`",
	'status': "volatile",
	'icon': "- (emoji)`" + "\uD83D\uDEA7`".encode('utf-16', 'surrogatepass').decode('utf-16'),
	'contact': "&<http://fault.io/critical>"
}

pjtxt = (
	"! CONTEXT:\n"
	"\t/protocol/\n"
	"\t\t&<http://if.fault.io/project/information>\n\n" + "\n".join([
		"/%s/\n\t%s" % i for i in project_info.items()
	]) + "\n"
)

def materialize_support_project(directory, name, fault='fault'):
	imp = python.Import.from_fullname(__package__).container
	tmpl_path = imp.file().container / 'templates' / 'context.txt'

	pdpath = directory ** 1
	sp_id = project_info['identifier'].encode('utf-8')
	(pdpath@"f_intention/.protocol").fs_init(sp_id + b" factors/polynomial-1")
	(pdpath@"f_intention/project.txt").fs_init(pjtxt.encode('utf-8', 'surrogateescape'))

	pd = root.Product(pdpath)
	pd.update()
	pd.store()

	from fault.text.bin import ifst
	return ifst.instantiate(directory, tmpl_path, name)

def context(route, intention, reference, symbols, options):
	ctx = route
	mechdir = ctx / 'mechanisms'
	lib = ctx / 'lib'
	syms = ctx / 'symbols'
	local = ctx / 'local'

	for x in mechdir, lib, local, syms:
		x.fs_mkdir()

	# Initialize entry point for context.

	if 'PYTHONPATH' in os.environ:
		pypath = os.environ['PYTHONPATH']
	else:
		depth = __package__.count('.')
		pypath = __file__
		for x in range(depth+2):
			pypath = os.path.dirname(pypath)

	pypath = '\nfpath = ' + repr(pypath)

	dev = (ctx / 'execute')
	dev.fs_init()
	src = ep_template % (
		repr(__package__ + '.construct').encode('utf-8'),
	)
	dev.fs_store(b'#!' + sys.executable.encode('utf-8') + pypath.encode('utf-8') + src)
	os.chmod(str(dev), 0o744)

	if reference is not None:
		support = str(reference)
	else:
		support = ''

	coredata = skeleton(intention)
	coredata['context']['options'] = options
	coredata['context']['path'] = ['source']

	if intention == 'delineation':
		coredata['context']['requirement'] = 'debug'
		coredata['context']['override-variants'] = {
			'system': 'void',
			'architecture': 'data',
		}

	corefile = mechdir / 'core'
	corefile.fs_store(pickle.dumps({'root': coredata}))
	materialize_support_project(local / 'f_intention', 'intention')

def main(inv:(process.Invocation)) -> (process.Exit):
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
