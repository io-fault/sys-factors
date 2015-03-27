import sys
from .. import libdocument as lib

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
	test/lib.is_module_function(ModuleFunction, test_module) == True
	test/lib.is_module_function(module_data, test_module) == False
	test/lib.is_module_function(dir, lib) == False

	test/lib.is_module_class(Sample, sys.modules[__name__]) == True

	test/lib.is_class_method(Sample.meth) == True
	test/lib.is_class_property(Sample.prop) == True
	test/lib.is_class_property(Sample.__dict__['prop']) == True
	test/lib.is_class_property(Sample.data) == False

def test_project(test):
	project = lib.project(lib)
	test/project['name'] == 'dev'

def test_hierarchy(test):
	hier = lib.hierarchy('fault.dev')

def test_xml(test):
	r = lib.routes.Import.from_fullname('fault.dev.libdocument')

def test_classes(test):
	pass

if __name__ == '__main__':
	import sys; from .. import libtest
	libtest.execute(sys.modules['__main__'])
