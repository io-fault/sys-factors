#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <structmember.h>
#include <pythread.h>

/*
 * Symbol for filting coverage results.
 */
#define XCOVERAGE

#define FACET(PROBE_NAME) (xxFACETxxx##PROBE_NAME)
#define FEATURE(FEATURE_NAME) (xxFEATURExxx##FEATURE_NAME)

#define xxROLE(R, OPT) (xxx##R##xxx & xxx##R##x##OPT)

#define TEST(y)		xxROLE(TEST, y)
#define DEBUG(y)		xxROLE(DEBUG, y)
#define FACTOR(y)		xxROLE(FACTOR, y)
#define INSPECT(y)	xxROLE(INSPECT, y)
#define BOOTSTRAP(y)	xxROLE(BOOTSTRAP, y)

#define ROLE_OPTION(r, x) (xxx##r##xxx & xxx##r##x##OPT)
#define FACTOR_ROLE(r) xxROLE(r)

#define F_ROLE(N)
#define F_FEATURE(F) (xXx##F##xXx & xxxF_##O##FEATURE)
#define F_OPTION(O) (xxx##O##xxx & xxxF_##O##OPT)

#if TEST()
#define ROLE TEST
#elif DEBUG()
#define ROLE DEBUG
#elif FACTOR()
#define ROLE FACTOR
#elif INSPECT()
#define ROLE INSPECT
#elif BOOTSTRAP()
#define ROLE BOOTSTRAP
#else
#error unknown role
#endif

#define include_docstr (1L)

/*
 * Don't inherit Python's doc-string configuration for non-optimized builds.
 */
#if FACTOR(DOCSTRINGS)
#undef PyDoc_STR
#define PyDoc_STR(x) x
#elif FACTOR()
#undef PyDoc_STR
#define PyDoc_STR(x) ""
#endif

/*
 * Cover for its absence.
 */
#ifndef Py_RETURN_NONE
#define Py_RETURN_NONE do { Py_INCREF(Py_None); return(Py_None); } while(0)
#endif

typedef PyObject * PyObj;

#ifndef __cplusplus
static PyMethodDef methods[];
static struct PyModuleDef module;
static PyObj __dict__;
#else
static PyObj __dict__;
#endif

#define METHODS() \
	static PyMethodDef methods[]

#define QPATH(tail) MODULE_QNAME "." tail

#define PyAllocate(TYP) (((PyTypeObject *) TYP)->tp_alloc((PyTypeObject *) TYP, 0))

static inline PyObj
import_sibling(const char *modname, const char *attribute)
{
	PyObj is_m, is_ob, is_fromlist;

	is_fromlist = Py_BuildValue("(s)", attribute);
	if (is_fromlist == NULL)
		return(NULL);

   is_m = PyImport_ImportModuleLevel(modname, __dict__, __dict__, is_fromlist, 1);

	Py_DECREF(is_fromlist);
	if (is_m == NULL)
		return(NULL);

	is_ob = PyObject_GetAttrString(is_m, attribute);
	Py_DECREF(is_m);

	return(is_ob);
}

#define DROP_MODULE(MOD) \
do { \
	Py_DECREF(MOD); \
	__dict__ = NULL; \
} while(0)

#if PY_MAJOR_VERSION > 2

/*
 * Python 3.x
 */
#define INIT(DOCUMENTATION) \
static struct PyModuleDef \
module = { \
	PyModuleDef_HEAD_INIT, \
	MODULE_QNAME, \
	DOCUMENTATION, \
	-1, \
	methods \
}; \
PyMODINIT_FUNC INIT_FUNCTION(void)

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
			*MOD = _MOD; \
	} \
} while(0)
#else

/*
 * Python 2.x
 */

/*
 * Just invoke the new signature. Allows the user to return(NULL) regardless of Python
 * version.
 */
#define INIT(DOCUMENTATION) \
	static PyObject * INIT_FUNCTION(void); /* prototype */ \
	PyMODINIT_FUNC INIT_FUNCTION_COMPAT(void) { PyObj mod; mod = INIT_FUNCTION(); /* for consistent return() signature */ } \
	static PyObject * INIT_FUNCTION(void)

#define CREATE_MODULE(MOD) do { \
	PyObj _MOD = Py_InitModule(MODULE_QNAME, methods); \
	if (_MOD) { __dict__ = PyModule_GetDict(_MOD); \
		if (__dict__ == NULL) { Py_DECREF(_MOD); *MOD = NULL; } \
		else *MOD = _MOD; \
	} \
} while(0)
#endif

/*
 * Override support for error injection.
 */
#if TEST()
/*
 * Support for overriding the ERRNO for arbitrary port calls.
 */

/*
 * Dictionary of configured injectors.
 */
static PyObj __ERRNO_RECEPTACLE__ = NULL;
static PyObj __PYTHON_RECEPTACLE__ = NULL;

#define ERRNO_INJECTION_RETURN "i"

/*
 * Reclaiming the GIL is rather time consuming in some contexts,
 * so if the dictionary is zero, don't bother.
 *
 * ERRNO_RECEPTACLE(0, &r, open, ...)
 * if (r == 0)
 * {
 *
 * }
 */
#define ERRNO_RECEPTACLE(ERROR_STATUS, RETURN, SYSCALL, ...) \
do { \
	PyObj _er_entry; \
	PyGILState_STATE _er_gs; \
	if (PyDict_Size(__ERRNO_RECEPTACLE__) == 0) \
	{ \
		*(RETURN) = SYSCALL(__VA_ARGS__); \
	} \
	else \
	{ \
		_er_gs = PyGILState_Ensure(); /* need it to get the item */ \
		_er_entry = PyDict_GetItemString(__ERRNO_RECEPTACLE__, (char *) (__func__ "." #SYSCALL)); \
\
		if (_er_entry == NULL) \
		{ \
			*(RETURN) = SYSCALL(__VA_ARGS__); \
		} \
		else \
		{ \
			PyObj _er_override = PyObject_CallFunction(_er_entry, "ss", (char *) __func__, #SYSCALL); \
\
			if (_er_override == Py_False) \
			{ \
				/* dont override and perform syscall */ \
				*(RETURN) = SYSCALL(__VA_ARGS__); \
			} \
			else \
			{ \
				/* overridden */ \
				int seterrno = -1; \
				if (_er_override == NULL || !PyArg_ParseTuple(_er_override, ERRNO_INJECTION_RETURN, &seterrno)) \
				{ \
					/* convert to python warning */ \
					PyErr_Clear(); \
					fprintf(stderr, \
						"errno injections must return tuples of '%s' OR False: %s.%s\n", \
						ERRNO_INJECTION_RETURN, (char *) __func__, #SYSCALL); \
				} \
				/* injected errno */ \
				errno = seterrno; \
				*(RETURN) = ERROR_STATUS; \
			} \
\
			Py_XDECREF(_er_override); \
		} \
		PyGILState_Release(_er_gs); \
	} \
} while(0)

/*
 * Usually called with GIL. Dynamically override a C-API call.
 */
#define PYTHON_RECEPTACLE(ID, RETURN, CALL, ...) \
do { \
	PyObj _pr_entry; \
	if (PyDict_Size(__PYTHON_RECEPTACLE__) == 0) \
	{ \
		*((PyObj *) RETURN) = (PyObj) CALL(__VA_ARGS__); \
	} \
	else \
	{ \
		_pr_entry = PyDict_GetItemString(__PYTHON_RECEPTACLE__, (char *) __func__ "." ID); \
		if (_pr_entry == NULL) \
		{ \
			*((PyObj *) RETURN) = (PyObj) CALL(__VA_ARGS__); \
		} \
		else \
		{ \
			PyObj _pr_override = PyObject_CallFunction(_pr_entry, "s", #CALL); \
			if (_pr_override == Py_False) \
			{ \
				Py_DECREF(_pr_override); \
				*((PyObj *) RETURN) = (PyObj) CALL(__VA_ARGS__); \
			} \
			else if (_pr_override != NULL) \
			{ \
				/* overridden */ \
				if (!PyArg_ParseTuple(_pr_override, "(O)", RETURN)) \
				{ \
					*(RETURN) = NULL; \
				} \
			} \
			else \
			{ \
				*(RETURN) = NULL; \
			} \
		} \
	} \
} while(0)

#else
#define ERRNO_RECEPTACLE(ERROR_STATUS, RETURN, SYSCALL, ...) \
	*(RETURN) = SYSCALL(__VA_ARGS__)

#define PYTHON_RECEPTACLE(ID, RETURN, CALL, ...) \
	*((PyObj *) RETURN) = (PyObj) CALL(__VA_ARGS__)
#endif
