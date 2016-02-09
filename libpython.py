"""
Functions for working with Python syntax.
"""
import ast

untraversable_nodes = (
	ast.Global, ast.Dict, ast.Str,
	ast.Name, ast.List, ast.Tuple,
	ast.arg,
	ast.Assign,
)

def lines(path):
	"""
	Return the set of lines that have expressions.
	"""
	seq = set()
	add = seq.add
	with open(path) as f:
		a = ast.parse(f.read(), path)
		maxlineno = 0
		for x in ast.walk(a):
			if hasattr(x, 'lineno'):
				if x.col_offset != -1:
					if isinstance(x, untraversable_nodes):
						# Letting expression nodes generate the coverable set.
						# These nodes don't actually generate line events during tracing.
						continue
					add(x.lineno)
				maxlineno = max(x.lineno, maxlineno)
	return seq

if __name__ == '__main__':
	import sys
	print(lines(sys.argv[1]))
