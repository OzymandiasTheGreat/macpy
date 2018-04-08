from ctypes import Structure, POINTER, c_long, c_int32, c_uint32, c_uint64
from ctypes import Union, c_short, c_void_p, c_uint


class Point(Structure):

	_fields_ = [('x', c_long), ('y', c_long)]


class MSLLHOOKSTRUCT(Structure):

	_fields_ = [
		('pt', Point),
		('mouseData', c_int32),
		('flags', c_uint32),
		('time', c_uint32),
		('dwExtraInfo', c_uint64)]


class MOUSEINPUT(Structure):

	_fields_ = (
		('dx', c_long),
		('dy', c_long),
		('mouseData', c_int32),
		('dwFlags', c_uint32),
		('time', c_uint32),
		('dwExtraInfo', c_void_p))


class KEYBDINPUT(Structure):

	_fields_ = (
		('wVk', c_short),
		('wScan', c_short),
		('dwFlags', c_uint32),
		('time', c_uint32),
		('dwExtraInfo', c_void_p))


class HARDWAREINPUT(Structure):

	_fields_ = (
		('uMsg', c_uint32),
		('wParamL', c_short),
		('wParamH', c_short))


class INPUTunion(Union):

	_fields_ = (
		('mi', MOUSEINPUT),
		('ki', KEYBDINPUT),
		('hi', HARDWAREINPUT))


class INPUT(Structure):

	_fields_ = (
		('type', c_uint32),
		('union', INPUTunion))


class KBDLLHOOKSTRUCT(Structure):

	_fields_ = (
		('vkCode', c_uint32),
		('scanCode', c_uint32),
		('flags', c_uint32),
		('time', c_uint32),
		('dwExtraInfo', c_void_p))


class RECT(Structure):

	_fields_ = (
		('left', c_long),
		('top', c_long),
		('right', c_long),
		('bottom', c_long))


class WINDOWPLACEMENT(Structure):

	_fields_ = (
		('length', c_uint),           # sizeof(WINDOWPLACEMENT)
		('flags', c_uint),
		('showCmd', c_uint),
		('ptMinPosition', Point),
		('ptMaxPosition', Point),
		('rcNormalPosition', RECT))
