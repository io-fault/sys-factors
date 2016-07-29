"""
Traceback serialization.
"""

from ....xml import library as libxml

def serialize():
	"""
	Serialize a Python traceback to XML.
	"""

from ....xml import libfactor
libfactor.load('schema', fragment=True)

__factor_type__ = 'xml.library'
