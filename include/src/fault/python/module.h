/**
	# Included once by the source file defining module initialization.
*/
#include "../symbols.h"

#ifndef MODULE_FUNCTIONS
	#warning MODULE_FUNCTIONS() macro not defined. Should be defined by importer. Using empty set.
	#define MODULE_FUNCTIONS()
#endif

#if FV_INSTRUMENTS() && __clang__
	void __llvm_profile_write_file(void);
	void __llvm_profile_reset_counters(void);
	void __llvm_profile_set_filename(const char *);

	static PyObj _fault_metrics_flush(PyObj self) { __llvm_profile_write_file(); Py_RETURN_NONE; }
	static PyObj _fault_metrics_clear(PyObj self) { __llvm_profile_reset_counters(); Py_RETURN_NONE; }

	static PyObj _fault_metrics_file(PyObj self, PyObj filepath)
	{
		static char ifbuf[2048] = {0,}; /* buf must be valid after exit */

		PyObj bytes;
		bytes = PyUnicode_EncodeFSDefault(filepath);
		if (bytes == NULL)
			return(NULL);

		if (PyBytes_GET_SIZE(bytes) < 2048)
		{
			memcpy(ifbuf, PyBytes_AS_STRING(bytes), PyBytes_GET_SIZE(bytes));
			ifbuf[PyBytes_GET_SIZE(bytes)] = 0;
			__llvm_profile_set_filename(ifbuf);
		}

		Py_DECREF(bytes);
		Py_RETURN_NONE;
	}

	#define FAULT_MODULE_FUNCTIONS() \
		PYMETHOD(_fault_metrics_set_path, _fault_metrics_file, METH_O, "set file path to write to" ) \
		PYMETHOD(_fault_metrics_write, _fault_metrics_flush, METH_NOARGS, "save counters to disk" ) \
		PYMETHOD(_fault_metrics_reset, _fault_metrics_clear, METH_NOARGS, "clear in memory counters" )
#elif FV_INSTRUMENTS()
	#warning No suitable instrumentation for coverage and profiling.
	#define FAULT_MODULE_FUNCTIONS()
#else
	#define FAULT_MODULE_FUNCTIONS()
#endif

/**
	# Used to destroy the module in error cases.
	# This clears the global __dict__ as well.
*/
#define DROP_MODULE(MOD) \
do { \
	Py_DECREF(MOD); \
	__dict__ = NULL; \
} while(0)

#if FV_INJECTIONS()
	#define DEFINE_MODULE_GLOBALS \
		PyObj __ERRNO_RECEPTACLE__; \
		PyObj __PYTHON_RECEPTACLE__; \
		PyObj __dict__ = NULL;

	#define DROP_MODULE_GLOBALS() do { \
			Py_XDECREF(__ERRNO_RECEPTACLE__); \
			Py_XDECREF(__PYTHON_RECEPTACLE__); \
			__ERRNO_RECEPTACLE__ = NULL; \
			__PYTHON_RECEPTACLE__ = NULL; \
		} while(0)

	#define INIT_MODULE_GLOBALS() \
		__ERRNO_RECEPTACLE__ = PyDict_New(); \
		__PYTHON_RECEPTACLE__ = PyDict_New(); \
		if (PyErr_Occurred()) { \
			DROP_MODULE_GLOBALS(); \
		} else { \
			PyDict_SetItemString(__dict__, "__ERRNO_RECEPTACLE__", __ERRNO_RECEPTACLE__); \
			PyDict_SetItemString(__dict__, "__PYTHON_RECEPTACLE__", __PYTHON_RECEPTACLE__); \
		}
#else
	#define DEFINE_MODULE_GLOBALS \
		PyObj __dict__ = NULL;

	/* Nothing without TEST || METRICS */
	#define INIT_MODULE_GLOBALS() ;
	#define DROP_MODULE_GLOBALS() ;
#endif

#define _py_INIT_FUNC_X(BN) CONCAT_IDENTIFIER(PyInit_, BN)
#define _py_INIT_FUNC _py_INIT_FUNC_X(FACTOR_BASENAME)

#if PY_MAJOR_VERSION > 2
/*
	# Python 3.x
*/
#define INIT(DOCUMENTATION) \
	DEFINE_MODULE_GLOBALS \
	static PyMethodDef methods[] = { \
		FAULT_MODULE_FUNCTIONS() \
		MODULE_FUNCTIONS() \
		{NULL,} \
	}; \
	\
	static struct PyModuleDef \
	module = { \
		PyModuleDef_HEAD_INIT, \
		MODULE_QNAME_STR, \
		DOCUMENTATION, \
		-1, \
		methods \
	}; \
	\
	_fault_reveal_symbol PyMODINIT_FUNC \
	_py_INIT_FUNC(void)

#define CREATE_MODULE(MOD) \
do { \
	PyObj _MOD = PyModule_Create(&module); \
	if (_MOD == NULL) \
		*MOD = NULL; /* error */ \
	else \
	{ \
		__dict__ = PyModule_GetDict(_MOD); \
		if (__dict__ == NULL) \
		{ \
			Py_DECREF(_MOD); \
			*MOD = NULL; \
		} \
		else \
		{ \
			INIT_MODULE_GLOBALS(); \
			if (PyErr_Occurred()) \
			{ \
				Py_DECREF(_MOD); \
				*MOD = NULL; \
			} \
			else \
			{ \
				*MOD = _MOD; \
			} \
		} \
	} \
} while(0)
#else
/*
	# Python 2.x
*/
#define _py_INIT_COMPAT CONCAT_IDENTIFIER(init, FACTOR_BASENAME)

/**
	# Invoke the new signature.
	# Allows the user to return(NULL) regardless of Python version.
*/
#define INIT(DOCUMENTATION) \
	DEFINE_MODULE_GLOBALS \
	static PyMethodDef methods[] = { \
		FAULT_MODULE_FUNCTIONS() \
		MODULE_FUNCTIONS() \
		{NULL,} \
	}; \
	static PyObject * _py_INIT_FUNC(void); /* prototype */ \
	_fault_reveal_symbol PyMODINIT_FUNC _py_INIT_COMPAT(void) \
	{ PyObj mod; mod = _py_INIT_FUNC(); /* for consistent return() signature */ } \
	static PyObject * _py_INIT_FUNC(void)

#define CREATE_MODULE(MOD) \
	do { \
		PyObj _MOD = Py_InitModule(MODULE_QNAME_STR, methods); \
		if (_MOD) { \
			__dict__ = PyModule_GetDict(_MOD); \
			if (__dict__ == NULL) { Py_DECREF(_MOD); *MOD = NULL; } \
			else *MOD = _MOD; \
		} \
	} while(0)

#endif
