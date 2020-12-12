import time
from threading import Thread
from ctypes import windll, create_unicode_buffer, POINTER, byref, wstring_at
from ctypes import WINFUNCTYPE, sizeof
from ctypes import c_void_p, c_wchar, c_uint, c_int, c_long, c_bool
from six import with_metaclass
from ..types.metawindow import MetaWindow
from ..constant.windows import OBJID_WINDOW, EVENT, WINEVENT, PM_REMOVE, GA, SW
from ..constant.windows import WM_CLOSE, MK, MouseWM, KeyWM, WHEEL_DELTA
from ..constant.windows import KEYEVENTF, InputType
from ..event import WindowEvent, WindowEventType as WinEType, WindowState
from ..event import PointerEventMotion, PointerEventButton, PointerEventAxis
from ..event import KeyboardEvent, PointerAxis
from ..types.structures import Point, WINDOWPLACEMENT, RECT, INPUT, INPUTunion
from ..types.structures import KEYBDINPUT
from ..types.tuples import WinPos, WinSize
from ..key import Key, KeyState, Modifiers


class WinWindow(with_metaclass(MetaWindow)):

	hook = None

	windll.user32.RealGetWindowClassW.argtypes = (
		c_void_p, POINTER(c_wchar*2048), c_uint)
	windll.user32.RealGetWindowClassW.restype = c_uint
	windll.user32.GetWindowThreadProcessId.argtypes = (c_void_p, POINTER(c_uint))
	windll.user32.GetWindowThreadProcessId.restype = c_uint
	windll.user32.GetWindowTextLengthW.argtypes = (c_void_p, )
	windll.user32.GetWindowTextLengthW.restype = c_int
	windll.user32.GetWindowTextW.restype = c_int
	windll.user32.PeekMessageW.argtypes = (
		c_void_p, c_void_p, c_uint, c_uint, c_uint)
	windll.user32.PeekMessageW.restype = c_bool
	windll.user32.GetForegroundWindow.argtypes = ()
	windll.user32.GetForegroundWindow.restype = c_void_p
	windll.user32.GetCursorPos.argtypes = (POINTER(Point), )
	windll.user32.GetCursorPos.restype = c_bool
	windll.user32.WindowFromPoint.argtypes = (Point, )
	windll.user32.WindowFromPoint.restype = c_void_p
	windll.user32.GetAncestor.argtypes = (c_void_p, c_uint)
	windll.user32.GetAncestor.restype = c_void_p
	windll.user32.FindWindowW.argtypes = (c_void_p, c_void_p)
	windll.user32.FindWindowW.restype = c_void_p
	windll.user32.GetWindowPlacement.argtypes = (
		c_void_p, POINTER(WINDOWPLACEMENT))
	windll.user32.GetWindowPlacement.restype = c_bool
	windll.user32.GetWindowRect.argtypes = (c_void_p, POINTER(RECT))
	windll.user32.GetWindowRect.restype = c_bool
	windll.user32.SetForegroundWindow.argtypes = (c_void_p, )
	windll.user32.SetForegroundWindow.restype = c_bool
	windll.user32.SetWindowPlacement.argtypes = (
		c_void_p, POINTER(WINDOWPLACEMENT))
	windll.user32.SetWindowPlacement.restype = c_bool
	windll.user32.MoveWindow.argtypes = (
		c_void_p, c_int, c_int, c_int, c_int, c_bool)
	windll.user32.MoveWindow.restype = c_bool
	windll.user32.PostMessageW.argtypes = (
		c_void_p, c_uint, POINTER(c_uint), POINTER(c_long))
	windll.user32.PostMessageW.restype = c_bool
	windll.user32.EndTask.argtypes = (c_void_p, c_bool, c_bool)
	windll.user32.EndTask.restype = c_bool
	windll.user32.PostMessageW.argtypes = (c_void_p, c_uint, c_int, c_long)
	windll.user32.PostMessageW.restype = c_bool
	windll.user32.SendInput.argtypes = (c_uint, c_void_p, c_int)
	windll.user32.SendInput.restype = c_uint
	windll.user32.ChildWindowFromPoint.argtypes = (c_void_p, Point)
	windll.user32.ChildWindowFromPoint.restype = c_void_p

	def __init__(self, hwnd):

		self.hwnd = hwnd
		wm_class = create_unicode_buffer(2048)
		windll.user32.RealGetWindowClassW(hwnd, byref(wm_class), 2048)
		self.wm_class = wstring_at(wm_class)
		pid = c_uint(0)
		windll.user32.GetWindowThreadProcessId(hwnd, byref(pid))
		self.pid = pid.value

	def __hash__(self):

		return hash(self.hwnd)

	@property
	def title(self):

		length = windll.user32.GetWindowTextLengthW(self.hwnd) + 1
		title = create_unicode_buffer(length)
		windll.user32.GetWindowTextW(self.hwnd, title, length)
		return wstring_at(title)

	@classmethod
	def install_window_hook(cls, callback):

		cls.hook_callback = callback
		cls.stop = False
		cls.hook = Thread(target=cls._hook, name='WinWindow hook loop')
		cls.hook.start()

	@classmethod
	def uninstall_window_hook(cls):

		if cls.hook and cls.hook.is_alive():
			cls.stop = True

	@classmethod
	def _hook(cls):

		def WinEventProc(hWEH, event, hwnd, idObject, idChild, thread, time):

			if idObject == OBJID_WINDOW:
				if event == EVENT.OBJECT_CREATE:
					cls.hook_callback(WindowEvent(cls(hwnd), WinEType.CREATED))
				elif event == EVENT.OBJECT_DESTROY:
					cls.hook_callback(WindowEvent(cls(hwnd), WinEType.DESTROYED))
				elif event == EVENT.SYSTEM_FOREGROUND:
					cls.hook_callback(WindowEvent(cls(hwnd), WinEType.FOCUSED))

		try:
			CMPFUNC = WINFUNCTYPE(
				None,
				c_void_p, c_uint, c_void_p, c_long, c_long, c_uint, c_uint)
			hPointer = CMPFUNC(WinEventProc)
			hWEH1 = windll.user32.SetWinEventHook(
				EVENT.OBJECT_CREATE, EVENT.OBJECT_DESTROY, 0, hPointer, 0, 0,
				WINEVENT.OUTOFCONTEXT | WINEVENT.SKIPOWNPROCESS)
			hWEH2 = windll.user32.SetWinEventHook(
				EVENT.SYSTEM_FOREGROUND, EVENT.SYSTEM_FOREGROUND, 0, hPointer,
				0, 0, WINEVENT.OUTOFCONTEXT | WINEVENT.SKIPOWNPROCESS)
			while not cls.stop:
				windll.user32.PeekMessageW(None, None, 0, 0, PM_REMOVE)
				time.sleep(0.005)
		finally:
			windll.user32.UnhookWinEvent(hWEH1)
			windll.user32.UnhookWinEvent(hWEH2)

	@classmethod
	def list_windows(cls):

		def EnumWindowsProc(hwnd, lParam):

			window_list.append(cls(hwnd))
			return True

		window_list = []
		CMPFUNC = WINFUNCTYPE(c_bool, c_void_p, c_void_p)
		hPointer = CMPFUNC(EnumWindowsProc)
		if windll.user32.EnumWindows(hPointer, None):
			return tuple(window_list)
		return ()

	@classmethod
	def get_active(cls):

		hwnd = windll.user32.GetForegroundWindow()
		if hwnd:
			return cls(hwnd)
		return None

	@classmethod
	def get_under_pointer(cls):

		point = Point()
		if windll.user32.GetCursorPos(byref(point)):
			hwnd = windll.user32.WindowFromPoint(point)
			hwnd = windll.user32.GetAncestor(hwnd, GA.ROOTOWNER)
			return cls(hwnd)
		return None

	@classmethod
	def get_by_class(cls, wm_class):

		buffer = create_unicode_buffer(len(wm_class))
		buffer.value = wm_class
		hwnd = windll.user32.FindWindowW(buffer, None)
		if hwnd:
			return cls(hwnd)
		return None

	@classmethod
	def get_by_title(cls, title):

		for window in cls.list_windows():
			if title in window.title:
				return window
		return None

	@property
	def state(self):

		wp = WINDOWPLACEMENT()
		wp.length = sizeof(wp)
		if windll.user32.GetWindowPlacement(self.hwnd, byref(wp)):
			if wp.showCmd in {SW.MAXIMIZE, SW.SHOWMAXIMIZED}:
				return WindowState.MAXIMIZED
			elif (wp.showCmd
					in {SW.HIDE, SW.MINIMIZE, SW.SHOWMINIMIZED,
						SW.SHOWMINNOACTIVE}):
				return WindowState.MINIMIZED
			elif (wp.showCmd
					in {SW.RESTORE, SW.SHOW, SW.SHOWNA, SW.SHOWNOACTIVATE,
						SW.SHOWNORMAL}):
				return WindowState.NORMAL
		return None

	@property
	def position(self):

		rect = RECT()
		if windll.user32.GetWindowRect(self.hwnd, byref(rect)):
			return WinPos(rect.left, rect.top)
		return None

	@property
	def size(self):

		rect = RECT()
		if windll.user32.GetWindowRect(self.hwnd, byref(rect)):
			return WinSize(rect.right - rect.left, rect.bottom - rect.top)
		return None

	def activate(self):

		windll.user32.SetForegroundWindow(self.hwnd)

	def set_placement(self, placement):

		wp = WINDOWPLACEMENT()
		wp.length = sizeof(wp)
		if windll.user32.GetWindowPlacement(self.hwnd, byref(wp)):
			wp.showCmd = placement
			wp.length = sizeof(wp)
			windll.user32.SetWindowPlacement(self.hwnd, byref(wp))

	def restore(self):

		self.set_placement(SW.RESTORE)

	def minimize(self):

		self.set_placement(SW.MINIMIZE)

	def maximize(self):

		self.set_placement(SW.MAXIMIZE)

	def resize(self, width, height):

		rect = RECT()
		if windll.user32.GetWindowRect(self.hwnd, byref(rect)):
			windll.user32.MoveWindow(
				self.hwnd, rect.left, rect.top, width, height, True)

	def move(self, x, y):

		rect = RECT()
		if windll.user32.GetWindowRect(self.hwnd, byref(rect)):
			nWidth = rect.right - rect.left
			nHeight = rect.bottom - rect.top
			windll.user32.MoveWindow(self.hwnd, x, y, nWidth, nHeight, True)

	def close(self):

		windll.user32.PostMessageW(
			self.hwnd, WM_CLOSE, byref(c_uint(0)), byref(c_long(0)))

	def force_close(self):

		windll.user32.EndTask(self.hwnd, False, True)

	def send_input(self, *inputs):

		nInputs = len(inputs)
		LPINPUT = INPUT * nInputs
		pInputs = LPINPUT(*inputs)
		cbSize = sizeof(INPUT)
		windll.user32.SendInput(nInputs, pInputs, cbSize)

	def pack_input(self, keycode, flags):

		wScan = keycode
		if flags & KEYEVENTF.UNICODE:
			wVk = 0
		else:
			wVk = keycode
		return INPUT(InputType.KEYBOARD, INPUTunion(
				ki=KEYBDINPUT(wVk, wScan, flags, 0, None)))

	def send_event(self, event):

		mods = event.modifiers._asdict()
		if hasattr(event, 'state'):
			if event.state is KeyState.PRESSED:
				for mod, active in mods.items():
					if active:
						if mod == 'ALTGR':
							self.send_input(self.pack_input(
								Key.KEY_RIGHTALT.vk, 0))
							self.send_input(self.pack_input(
								Key.KEY_LEFTCTRL.vk, 0))
						else:
							self.send_input(self.pack_input(
								getattr(Modifiers, mod)[0].vk, 0))
				if isinstance(event, KeyboardEvent):
					self.send_key(event.key, event.state, event.modifiers.ALT)
				elif isinstance(event, PointerEventButton):
					flags = 0
					if event.modifiers.SHIFT:
						flags |= MK.SHIFT
					if event.modifiers.CTRL:
						flags |= MK.CONTROL
					self.send_button(
						event.position, event.button, event.state, flags)
				else:
					raise TypeError('Unsupported event type')
			elif event.state is KeyState.RELEASED:
				if isinstance(event, KeyboardEvent):
					self.send_key(event.key, event.state, event.modifiers.ALT)
				elif isinstance(event, PointerEventButton):
					flags = 0
					if event.modifiers.SHIFT:
						flags |= MK.SHIFT
					if event.modifiers.CTRL:
						flags |= MK.CONTROL
					self.send_button(
						event.position, event.button, event.state, flags)
				else:
					raise TypeError('Unsupported event type')
				for mod, active in mods.items():
					if active:
						if mod == 'ALTGR':
							self.send_input(self.pack_input(
								Key.KEY_LEFTCTRL.vk, KEYEVENTF.KEYUP))
							self.send_input(self.pack_input(
								Key.KEY_RIGHTALT.vk, KEYEVENTF.KEYUP))
						else:
							self.send_input(self.pack_input(
								getattr(Modifiers, mod)[0].vk, KEYEVENTF.KEYUP))
			else:
				raise TypeError('Unsupported state')
		else:
			flags = 0
			if event.modifiers.SHIFT:
				flags |= MK.SHIFT
			if event.modifiers.CTRL:
				flags |= MK.CONTROL
			for mod, active in mods.items():
				if active:
					if mod == 'ALTGR':
						self.send_input(self.pack_input(Key.KEY_RIGHTALT.vk, 0))
						self.send_input(self.pack_input(Key.KEY_LEFTCTRL.vk, 0))
					else:
						self.send_input(self.pack_input(
							getattr(Modifiers, mod)[0].vk, 0))
			if isinstance(event, PointerEventMotion):
				self.send_motion(event.position, flags)
			elif isinstance(event, PointerEventAxis):
				self.send_axis(event.position, event.value, event.axis, flags)
			else:
				raise TypeError('Unsupported event type')
			for mod, active in mods.items():
				if active:
					if mod == 'ALTGR':
						self.send_input(self.pack_input(
							Key.KEY_LEFTCTRL.vk, KEYEVENTF.KEYUP))
						self.send_input(self.pack_input(
							Key.KEY_RIGHTALT.vk, KEYEVENTF.KEYUP))
					else:
						self.send_input(self.pack_input(
							getattr(Modifiers, mod)[0].vk, KEYEVENTF.KEYUP))

	def send_key(self, key, state, alt):

		wParam = key.vk
		if alt:
			if state is KeyState.PRESSED:
				lParam = 0 | 1 << 29
				windll.user32.PostMessageW(
					self.hwnd, KeyWM.WM_SYSKEYDOWN, wParam, lParam)
			else:
				lParam = 1 | 1 << 29 | 1 << 30 | 1 << 31
				windll.user32.PostMessageW(
					self.hwnd, KeyWM.WM_SYSKEYUP, wParam, lParam)
		else:
			if state is KeyState.PRESSED:
				lParam = 0
				windll.user32.PostMessageW(
					self.hwnd, KeyWM.WM_KEYDOWN, wParam, lParam)
			else:
				lParam = 1 | 1 << 30 | 1 << 31
				windll.user32.PostMessageW(
					self.hwnd, KeyWM.WM_KEYUP, wParam, lParam)

	def send_button(self, position, button, state, flags):

		wParam = 0 | flags
		lParam = position.x | position.y << 16
		if button is Key.BTN_LEFT:
			if state is KeyState.PRESSED:
				windll.user32.PostMessageW(
					self.hwnd, MouseWM.WM_LBUTTONDOWN,
					wParam | MK.LBUTTON, lParam)
			else:
				windll.user32.PostMessageW(
					self.hwnd, MouseWM.WM_LBUTTONUP,
					wParam | MK.LBUTTON, lParam)
		elif button is Key.BTN_MIDDLE:
			if state is KeyState.PRESSED:
				windll.user32.PostMessageW(
					self.hwnd, MouseWM.WM_MBUTTONDOWN,
					wParam | MK.MBUTTON, lParam)
			else:
				windll.user32.PostMessageW(
					self.hwnd, MouseWM.WM_MBUTTONUP,
					wParam | MK.MBUTTON, lParam)
		elif button is Key.BTN_RIGHT:
			if state is KeyState.PRESSED:
				windll.user32.PostMessageW(
					self.hwnd, MouseWM.WM_RBUTTONDOWN,
					wParam | MK.RBUTTON, lParam)
			else:
				windll.user32.PostMessageW(
					self.hwnd, MouseWM.WM_RBUTTONUP,
					wParam | MK.RBUTTON, lParam)
		elif button is Key.BTN_SIDE:
			if state is KeyState.PRESSED:
				windll.user32.PostMessageW(
					self.hwnd, MouseWM.WM_XBUTTONDOWN,
					wParam | MK.XBUTTON1, lParam)
			else:
				windll.user32.PostMessageW(
					self.hwnd, MouseWM.WM_XBUTTONUP,
					wParam | MK.XBUTTON1, lParam)
		elif button is Key.BTN_EXTRA:
			if state is KeyState.PRESSED:
				windll.user32.PostMessageW(
					self.hwnd, MouseWM.WM_XBUTTONDOWN,
					wParam | MK.XBUTTON2, lParam)
			else:
				windll.user32.PostMessageW(
					self.hwnd, MouseWM.WM_XBUTTONUP,
					wParam | MK.XBUTTON2, lParam)
		else:
			raise ValueError('Unsupported button for this platform')

	def send_motion(self, position, flags):

		wParam = 0 | flags
		lParam = position.x | position.y << 16
		windll.user32.PostMessageW(
			self.hwnd, MouseWM.WM_MOUSEMOVE, wParam, lParam)

	def send_axis(self, position, value, axis, flags):

		wParam = 0 | flags | (value * WHEEL_DELTA) << 16
		lParam = (self.position.x + position.x
			| (self.position.y + position.y) << 16)
		control = windll.user32.ChildWindowFromPoint(
			self.hwnd, Point(position.x, position.y))
		if axis is PointerAxis.VERTICAL:
			windll.user32.PostMessageW(
				control, MouseWM.WM_MOUSEWHEEL, -wParam, lParam)
		elif axis is PointerAxis.HORIZONTAL:
			windll.user32.PostMessageW(
				self.hwnd, MouseWM.WM_MOUSEHWHEEL, wParam, lParam)
		else:
			raise TypeError('Unsupported axis type')
