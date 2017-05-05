/**
	# A C-Preprocessor dataset providing access to POSIX errnos.

	# Some systems do not include the full set of defines, so
	# compensation is performed in order to allow proper
	# X-macro expansion without too much difficulty.

	# This file should only be included when building
	# lookup table functions for better error descriptions.
**/

/*
	# Compensation for missing errnos.
*/
#define ENOTDEFINED -0x00F0C0DE

#ifndef ENONE
	#define ENONE 0
#endif

/**
	# If there isn't a definition, attempt to avoid colliding with a real error code.
	# (ENOTDEFINED - C)
**/
#ifndef E2BIG
	#define E2BIG ENOTDEFINED - 1
#endif
#ifndef EACCES
	#define EACCES ENOTDEFINED - 2
#endif
#ifndef EADDRINUSE
	#define EADDRINUSE ENOTDEFINED - 3
#endif
#ifndef EADDRNOTAVAIL
	#define EADDRNOTAVAIL ENOTDEFINED - 4
#endif
#ifndef EAFNOSUPPORT
	#define EAFNOSUPPORT ENOTDEFINED - 5
#endif
#ifndef EAGAIN
	#define EAGAIN ENOTDEFINED - 6
#endif
#ifndef EALREADY
	#define EALREADY ENOTDEFINED - 7
#endif
#ifndef EBADF
	#define EBADF ENOTDEFINED - 8
#endif
#ifndef EBADMSG
	#define EBADMSG ENOTDEFINED - 9
#endif
#ifndef EBUSY
	#define EBUSY ENOTDEFINED - 10
#endif
#ifndef ECANCELED
	#define ECANCELED ENOTDEFINED - 11
#endif
#ifndef ECHILD
	#define ECHILD ENOTDEFINED - 12
#endif
#ifndef ECONNABORTED
	#define ECONNABORTED ENOTDEFINED - 13
#endif
#ifndef ECONNREFUSED
	#define ECONNREFUSED ENOTDEFINED - 14
#endif
#ifndef ECONNRESET
	#define ECONNRESET ENOTDEFINED - 15
#endif
#ifndef EDEADLK
	#define EDEADLK ENOTDEFINED - 16
#endif
#ifndef EDESTADDRREQ
	#define EDESTADDRREQ ENOTDEFINED - 16
#endif
#ifndef EDOM
	#define EDOM ENOTDEFINED - 17
#endif
#ifndef EDQUOT
	#define EDQUOT ENOTDEFINED - 18
#endif
#ifndef EEXIST
	#define EEXIST ENOTDEFINED - 19
#endif
#ifndef EFAULT
	#define EFAULT ENOTDEFINED - 20
#endif
#ifndef EFBIG
	#define EFBIG ENOTDEFINED - 21
#endif
#ifndef EHOSTUNREACH
	#define EHOSTUNREACH ENOTDEFINED - 22
#endif
#ifndef EIDRM
	#define EIDRM ENOTDEFINED - 23
#endif
#ifndef EILSEQ
	#define EILSEQ ENOTDEFINED - 24
#endif
#ifndef EINPROGRESS
	#define EINPROGRESS ENOTDEFINED - 25
#endif
#ifndef EINTR
	#define EINTR ENOTDEFINED - 26
#endif
#ifndef EINVAL
	#define EINVAL ENOTDEFINED - 27
#endif
#ifndef EIO
	#define EIO ENOTDEFINED - 28
#endif
#ifndef EISCONN
	#define EISCONN ENOTDEFINED - 29
#endif
#ifndef EISDIR
	#define EISDIR ENOTDEFINED - 30
#endif
#ifndef ELOOP
	#define ELOOP ENOTDEFINED - 31
#endif
#ifndef EMFILE
	#define EMFILE ENOTDEFINED - 32
#endif
#ifndef EMLINK
	#define EMLINK ENOTDEFINED - 33
#endif
#ifndef EMSGSIZE
	#define EMSGSIZE ENOTDEFINED - 34
#endif
#ifndef EMULTIHOP
	#define EMULTIHOP ENOTDEFINED - 35
#endif
#ifndef ENAMETOOLONG
	#define ENAMETOOLONG ENOTDEFINED - 36
#endif
#ifndef ENETDOWN
	#define ENETDOWN ENOTDEFINED - 37
#endif
#ifndef ENETRESET
	#define ENETRESET ENOTDEFINED - 38
#endif
#ifndef ENETUNREACH
	#define ENETUNREACH ENOTDEFINED - 39
#endif
#ifndef ENFILE
	#define ENFILE ENOTDEFINED - 40
#endif
#ifndef ENOBUFS
	#define ENOBUFS ENOTDEFINED - 41
#endif
#ifndef ENODATA
	#define ENODATA ENOTDEFINED - 42
#endif
#ifndef ENODEV
	#define ENODEV ENOTDEFINED - 43
#endif
#ifndef ENOENT
	#define ENOENT ENOTDEFINED - 44
#endif
#ifndef ENOEXEC
	#define ENOEXEC ENOTDEFINED - 45
#endif
#ifndef ENOLCK
	#define ENOLCK ENOTDEFINED - 46
#endif
#ifndef ENOLINK
	#define ENOLINK ENOTDEFINED - 47
#endif
#ifndef ENOMEM
	#define ENOMEM ENOTDEFINED - 48
#endif
#ifndef ENOMSG
	#define ENOMSG ENOTDEFINED - 49
#endif
#ifndef ENOPROTOOPT
	#define ENOPROTOOPT ENOTDEFINED - 50
#endif
#ifndef ENOSPC
	#define ENOSPC ENOTDEFINED - 51
#endif
#ifndef ENOSR
	#define ENOSR ENOTDEFINED - 52
#endif
#ifndef ENOSTR
	#define ENOSTR ENOTDEFINED - 53
#endif
#ifndef ENOSYS
	#define ENOSYS ENOTDEFINED - 54
#endif
#ifndef ENOTCONN
	#define ENOTCONN ENOTDEFINED - 55
#endif
#ifndef ENOTDIR
	#define ENOTDIR ENOTDEFINED - 56
#endif
#ifndef ENOTEMPTY
	#define ENOTEMPTY ENOTDEFINED - 57
#endif
#ifndef ENOTSOCK
	#define ENOTSOCK ENOTDEFINED - 58
#endif
#ifndef ENOTSUP
	#define ENOTSUP ENOTDEFINED - 59
#endif
#ifndef ENOTTY
	#define ENOTTY ENOTDEFINED - 60
#endif
#ifndef ENXIO
	#define ENXIO ENOTDEFINED - 61
#endif
#ifndef EOPNOTSUPP
	#define EOPNOTSUPP ENOTDEFINED - 62
#endif
#ifndef EOVERFLOW
	#define EOVERFLOW ENOTDEFINED - 63
#endif
#ifndef EPERM
	#define EPERM ENOTDEFINED - 64
#endif
#ifndef EPIPE
	#define EPIPE ENOTDEFINED - 65
#endif
#ifndef EPROTO
	#define EPROTO ENOTDEFINED - 66
#endif
#ifndef EPROTONOSUPPORT
	#define EPROTONOSUPPORT ENOTDEFINED - 67
#endif
#ifndef EPROTOTYPE
	#define EPROTOTYPE ENOTDEFINED - 68
#endif
#ifndef ERANGE
	#define ERANGE ENOTDEFINED - 69
#endif
#ifndef EROFS
	#define EROFS ENOTDEFINED - 70
#endif
#ifndef ESPIPE
	#define ESPIPE ENOTDEFINED - 71
#endif
#ifndef ESRCH
	#define ESRCH ENOTDEFINED - 72
#endif
#ifndef ESTALE
	#define ESTALE ENOTDEFINED - 73
#endif
#ifndef ETIME
	#define ETIME ENOTDEFINED - 74
#endif
#ifndef ETIMEDOUT
	#define ETIMEDOUT ENOTDEFINED - 75
#endif
#ifndef ETXTBSY
	#define ETXTBSY ENOTDEFINED - 76
#endif
#ifndef EWOULDBLOCK
	#define EWOULDBLOCK ENOTDEFINED - 77
#endif
#ifndef EXDEV
	#define EXDEV ENOTDEFINED - 78
#endif

/**
	# (system/manual)`strerror` is normally acceptable, but the macro
	# table here can also be used to lookup the define
	# name as well as the POSIX defined description string.
**/
#define _FAULT_ERRNO_TABLE() \
	XDEF(E2BIG, "Argument list too long.") \
	XDEF(EACCES, "Permission denied.") \
	XDEF(EADDRINUSE, "Address in use.") \
	XDEF(EADDRNOTAVAIL, "Address not available.") \
	XDEF(EAFNOSUPPORT, "Address family not supported.") \
	XDEF(EAGAIN, "Resource unavailable, try again.") \
	XDEF(EALREADY, "Connection already in progress.") \
	XDEF(EBADF, "Bad file descriptor.") \
	XDEF(EBADMSG, "Bad message.") \
	XDEF(EBUSY, "Device or resource busy.") \
	XDEF(ECANCELED, "Operation canceled.") \
	XDEF(ECHILD, "No child processes.") \
	XDEF(ECONNABORTED, "Connection aborted.") \
	XDEF(ECONNREFUSED, "Connection refused.") \
	XDEF(ECONNRESET, "Connection reset.") \
	XDEF(EDEADLK, "Resource deadlock would occur.") \
	XDEF(EDESTADDRREQ, "Destination address required.") \
	XDEF(EDOM, "Mathematics argument out of domain of function.") \
	XDEF(EDQUOT, "Reserved.") \
	XDEF(EEXIST, "File exists.") \
	XDEF(EFAULT, "Bad address.") \
	XDEF(EFBIG, "File too large.") \
	XDEF(EHOSTUNREACH, "Host is unreachable.") \
	XDEF(EIDRM, "Identifier removed.") \
	XDEF(EILSEQ, "Illegal byte sequence.") \
	XDEF(EINPROGRESS, "Operation in progress.") \
	XDEF(EINTR, "Interrupted function.") \
	XDEF(EINVAL, "Invalid argument.") \
	XDEF(EIO, "I/O error.") \
	XDEF(EISCONN, "Socket is connected.") \
	XDEF(EISDIR, "Is a directory.") \
	XDEF(ELOOP, "Too many levels of symbolic links.") \
	XDEF(EMFILE, "Too many open files.") \
	XDEF(EMLINK, "Too many links.") \
	XDEF(EMSGSIZE, "Message too large.") \
	XDEF(EMULTIHOP, "Reserved.") \
	XDEF(ENAMETOOLONG, "Filename too long.") \
	XDEF(ENETDOWN, "Network is down.") \
	XDEF(ENETRESET, "Connection aborted by network.") \
	XDEF(ENETUNREACH, "Network unreachable.") \
	XDEF(ENFILE, "Too many files open in system.") \
	XDEF(ENOBUFS, "No buffer space available.") \
	XDEF(ENODATA, "No message is available on the STREAM head read queue.") \
	XDEF(ENODEV, "No such device.") \
	XDEF(ENOENT, "No such file or directory.") \
	XDEF(ENOEXEC, "Executable file format error.") \
	XDEF(ENOLCK, "No locks available.") \
	XDEF(ENOLINK, "Reserved.") \
	XDEF(ENOMEM, "Not enough space.") \
	XDEF(ENOMSG, "No message of the desired type.") \
	XDEF(ENOPROTOOPT, "Protocol not available.") \
	XDEF(ENOSPC, "No space left on device.") \
	XDEF(ENOSR, "No STREAM resources.") \
	XDEF(ENOSTR, "Not a STREAM.") \
	XDEF(ENOSYS, "Function not supported.") \
	XDEF(ENOTCONN, "The socket is not connected.") \
	XDEF(ENOTDIR, "Not a directory.") \
	XDEF(ENOTEMPTY, "Directory not empty.") \
	XDEF(ENOTSOCK, "Not a socket.") \
	XDEF(ENOTTY, "Inappropriate I/O control operation.") \
	XDEF(ENXIO, "No such device or address.") \
	XDEF(EOVERFLOW, "Value too large to be stored in data type.") \
	XDEF(EPERM, "Operation not permitted.") \
	XDEF(EPIPE, "Broken pipe.") \
	XDEF(EPROTO, "Protocol error.") \
	XDEF(EPROTONOSUPPORT, "Protocol not supported.") \
	XDEF(EPROTOTYPE, "Protocol wrong type for socket.") \
	XDEF(ERANGE, "Result too large.") \
	XDEF(EROFS, "Read-only file system.") \
	XDEF(ESPIPE, "Invalid seek.") \
	XDEF(ESRCH, "No such process.") \
	XDEF(ESTALE, "Reserved.") \
	XDEF(ETIME, "Stream ioctl() timeout.") \
	XDEF(ETIMEDOUT, "Connection timed out.") \
	XDEF(ETXTBSY, "Text file busy.") \
	XDEF(EXDEV, "Cross-device link.") \
	\
	XDEF(EOPNOTSUPP, "Operation not supported on socket.") \
	\
	XDEF(ENONE, "No error occurred.") \
	XDEF(ENOTDEFINED, "Error number was not defined in \"sys/errno.h\".")

/**
	# Handle exceptional cases where the system defines these as the same errno.
**/

#if EWOULDBLOCK != EAGAIN
	#define _FAULT_ERRNO_WOULDBLOCK XDEF(EWOULDBLOCK, "Operation would block.")
#else
	#warning EAGAIN == EWOULDBLOCK
	#define _FAULT_ERRNO_WOULDBLOCK
#endif

#if ENOTSUP != EOPNOTSUPP
	#define _FAULT_ERRNO_OPNOTSUPP XDEF(ENOTSUP, "Not supported.")
#else
	#warning EOPNOTSUPP == ENOTSUP
	#define _FAULT_ERRNO_OPNOTSUPP
#endif

#define FAULT_POSIX_ERRNO_TABLE() \
	_FAULT_ERRNO_WOULDBLOCK \
	_FAULT_ERRNO_OPNOTSUPP \
	_FAULT_ERRNO_TABLE()
