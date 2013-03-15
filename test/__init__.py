import contextlib

@contextlib.contextmanager
def context():
	global some_var
	try:
		some_var = 'context!'
		yield None
	finally:
		del some_var
