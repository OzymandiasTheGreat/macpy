#!/usr/bin/env python3

import sys
if sys.version_info >= (3, 6):
	from enum import Enum, auto
else:
	from aenum import Enum, auto
try:
	from time import monotonic
except ImportError:
	from monotonic import monotonic
from .types.tuples import MousePos, Modifiers, Locks


class PointerAxis(Enum):
	"""An enumeration describing pointer scrolling axis.
	"""

	VERTICAL = auto()
	HORIZONTAL = auto()


class WindowEventType(Enum):
	"""An enumeration describing whether window was created, destroyed
	or focused.
	"""

	CREATED = auto()
	DESTROYED = auto()
	FOCUSED = auto()


class WindowState(Enum):
	"""An enumeration describing window state.
	"""

	NORMAL = auto()
	MINIMIZED = auto()
	MAXIMIZED = auto()


class Event(object):
	"""Base class for all macpy events.

	Attributes:
		time (:class:`float`): Event timestamp. This does not translate to
			concrete time but timestamps of later events are guaranteed to be
			greater than timestamps of earlier events.
	"""

	def __init__(self):

		self.time = monotonic()

	def __repr__(self):

		items = []
		for name, attr in self.__dict__.items():
			if not name.startswith('_'):
				items.append('{0}={1}'.format(name, repr(attr)))
		items.sort()
		return '<{0}: {1}>'.format(self.__class__.__name__, ', '.join(items))


class PointerEventMotion(Event):
	"""Event representing pointer movement on screen.

	Attributes:
		position (:class:`tuple`): A namedtuple containing x and y coordinates
			of pointer on screen.
		modifiers (:class:`tuple`): A namedtuple containing modifier state at
			the time of this event.
	"""

	def __init__(self, x, y, modifiers):
		"""Event representing pointer motion.

		Args:
			x (int): Pointer position on x axis in pixels.
			y (int): Pointer position on y axis in pixels.
			modifiers (dict): Modifier key state at the time of this event.
		"""

		Event.__init__(self)
		self.position = MousePos(x, y)
		self.modifiers = Modifiers(**modifiers)


class PointerEventButton(Event):
	"""Event representing button events on connected pointing devices.

	Attributes:
		button (:class:`~macpy.key.Key`): Button that was pressed/released.
		state (:class:`~macpy.key.KeyState`): Whether button was pressed or
			released.
		modifiers (:class:`tuple`): A namedtuple containing modifier state at
			the time of this event.
	"""

	def __init__(self, x, y, button, state, modifiers):
		"""Event representing button press/release.

		Args:
			x (int): Pointer position on x axis in pixels.
			y (int): Pointer position on y axis in pixels.
			button (~macpy.key.Key): Button that was pressed/released.
			state (~macpy.key.KeyState): Whether the button was pressed or
				released.
			modifiers (dict): Modifier key state at the time of this event.
		"""

		Event.__init__(self)
		self.position = MousePos(x, y)
		self.button = button
		self.state = state
		self.modifiers = Modifiers(**modifiers)


class PointerEventAxis(Event):
	"""Event representing scrolling.

	Attributes:
		value (:class:`float`): The amount scrolled. This is platform dependent.
		axis (:class:`.PointerAxis`): The axis along which scrolling ocured.
		modifiers (:class:`tuple`): A namedtuple containing modifier state at
			the time of this event.
	"""

	def __init__(self, x, y, value, axis, modifiers):
		"""Event representing scrolling.

		Args:
			x (int): Pointer position on x axis in pixels.
			y (int): Pointer position on y axis in pixels.
			value (int): The amount scrolled, exact interpretation of this
				value is platform-specific.
			axis (.PointerAxis): The axis along which to scroll.
			modifiers (dict): Modifier key state at the time of this event.
		"""

		Event.__init__(self)
		self.position = MousePos(x, y)
		self.value = value
		self.axis = axis
		self.modifiers = Modifiers(**modifiers)


class KeyboardEvent(Event):
	"""Event representing key press/release on connected keyboards.

	Attributes:
		key (:class:`~macpy.key.Key`): The key that was pressed/released.
		state (:class:`~macpy.key.KeyState`): Whether the key was pressed or
			released.
		char (:class:`str`): The character produced by this key event if any.
		modifiers (:class:`tuple`): A namedtuple containing modifier state at
			the time of this event.
		locks (:class:`tuple`): A namedtuple containing lock key state at the
			time of this event.
	"""

	def __init__(self, key, state, char, modifiers, locks):
		"""Event representing key press/release.

		Args:
			key (~macpy.key.Key): The key that will be pressed/released.
			state (~macpy.key.KeyState): Whether the key will be pressed or
				released.
			char (str): The character that will be typed. Currently this is
				ignored, you can set it to :obj:`None`.
			modifiers (dict): Modifier key state at the time of this event.
			locks (dict): Lock key state at the time of this event.
		"""

		Event.__init__(self)
		self.key = key
		self.state = state
		self.char = char
		self.modifiers = Modifiers(**modifiers)
		self.locks = Locks(**locks)


class HotKey(Event):
	"""A hotkey object.

	Hotkey object are hashable and compare equal regardless of timestamps.

	Attributes:
		key (:class:`~macpy.key.Key`): A key that triggered this event.
		modifiers (:class:`frozenset`): A frozenset of modifier keys that were
			also pressed.
	"""

	def __init__(self, key, modifiers):

		Event.__init__(self)
		self.key = key
		self.modifiers = frozenset(modifiers)

	def __eq__(self, other):

		if isinstance(other, type(self)):
			return self.key == other.key and self.modifiers == other.modifiers
		else:
			return NotImplemented

	def __hash__(self):

		return hash((self.key, self.modifiers))


class HotString(Event):
	"""A hotstring object.

	Hotstring objects are hashable and compare equal regardless of timestamps
	and the current trigger.

	Attributes:
		string (:class:`str`): The string that needs to be typed to trigger
			this hotstring.
		triggers (:class:`frozenset`): The trigger keys that need to be typed
			after the string. This frozenset may be empty.
		trigger (:class:`str`): The trigger that triggered this hotstring.
			May be :obj:`None`.
	"""

	def __init__(self, string, triggers, trigger=None):

		Event.__init__(self)
		self.string = string
		self.triggers = frozenset(triggers)
		self.trigger = trigger

	def __eq__(self, other):

		if isinstance(other, type(self)):
			return (
				self.string == other.string and self.triggers == other.triggers)
		else:
			return NotImplemented

	def __hash__(self):

		return hash((self.string, self.triggers))


class WindowEvent(Event):
	"""Event representing window creation, destruction and focus change.

	Attributes:
		window (:class:`~macpy.Window`): The window that was
			created/destroyed/focused.
		type (:class:`.WindowEventType`): The action that was taken on
			the window.
	"""

	def __init__(self, window, event_type):

		Event.__init__(self)
		self.window = window
		self.type = event_type
