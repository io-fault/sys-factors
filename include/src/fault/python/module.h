/*
 * Included once by the source file defining module initialization.
 */

/* Appropriate way to define the method table for the module */
#define METHODS() \
	static PyMethodDef methods[]

/* Used to destroy the module in error cases. */
#define DROP_MODULE(MOD) \
do { \
	Py_DECREF(MOD); \
	__dict__ = NULL; \
} while(0)

#if TEST()
	#define DEFINE_MODULE_GLOBALS \
		PyObj __ERRNO_RECEPTACLE__; \
		PyObj __PYTHON_RECEPTACLE__; \
		PyObj __dict__ = NULL;
#else
	#define DEFINE_MODULE_GLOBALS \
		PyObj __dict__ = NULL;
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
	PyMODINIT_FUNC \
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
			*MOD = _MOD; \
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
	PyMODINIT_FUNC _py_INIT_COMPAT(void) \
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

/*
 * Support for failure injection.
 */
#if TEST()
	/*
	 * Support for overriding the ERRNO to inject system call failures.
	 */

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
				if (_er_override == NULL || !PyArg_ParseTuple(_er_override, "i", &seterrno)) \
				{ \
					/* convert to python warning */ \
					PyErr_Clear(); \
					fprintf(stderr, \
						"errno injections must return tuples of '%s' OR False: %s.%s\n", \
						"i", (char *) __func__, #SYSCALL); \
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
