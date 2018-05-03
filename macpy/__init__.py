#!/usr/bin/env python3

from six import with_metaclass
import sys
if sys.version_info >= (3, 6):
	from enum import Enum, auto
else:
	from aenum import Enum, auto
import time
from .version import __version__
from .key import Key, KeyState
from .event import PointerAxis, WindowEventType, WindowState, Event, WindowEvent
from .event import KeyboardEvent, HotKey, HotString
from .event import PointerEventMotion, PointerEventButton, PointerEventAxis
from .types.metawindow import MetaWindow
from .platform import PLATFORM, Platform
# ~ PLATFORM = Platform.WAYLAND
if PLATFORM is Platform.WINDOWS:
	from .interface.winkeyboard import WinKeyboard
	from .interface.winpointer import WinPointer
	from .interface.winwindow import WinWindow
elif PLATFORM is Platform.WAYLAND:
	from .interface.evkeyboard import EvKeyboard
	from .interface.evpointer import EvPointer
else:
	from .interface.xkeyboard import XKeyboard
	from .interface.xpointer import XPointer
	from .interface.xwindow import XWindow


__all__ = ('Key', 'KeyState', 'PointerAxis', 'WindowEventType', 'WindowState',
	'Event', 'WindowEvent', 'KeyboardEvent', 'HotKey', 'HotString',
	'PointerEventMotion', 'PointerEventButton', 'PointerEventAxis',
	'Keyboard', 'Pointer', 'Window', 'RecordType', 'record', 'replay')


class Keyboard(object):
	"""Keyboard interface object.

	Allows simulating keyboard input as well as reading data from connected
	physical keyboards.
	"""

	def __init__(self):

		if PLATFORM is Platform.WINDOWS:
			self._interface = WinKeyboard()
		elif PLATFORM is Platform.WAYLAND:
			self._interface = EvKeyboard()
		else:
			self._interface = XKeyboard()

	def close(self):
		"""Close opened resources and cleanly exit mainloop.

		Call this method when you are done with this object.
		"""

		self._interface.close()

	def get_key_state(self, key):
		"""Check whether the key is pressed or released.

		Args:
			key (~macpy.key.Key): The key to check.
		Returns:
			~macpy.key.KeyState: Current state of the key.
		"""

		return self._interface.get_key_state(key)

	def install_keyboard_hook(self, callback, grab=False):
		"""Installs a low level hook that sends all keyboard input to
		the callback.

		Callback must take a single event argument.

		For event definition see :class:`~macpy.event.KeyboardEvent`.

		Args:
			callback (Callable): A callable which receives events.
			grab (bool): If grab is :obj:`True` events are consumed and not
				passed through to other applications.
				Note:
					Even if grab is :obj:`True`, synthetic events are still
					allowed on Windows.

					Under wayland this option does nothing.
		"""

		self._interface.install_keyboard_hook(callback, grab=grab)

	def uninstall_keyboard_hook(self):
		"""Uninstall keyboard hook and stop hook's loop.

		You don't have to explicitly call this method, calling :meth:`close`
		automatically removes hook if it's installed.
		"""

		self._interface.uninstall_keyboard_hook()

	def init_hotkeys(self):
		"""Initialize hotkey loop.

		You need to call this method once before using any hotkey related
		methods.
		"""

		self._interface.init_hotkeys()

	def uninit_hotkeys(self):
		"""Deinitialize hotkey loop.

		You don't have to explicitly call this method, calling :meth:`close`
		automatically stop hotkey loop if it's started.
		"""

		self._interface.uninit_hotkeys()

	def register_hotkey(self, key, modifiers, callback):
		"""Register a key combination that once pressed triggers callback.

		Note:
			It is currently not possible to define hotkeys which trigger only
			with e.g. :attr:`~macpy.key.Key.KEY_LEFTSHIFT`. Left/right keys
			are automatically converted to generic modifier e.g.
			:attr:`~macpy.key.Key.KEY_SHIFT`.
		Args:
			key (~macpy.key.Key): The key which triggers callback.
			modifiers ([~macpy.key.Key, ....]): Iterable of modifier keys that
				also need to be pressed. Valid modifiers are
				:attr:`~macpy.key.Key.KEY_SHIFT`,
				:attr:`~macpy.key.Key.KEY_CTRL`, :attr:`~macpy.key.Key.KEY_ALT`
				and :attr:`~macpy.key.Key.KEY_META`.
			callback (Callable): Callable which will be called
				with :class:`~macpy.event.HotKey` object as a single argument.
		Returns:
			~macpy.event.HotKey: A hotkey object.
		"""

		return self._interface.register_hotkey(key, modifiers, callback)

	def unregister_hotkey(self, hotkey):
		"""Unegister a previously registered hotkey.

		Args:
			hotkey (~macpy.event.HotKey): A hotkey object as returned by e.g.
				:meth:`register_hotkey`.
		"""

		self._interface.unregister_hotkey(hotkey)

	def register_hotstring(self, string, triggers, callback):
		"""Register a string that once typed will trigger callback.

		If triggers are empty, the string will trigger as soon as it's typed.
		Otherwise it will only trigger if it's followed by one of the triggers.

		Keyboard hook needs to be installed for hotstrings to work. Otherwise
		this method raises :exc:`RuntimeError`.

		Args:
			string (str): The string that will trigger the callback.
			triggers ((str)): Iterable of characters that will be checked for
				after the string.
			callback (Callable): A callable that will be called
				with :class:`~macpy.event.HotString` as a single argument.
		Returns:
			~macpy.event.HotString: A hotstring object.
		Raises:
			RuntimeError
		"""

		return self._interface.register_hotstring(string, triggers, callback)

	def unregister_hotstring(self, hotstring):
		"""Unregister a previously registered hotstring.

		Args:
			hotstring (~macpy.event.HotString): A hotstring object as returned
				by e.g. :meth:`register_hotstring`.
		"""

		self._interface.unregister_hotstring(hotstring)

	def keypress(self, key, state=None):
		"""Simulate a key press/release event.

		Args:
			key (~macpy.key.Key): Key to simulate.
			state (~macpy.key.KeyState): The state to simulate. If state
				is :obj:`None` (default), both key press and release are
				simulated.
		"""

		self._interface.keypress(key, state)

	def type(self, string):
		"""Type a given string.

		Depending on underlying implementation and current platform this may
		be more efficient then using :meth:`keypress`.

		Args:
			string (str): String to type.
		"""

		self._interface.type(string)


class Pointer(object):
	"""Pointer interface object.

	Allows simulating pointer input as well as reading data from connected
	physical pointing devices.
	"""

	def __init__(self):

		if PLATFORM is Platform.WINDOWS:
			self._interface = WinPointer()
		elif PLATFORM is Platform.WAYLAND:
			self._interface = EvPointer()
		else:
			self._interface = XPointer()

	def close(self):
		"""Close opened resources and cleanly exit mainloop.

		Call this method when you are done with this object.
		"""

		self._interface.close()

	def install_pointer_hook(self, callback, grab=False):
		"""Installs a low level hook that sends all pointer events to
		the callback.

		Callback must take a single event argument.

		For event definitions see :class:`~macpy.event.PointerEventMotion`,
		:class:`~macpy.event.PointerEventButton`
		and :class:`~macpy.event.PointerEventAxis`.

		Args:
			callback (Callable): A callable which will receive pointer events.
			grab (bool): If grab is :obj:`True` events are consumed and not
				passed through to other applications.
				Note:
					Even if grab is :obj:`True`, synthetic events are still
					allowed on Windows.

					Under wayland this option does nothing.
		"""

		self._interface.install_pointer_hook(callback, grab=grab)

	def uninstall_pointer_hook(self):
		"""Uninstalls pointer hook and stops hook's loop.

		You don't have to explicitly call this method. Calling :meth:`close`
		will remove the hook automatically if it's installed.
		"""

		self._interface.uninstall_pointer_hook()

	def warp(self, x, y, relative=False):
		"""Warp pointer to the given location on screen.

		Pointer cannot be warped beyond the bounds of the virtual screen.

		Args:
			x (int): X coordinate.
			y (int): Y coordinate.
			relative (bool): Whether given coordinates are absolute or relative
				to current pointer position.
		"""

		self._interface.warp(x, y, relative)

	def scroll(self, axis, value):
		"""Simulate mouse scroll wheel along the given axis.

		Note:
			value is platform dependent, so the same value may result in
			different amount scrolled depending on current platform.
		Args:
			axis (~macpy.event.PointerAxis): The axis along which to scroll.
			value (int): The amount which to scroll. See Note.
		"""

		self._interface.scroll(axis, value)

	def click(self, key, state=None):
		"""Simulate a mouse click.

		Args:
			key (~macpy.key.Key): A button to click.
			state (~macpy.key.KeyState): The state to simulate. If state
				is :obj:`None` both button press and release are simulated.
		"""

		self._interface.click(key, state)

	def get_button_state(self, button):
		"""Check whether the button is pressed or released.

		Args:
			button (~macpy.key.Key): The button to check.
		Returns:
			~macpy.key.KeyState: Current state of the key.
		"""

		return self._interface.get_button_state(button)

	@property
	def position(self):
		"""Current position of the pointer on screen.

		Returns:
			tuple: A namedtuple where first member is the x coordinate and the
				second - y coordinate, in pixels.
		"""

		return self._interface.position


class Window(with_metaclass(MetaWindow)):
	"""Window interface object.

	Allows manipulating windows on supported platforms:
	activating, minimizing, closing, moving, etc.

	Rather than instanciating this class directly, use one of the class
	methods, e.g. :meth:`get_active`.

	Attributes:
		title (str): Visible window title. Might be :obj:`None` if window is
			already closed.
		wm_class (str): Window class. Might be :obj:`None` if window is
			already closed.
		pid (int): PID of the process to which this window belongs. Might be
			:obj:`None` if window is closed or if window does not set
			this property.
	"""

	if PLATFORM is Platform.WINDOWS:
		_interface = WinWindow
	elif PLATFORM is Platform.WAYLAND:
		_interface = None
	else:
		_interface = XWindow
	_callback = None

	def __init__(self, window):

		self._window = window
		self.wm_class = window.wm_class
		self.pid = window.pid

	@property
	def title(self):

		return self._window.title

	@classmethod
	def _redirect(cls, event):

		cls._callback(WindowEvent(cls(event.window), event.type))

	@classmethod
	def install_window_hook(cls, callback):
		"""Hook window creation, destruction and focus change.

		Callback is called with :class:`~macpy.event.WindowEvent` as a single
		argument.

		Args:
			callback (Callable): A callable to receive events.
		Raises:
			NotImplementedError
		"""

		if cls._interface:
			cls._callback = callback
			cls._interface.install_window_hook(cls._redirect)
		else:
			raise NotImplementedError('Unsupported platform')

	@classmethod
	def uninstall_window_hook(self):
		"""Remove window hook.

		Since hook runs in a separate thread, you should call this method
		once you are done for a clean exit.

		Raises:
			NotImplementedError
		"""

		if cls._interface:
			cls._interface.uninstall_window_hook()
		else:
			raise NotImplementedError('Unsupported platform')

	@classmethod
	def list_windows(cls):
		"""Return a tuple of currently open window objects.

		Returns:
			(.Window, ....): A tuple of currently open windows.
		Raises:
			NotImplementedError
		"""

		if cls._interface:
			return tuple(cls(window) for window in cls._interface.list_windows())
		else:
			raise NotImplementedError('Unsupported platform')

	@classmethod
	def get_active(cls):
		"""Return currently focused window.

		Returns:
			.Window: A window object.
		Raises:
			NotImplementedError
		"""

		if cls._interface:
			window = cls._interface.get_active()
			if window:
				return cls(window)
			else:
				return None
		else:
			raise NotImplementedError('Unsupported platform')

	@classmethod
	def get_under_pointer(cls):
		"""Return the window that is currently under pointer.

		Returns:
			.Window: A window object.
		Raises:
			NotImplementedError
		"""

		if cls._interface:
			window = cls._interface.get_under_pointer()
			if window:
				return cls(window)
			else:
				return None
		else:
			raise NotImplementedError('Unsupported platform')

	@classmethod
	def get_by_class(cls, wm_class):
		"""Return the first window whose :attr:`wm_class` matches wm_class.

		Args:
			wm_class (str): Window class to match.
		Returns:
			.Window: A window object.
		Raises:
			NotImplementedError
		"""

		if cls._interface:
			window = cls._interface.get_by_class(wm_class)
			if window:
				return cls(window)
			else:
				return None
		else:
			raise NotImplementedError('Unsupported platform')

	@classmethod
	def get_by_title(cls, title):
		"""Return the first window whose :attr:`title` matches title.

		Args:
			title (str): Partial window title to match.
		Returns:
			.Window: A window object.
		Raises:
			NotImplementedError
		"""

		if cls._interface:
			window = cls._interface.get_by_title(title)
			if window:
				return cls(window)
			else:
				return None
		else:
			raise NotImplementedError

	@property
	def state(self):
		"""This window's state.

		Returns:
			~macpy.event.WindowState: Window state.
		"""

		return self._window.state

	@property
	def position(self):
		"""This window's position on screen in pixels.

		Returns:
			(int, int): A namedtuple of x and y coordinates.
		"""

		return self._window.position

	@property
	def size(self):
		"""This window's size in pixels.

		Returns:
			(int, int): A namedtuple of width and height.
		"""

		return self._window.size

	def activate(self):
		"""Activate this window.
		"""

		self._window.activate()

	def restore(self):
		"""Restore this window.
		"""

		self._window.restore()

	def minimize(self):
		"""Minimize this window.
		"""

		self._window.minimize()

	def maximize(self):
		"""Maximize this window.
		"""

		self._window.maximize()

	def resize(self, width, height):
		"""Resize this window to the given width and height in pixels.

		Args:
			width (int): New width.
			height (int): New height.
		"""

		self._window.resize(width, height)

	def move(self, x, y):
		"""Move this window to the given screen x and y coordinates in pixels.

		Args:
			x (int): New position along x axis.
			y (int): New position along y axis.
		"""

		self._window.move(x, y)

	def close(self):
		"""Request this window to close.

		If there are unsaved data, the window may refuse to close.
		"""

		self._window.close()

	def force_close(self):
		"""Forcibly close this window.
		"""

		self._window.force_close()

	def send_event(self, event):
		"""Send an input event dirrectly to this window, regardless of whether
		it has input focus.

		Valid input events are :class:`~macpy.event.KeyboardEvent`,
		:class:`~macpy.event.PointerEventMotion`,
		:class:`~macpy.event.PointerEventButton` and
		:class:`~macpy.event.PointerEventAxis`.

		Note:
			For events that contain coordinates, these coordinates are always
			relative to this window.

		Args:
			event (~macpy.event.Event): Event to send.
		"""

		self._window.send_event(event)


class RecordType(Enum):
	"""An enumeration specifying which events to record.

	Attributes:
		KEYBOARD: Record keyboard events only.
		POINTER: Record pointer events only.
		BOTH: Record both keyboard and pointer events.
	"""

	KEYBOARD = auto()
	POINTER = auto()
	BOTH = auto()


def record(record_type, stop_key=None, timer=None):
	"""Record events of record_type and return a list.

	Args:
		record_type (RecordType): The type of events to record.
		stop_key (~macpy.key.Key): The key or button which will end the
			recording. If stop_key is :obj:`None` the recording will go on
			until timer runs out.
		timer (float): The duration of recording session. If timer is
			:obj:`None` the session will go on until specified key is pressed.
	Returns:
		[~macpy.event.Event]: A list of recorded events.
	"""

	def process_event(event):

		nonlocal stop
		if isinstance(event, KeyboardEvent):
			if event.key == stop_key:
				stop = True
				return
		elif isinstance(event, PointerEventButton):
			if event.button == stop_key:
				stop = True
				return
		event_list.append(event)

	event_list = []
	stop = False

	if not isinstance(record_type, RecordType):
		raise TypeError('Unsupported record type')
	if record_type is RecordType.KEYBOARD or record_type is RecordType.BOTH:
		keyboard = Keyboard()
		keyboard.install_keyboard_hook(process_event)
	if record_type is RecordType.POINTER or record_type is RecordType.BOTH:
		pointer = Pointer()
		pointer.install_pointer_hook(process_event)

	if timer is None:
		while not stop:
			time.sleep(0.005)
	else:
		time.sleep(timer)

	if record_type is RecordType.KEYBOARD or record_type is RecordType.BOTH:
		keyboard.close()
	if record_type is RecordType.POINTER or record_type is RecordType.BOTH:
		pointer.close()

	return event_list


def replay(event_list, delay=0):
	"""Replay events from a sequence.

	Args:
		event_list ([~macpy.event.Event]): A sequence of events.
		delay (float): The seconds to wait between each event (or pair).
	"""

	keyboard = Keyboard()
	pointer = Pointer()

	for event in event_list:
		if isinstance(event, KeyboardEvent):
			keyboard.keypress(event.key, event.state)
			if event.state is KeyState.RELEASED:
				time.sleep(delay)
		elif isinstance(event, PointerEventMotion):
			pointer.warp(event.position.x, event.position.y)
			time.sleep(delay)
		elif isinstance(event, PointerEventButton):
			pointer.click(event.button, event.state)
			if event.state is KeyState.RELEASED:
				time.sleep(delay)
		elif isinstance(event, PointerEventAxis):
			pointer.scroll(event.axis, event.value)
			time.sleep(delay)
		else:
			raise TypeError('Unsupported event')

	keyboard.close()
	pointer.close()
