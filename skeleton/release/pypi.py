# root package module documentation
from .. import (__doc__ as LONG_DESCRIPTION)
from ..project import identity as URL

#URL = '' # override project.identity

# Adjust for common sphinx roles.
LONG_DESCRIPTION = """
.. role:: manpage(literal)
.. role:: py:attr(literal)
.. role:: py:meth(literal)
.. role:: py:class(literal)
.. role:: py:mod(literal)
.. role:: py:obj(literal)
.. role:: py:func(literal)
.. role:: py:attribute(literal)
.. role:: py:method(literal)
.. role:: py:module(literal)
.. role:: py:object(literal)
.. role:: py:function(literal)
""" + LONG_DESCRIPTION

CLASSIFIERS = [
	'Development Status :: 3 - Alpha',
	#'Development Status :: 5 - Production/Stable',
	'Intended Audience :: Developers',
	'Environment :: Console',
	'License :: Public Domain',
	'License :: Freely Distributable',
	'License :: Freeware',
	'Natural Language :: English',
	'Operating System :: OS Independent',
	'Programming Language :: Python',
	'Programming Language :: Python :: 3',
	'Topic :: Software Development :: Libraries',
	'Topic :: Software Development :: Build Tools',
	'Topic :: Software Development :: Debuggers',
	'Topic :: Software Development :: Testing',
	'Topic :: System :: Shells',
	'Topic :: System :: Software Distribution',
	'Topic :: Utilities',
]
