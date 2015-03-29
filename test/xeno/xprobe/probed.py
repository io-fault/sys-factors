from ... import libframe, libprobe

# used to validate module identity
data = 'expected'

def probe(context):
	context.define(foo = '"bar"')
