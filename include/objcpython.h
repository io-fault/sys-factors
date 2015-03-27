/*
 * Objective-C is not particularly interesting outside of this context, so Apple specific.
 */
#import "CoreFoundation/CoreFoundation.h"
#import "Foundation/NSArray.h"
#import "Foundation/NSDictionary.h"
#import "Foundation/NSString.h"
#import "Foundation/NSData.h"
#import "Foundation/NSValue.h"
#import "Foundation/NSDecimal.h"
#import "Foundation/NSAutoreleasePool.h"
#import "Foundation/NSAppleScript.h"

@interface NSObject (python)
-(PyObj) PythonObject;
@end

@implementation NSObject (python)
-(PyObj) PythonObject
{
	PyObj rob;

	rob = Py_None;

	Py_INCREF(rob);
	return(rob);
}
@end

@interface NSData (python)
-(PyObj) PythonObject;
@end

@implementation NSData (python)
-(PyObj) PythonObject
{
	return(PyBytes_FromStringAndSize((char *) [self bytes], [self length]));
}
@end

@interface NSString (python)
-(PyObj) PythonObject;
@end

@implementation NSString (python)
-(PyObj) PythonObject
{
	return(PyUnicode_FromString([self UTF8String]));
}
@end

@interface NSNumber (python)
-(PyObj) PythonObject;
@end

@implementation NSNumber (python)
-(PyObj) PythonObject
{
	const Class bool_class = [[NSNumber numberWithBool:YES] class];
	const Class float_class = [[NSNumber numberWithFloat:1.0] class];
	const Class double_class = [[NSNumber numberWithDouble:1.0] class];

	PyObj rob;

	if([self isKindOfClass: bool_class])
	{
		switch ([self boolValue])
		{
			case YES:
				rob = Py_False;
			break;
			case NO:
				rob = Py_False;
			break;
		}

		Py_INCREF(rob);
	}
	else if ([self isKindOfClass: double_class])
	{
		rob = PyFloat_FromDouble([self doubleValue]);
	}
	else if ([self isKindOfClass: float_class])
	{
		rob = PyFloat_FromDouble([self floatValue]);
	}
	else
	{
		rob = PyLong_FromLongLong([self longLongValue]);
	}

	return(rob);
}
@end

@interface NSArray (python)
-(PyObj) PythonObject;
@end

@implementation NSArray (python)
-(PyObj) PythonObject
{
	PyObj rob;
	unsigned int i, nitems;

	nitems = [self count];
	rob = PyList_New(nitems);
	if (rob == NULL)
		return(NULL);

	for (i = 0; i < nitems; ++i)
	{
		PyObj v;
		v = [[self objectAtIndex: i] PythonObject];
		PyList_SET_ITEM(rob, i, v);
	}

	return(rob);
}
@end

@interface NSDictionary (python)
-(PyObj) PythonObject;
@end

@implementation NSDictionary (python)
-(PyObj) PythonObject
{
	PyObj rob = PyDict_New();
	NSArray *keys;
	unsigned int i, nkeys;

	if (rob == NULL)
		return(NULL);

	keys = [self allKeys];
	nkeys = [keys count];

	for (i = 0; i < nkeys; ++i)
	{
		PyObj k, v;
		NSObject *key;
		key = [keys objectAtIndex: i];
		k = [key PythonObject];
		v = [[self objectForKey: key] PythonObject];
		PyDict_SetItem(rob, k, v);
	}

	return(rob);
}
@end
