#include <setjmp.h>
#include <time.h>
#include <sys/time.h>

#include <fault/roles.h>
#include <fault/python/environ.h>

typedef long long long_long;

#define INT_TYPES() \
	X(int,int) \
	X(short,short) \
	X(long,long) \
	X(char,char) \
	X(long long,long_long) \

#define REAL_TYPES() \
	X(float,float) \
	X(double,double) \
	X(long double,long_double) \

typedef void * voidptr;

#define POINTER_TYPES() \
	X(voidptr) \
	X(ptrdiff_t) \
	X(intptr_t) \

#define X(y,z) typedef unsigned y _u_##z; typedef signed y _s_##z;
INT_TYPES()
#undef X

#define C_TYPES() \
	X(void) \
	X(va_list) \
	X(jmp_buf) \

#define ADD(y, z) PyModule_AddIntConstant(mod, y, sizeof(z))

#define TIME_TYPES() \
	X(struct timeval, timeval) \
	X(struct timezone, timezone) \
	X(struct tm, tm) \
	X(time_t, time_t) \

#include <fault/python/module.h>
INIT("Sizes of the standard C types.")
{
	PyObj mod;
	CREATE_MODULE(&mod);
	if (mod == NULL)
		return(NULL);

#define X(_,x) ADD(#x, x); ADD("signed_" #x, _s_##x); ADD("unsigned_" #x, _u_##x);
	INT_TYPES()
#undef X

#define X(y,x) ADD(#x, y);
	REAL_TYPES()
	TIME_TYPES()
#undef X

#define X(p) ADD(#p, p);
	POINTER_TYPES()
	C_TYPES()
#undef X

	return(mod);
}
/*
 * vim: ts=3:sw=3:noet:
 */
