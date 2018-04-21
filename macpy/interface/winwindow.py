import time
from threading import Thread
from ctypes import windll, create_unicode_buffer, POINTER, byref, wstring_at
from ctypes import WINFUNCTYPE, sizeof
from ctypes import c_void_p, c_wchar, c_uint, c_int, c_long, c_bool
from six import with_metaclass
from ..types.metawindow import MetaWindow
from ..constant.windows import OBJID_WINDOW, EVENT, WINEVENT, PM_REMOVE, GA, SW
from ..constant.windows import WM_CLOSE
from ..event import WindowEvent, WindowEventType as WinEType, WindowState
from ..types.structures import Point, WINDOWPLACEMENT, RECT
from ..types.tuples import WinPos, WinSize


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
