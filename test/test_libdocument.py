import sys
from .. import libdocument as library

class Sample(object):
	def meth(self):
		'meth doc'
		pass

	@staticmethod
	def staticmeth(self):
		'staticmeth doc'
		pass

	@classmethod
	def classmeth(typ):
		'classmeth doc'
		pass

	@property
	def prop(self):
		'prop doc'
		return None

	data = 'class data'

def ModuleFunction():
	'module function doc'
	pass

module_data = 'module data'

def NoArgs():
	pass

def SingleArgument(arg):
	pass

def TwoArguments(first, second):
	pass

def VariableArguments(*variable_arguments_name):
	pass

def VariableKeywords(**variable_keywords_name):
	pass

def VariableArgumentsKeywords(*variable_arguments_name, **variable_keywords_name):
	pass

def Defaults(first = 'first', second = 'second'):
	pass

def Keywords(*args, first = 'first', second = 'second'):
	pass

def test_type_checks(test, test_module = sys.modules[__name__]):
	# check that is_module_function sees that is_module_function is a
	# function in the module libdocument
	test/library.is_module_function(ModuleFunction, test_module) == True
	test/library.is_module_function(module_data, test_module) == False
	test/library.is_module_function(dir, library) == False

	test/library.is_module_class(Sample, sys.modules[__name__]) == True

	test/library.is_class_method(Sample.meth) == True
	test/library.is_class_property(Sample.prop) == True
	test/library.is_class_property(Sample.__dict__['prop']) == True
	test/library.is_class_property(Sample.data) == False

def test_project(test):
	project = library.project(library)
	test/project['name'] == 'development'

def test_hierarchy(test):
	#hier = library.hierarchy('fault.development')
	pass

def test_xml(test):
	#r = library.routes.Import.from_fullname('fault.dev.libdocument')
	pass

def test_classes(test):
	pass

if __name__ == '__main__':
	import sys; from .. import libtest
	libtest.execute(sys.modules['__main__'])
