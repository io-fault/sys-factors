/*
 * Included once by the source file defining module initialization.
 */
#include "../symbols.h"

/* Appropriate way to define the method table for the module */
#define METHODS() \
	static PyMethodDef methods[]

/* Used to destroy the module in error cases. */
#define DROP_MODULE(MOD) \
do { \
	Py_DECREF(MOD); \
	__dict__ = NULL; \
} while(0)

#if TEST() || METRICS()
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
 * Python 3.x
 */
#define INIT(DOCUMENTATION) \
	DEFINE_MODULE_GLOBALS \
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
#define _py_INIT_COMPAT CONCAT_IDENTIFIER(init, FACTOR_BASENAME)
/*
 * Python 2.x
 */

/*
 * Just invoke the new signature. Allows the user to return(NULL) regardless of Python
 * version.
 */
#define INIT(DOCUMENTATION) \
	DEFINE_MODULE_GLOBALS \
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
