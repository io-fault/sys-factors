"""
# Data regarding Construction Context intentions.
"""

description = {
	'optimal': "Subjective performance selection",
	'debug': "Reduced optimizations and defines for emitting debugging information",

	'injections': "Debugging intention with support for injections for comprehensive testing",
	'instruments': "Test intention with profiling and coverage collection enabled",

	'fragments': "Source file AST extraction context",
}

flags = {
	'optimal': '-O',
	'debug': '-g',

	'injections': '-J',
	'instruments': '-M',

	'fragments': '-A',
}
