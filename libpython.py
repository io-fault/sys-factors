import ast

def lines(path):
	"""
	Return the set of lines that have expressions.
	"""
	seq = set()
	with open(path) as f:
		a = ast.parse(f.read(), path)
		for x in ast.walk(a):
			if hasattr(x, 'lineno'):
				if x.col_offset != -1:
					if isinstance(x, (ast.Name, ast.List, ast.Tuple, ast.Nonlocal)):
						# Covers some doc-string edges.
						continue
					seq.add(x.lineno)
	return seq
