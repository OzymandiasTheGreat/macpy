#!/usr/bin/env python3

from collections import namedtuple


MousePos = namedtuple('PointerPosition', ('x', 'y'))
Modifiers = namedtuple('Modifiers', ('SHIFT', 'ALTGR', 'CTRL', 'ALT', 'META'))
Locks = namedtuple('Locks', ('NUMLOCK', 'CAPSLOCK', 'SCROLLLOCK'))


WinPos = namedtuple('WindowPosition', ('x', 'y'))
WinSize = namedtuple('WindowSize', ('width', 'height'))


# Windows specific
MouseEvent = namedtuple('MouseEvent', ('message', 'point', 'data', 'flags'))
KeyEvent = namedtuple('KeyEvent', ('message', 'vk', 'scancode', 'flags'))
