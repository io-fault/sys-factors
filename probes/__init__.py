"""
# Filesystem templates for the standard construction context probe set.
"""
__factor_domain__ = 'xml'
__factor_type__ = 'library'

def init(ctx):
	# Initialze default scanner probes.
	sa = (ctx / 'scanner')
	probed = (sa / 'probes')
	status = os.spawnv(os.P_WAIT, sys.executable, [
		sys.executable, '-m', __name__, str(probed)
	])
	(probed / '__init__.py').init('file')
