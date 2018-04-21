#!/usr/bin/env python3

from Xlib import display
from Xlib.error import DisplayNameError
from ..types.dummy import Display


try:
	_display = display.Display()
except DisplayNameError:
	_display = Display()


NET_WM_PID = _display.get_atom('_NET_WM_PID')
NET_WM_VISIBLE_NAME = _display.get_atom('_NET_WM_VISIBLE_NAME')
NET_WM_NAME = _display.get_atom('_NET_WM_NAME')

NET_CLIENT_LIST = _display.get_atom('_NET_CLIENT_LIST')
NET_ACTIVE_WINDOW = _display.get_atom('_NET_ACTIVE_WINDOW')

WM_STATE = _display.get_atom('WM_STATE')
NET_WM_STATE = _display.get_atom('_NET_WM_STATE')
NET_WM_STATE_MAXIMIZED_VERT = _display.get_atom('_NET_WM_STATE_MAXIMIZED_VERT')
NET_WM_STATE_MAXIMIZED_HORZ = _display.get_atom('_NET_WM_STATE_MAXIMIZED_HORZ')
WM_CHANGE_STATE = _display.get_atom('WM_CHANGE_STATE')

NET_WM_STATE_REMOVE = 0
NET_WM_STATE_ADD = 1
NET_WM_STATE_TOGGLE = 2

NET_MOVERESIZE_WINDOW = _display.get_atom('_NET_MOVERESIZE_WINDOW')
NET_CLOSE_WINDOW = _display.get_atom('_NET_CLOSE_WINDOW')


_display.close()
del _display
