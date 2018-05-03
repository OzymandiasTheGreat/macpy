#!/usr/bin/env python3

from __future__ import print_function
try:
	from queue import Queue
except ImportError:
	from Queue import Queue
from threading import Thread
import traceback
import atexit
from ctypes import WINFUNCTYPE, windll, wintypes, POINTER, byref, sizeof
from ctypes import c_int, c_void_p, c_short, c_bool, c_uint
from ..key import Key, KeyState
from ..event import PointerAxis
from ..event import PointerEventMotion, PointerEventButton, PointerEventAxis
from ..types.tuples import MousePos, Modifiers, MouseEvent
from ..types.structures import MSLLHOOKSTRUCT, INPUT, INPUTunion, MOUSEINPUT, Point
from ..constant.windows import WH_MOUSE_LL, PM_REMOVE, WHEEL_DELTA, MouseWM
from ..constant.windows import InputType, MOUSEEVENTF, SM_CXSCREEN, SM_CYSCREEN
from ..constant.windows import XBUTTON1, XBUTTON2, LLMHF_INJECTED


class WinPointer(object):

	windll.user32.GetKeyState.argtypes = (c_int, )
	windll.user32.GetKeyState.restype = c_short
	windll.user32.SendInput.argtypes = (c_uint, c_void_p, c_int)
	windll.user32.SendInput.restype = c_uint
	windll.user32.GetSystemMetrics.argtypes = (c_int, )
	windll.user32.GetSystemMetrics.restype = c_int
	windll.user32.GetCursorPos.argtypes = (POINTER(Point), )
	windll.user32.GetCursorPos.restype = c_bool
	windll.user32.GetAsyncKeyState.argtypes = (c_int, )
	windll.user32.GetAsyncKeyState.restype = c_short

	def __init__(self):

		self.queue = Queue()
		self.mainloop = Thread(target=self._mainloop, name='WinPointer mainloop')
		self.mainloop.start()
		self.hook = None

	def _mainloop(self):

		while True:
			method, args = self.queue.get()
			if method is None:
				break
			try:
				method(*args)
			except Exception as e:
				print(
					'Error in WinPointer mainloop: \n',
					''.join(traceback.format_exception(
						type(e), e, e.__traceback__)))
			self.queue.task_done()

	def enqueue(self, method, *args):

		self.queue.put_nowait((method, args))

	def install_pointer_hook(self, callback, grab=False):

		self.stop = False
		self.hook_callback = callback
		self.hook_grab = grab
		self.hook = Thread(target=self._hook, name='WinPointer hook loop')
		self.hook.start()

	def uninstall_pointer_hook(self):

		self.stop = True
		self.hook = None

	def close(self):

		self.enqueue(None)
		if self.hook and self.hook.is_alive():
			self.uninstall_pointer_hook()

	def _hook(self):

		def low_level_handler(nCode, wParam, lParam):

			msllhook = lParam.contents
			event = MouseEvent(
				wParam, msllhook.pt, msllhook.mouseData, msllhook.flags)
			self.enqueue(self.process_event, event)
			if not self.hook_grab or event.flags & LLMHF_INJECTED:
				return windll.user32.CallNextHookEx(hID, nCode, wParam, lParam)
			else:
				return True

		try:
			CMPFUNC = WINFUNCTYPE(c_int, c_int, c_int, POINTER(MSLLHOOKSTRUCT))
			hPointer = CMPFUNC(low_level_handler)
			windll.kernel32.GetModuleHandleW.restype = wintypes.HMODULE
			windll.kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR, )
			hID = windll.user32.SetWindowsHookExW(
				WH_MOUSE_LL, hPointer,
				windll.kernel32.GetModuleHandleW(None), 0)
			atexit.register(windll.user32.UnhookWindowsHookEx, hID)
			while not self.stop:
				wm_msg = windll.user32.PeekMessageW(
					None, None, 0, 0, PM_REMOVE)
		except Exception as e:
			print('Error in WinPointer hook loop: \n',
				''.join(traceback.format_exception(type(e), e, e.__traceback__)))
		finally:
			windll.user32.UnhookWindowsHookEx(hID)

	def process_event(self, event):

		if event.flags & LLMHF_INJECTED:
			return

		mods = {
			'SHIFT': False,
			'ALTGR': False,
			'CTRL': False,
			'ALT': False,
			'META': False}
		if (windll.user32.GetKeyState(Key.KEY_SHIFT.vk) >> 8):
			mods['SHIFT'] = True
		if ((windll.user32.GetKeyState(Key.KEY_RIGHTALT.vk) >> 8)
				and (windll.user32.GetKeyState(Key.KEY_LEFTCTRL.vk) >> 8)):
			mods['ALTGR'] = True
		if ((windll.user32.GetKeyState(Key.KEY_CTRL.vk) >> 8)
				and not mods['ALTGR']):
			mods['CTRL'] = True
		if ((windll.user32.GetKeyState(Key.KEY_ALT.vk) >> 8)
				and not mods['ALTGR']):
			mods['ALT'] = True
		if ((windll.user32.GetKeyState(Key.KEY_LEFTMETA.vk) >> 8)
				or (windll.user32.GetKeyState(Key.KEY_RIGHTMETA.vk) >> 8)):
			mods['META'] = True

		msg_type = MouseWM(event.message)
		fresh_point = Point()
		windll.user32.GetCursorPos(byref(fresh_point))
		if msg_type == MouseWM.WM_MOUSEMOVE:
			self.hook_callback(PointerEventMotion(
				fresh_point.x, fresh_point.y, mods))
		elif msg_type == MouseWM.WM_LBUTTONDOWN:
			self.hook_callback(PointerEventButton(
				fresh_point.x, fresh_point.y,
				Key.BTN_LEFT, KeyState.PRESSED, mods))
		elif msg_type == MouseWM.WM_LBUTTONUP:
			self.hook_callback(PointerEventButton(
				fresh_point.x, fresh_point.y,
				Key.BTN_LEFT, KeyState.RELEASED, mods))
		elif msg_type == MouseWM.WM_MBUTTONDOWN:
			self.hook_callback(PointerEventButton(
				fresh_point.x, fresh_point.y,
				Key.BTN_MIDDLE, KeyState.PRESSED, mods))
		elif msg_type == MouseWM.WM_MBUTTONUP:
			self.hook_callback(PointerEventButton(
				fresh_point.x, fresh_point.y,
				Key.BTN_MIDDLE, KeyState.RELEASED, mods))
		elif msg_type == MouseWM.WM_RBUTTONDOWN:
			self.hook_callback(PointerEventButton(
				fresh_point.x, fresh_point.y,
				Key.BTN_RIGHT, KeyState.PRESSED, mods))
		elif msg_type == MouseWM.WM_RBUTTONUP:
			self.hook_callback(PointerEventButton(
				fresh_point.x, fresh_point.y,
				Key.BTN_RIGHT, KeyState.RELEASED, mods))
		elif msg_type == MouseWM.WM_XBUTTONDOWN:
			if (event.data >> 16) & XBUTTON1:
				button = Key.BTN_SIDE
			else:
				button = Key.BTN_EXTRA
			self.hook_callback(PointerEventButton(
				fresh_point.x, fresh_point.y,
				button, KeyState.PRESSED, mods))
		elif msg_type == MouseWM.WM_XBUTTONUP:
			if (event.data >> 16) & XBUTTON1:
				button = Key.BTN_SIDE
			else:
				button = Key.BTN_EXTRA
			self.hook_callback(PointerEventButton(
				fresh_point.x, fresh_point.y,
				button, KeyState.RELEASED, mods))
		if msg_type == MouseWM.WM_MOUSEWHEEL:
			value = -((event.data >> 16) / WHEEL_DELTA)
			self.hook_callback(PointerEventAxis(
				fresh_point.x, fresh_point.y,
				value, PointerAxis.VERTICAL, mods))
		elif msg_type == MouseWM.WM_MOUSEHWHEEL:
			value = ((event.data >> 16) / WHEEL_DELTA)
			self.hook_callback(PointerEventAxis(
				fresh_point.x, fresh_point.y,
				value, PointerAxis.HORIZONTAL, mods))

	def send_input(self, *inputs):

		nInputs = len(inputs)
		LPINPUT = INPUT * nInputs
		pInputs = LPINPUT(*inputs)
		cbSize = sizeof(INPUT)
		windll.user32.SendInput(nInputs, pInputs, cbSize)

	def pack_input(self, dx, dy, data, flags):

		return INPUT(InputType.MOUSE, INPUTunion(
			mi=MOUSEINPUT(dx, dy, data, flags, 0, None)))

	def warp(self, x, y, relative=False):

		flags = MOUSEEVENTF.MOVE
		if relative:
			dx = x
			dy = y
		else:
			dx = x * round(65535 / windll.user32.GetSystemMetrics(SM_CXSCREEN))
			dy = y * round(65535 / windll.user32.GetSystemMetrics(SM_CYSCREEN))
			flags |= MOUSEEVENTF.ABSOLUTE
		self.enqueue(self.send_input, self.pack_input(dx, dy, 0, flags))

	def scroll(self, axis, value):

		if not isinstance(axis, PointerAxis):
			raise TypeError('Invalid axis type')
		if axis == PointerAxis.VERTICAL:
			value = -value
		data = WHEEL_DELTA * value
		flags = (MOUSEEVENTF.WHEEL if axis == PointerAxis.VERTICAL
			else MOUSEEVENTF.HWHEEL)
		self.enqueue(self.send_input, self.pack_input(0, 0, data, flags))

	def click(self, key, state=None):

		if state is None:
			if key == Key.BTN_LEFT:
				self.enqueue(self.send_input, self.pack_input(
					0, 0, 0, MOUSEEVENTF.LEFTDOWN))
				self.enqueue(self.send_input, self.pack_input(
					0, 0, 0, MOUSEEVENTF.LEFTUP))
			elif key == Key.BTN_MIDDLE:
				self.enqueue(self.send_input, self.pack_input(
					0, 0, 0, MOUSEEVENTF.MIDDLEDOWN))
				self.enqueue(self.send_input, self.pack_input(
					0, 0, 0, MOUSEEVENTF.MIDDLEUP))
			elif key == Key.BTN_RIGHT:
				self.enqueue(self.send_input, self.pack_input(
					0, 0, 0, MOUSEEVENTF.RIGHTDOWN))
				self.enqueue(self.send_input, self.pack_input(
					0, 0, 0, MOUSEEVENTF.RIGHTUP))
			elif key == Key.BTN_SIDE:
				self.enqueue(self.send_input, self.pack_input(
					0, 0, XBUTTON1, MOUSEEVENTF.XDOWN))
				self.enqueue(self.send_input, self.pack_input(
					0, 0, XBUTTON1, MOUSEEVENTF.XUP))
			elif key == Key.BTN_EXTRA:
				self.enqueue(self.send_input, self.pack_input(
					0, 0, XBUTTON2, MOUSEEVENTF.XDOWN))
				self.enqueue(self.send_input, self.pack_input(
					0, 0, XBUTTON2, MOUSEEVENTF.XUP))
			else:
				pass
		elif state == KeyState.PRESSED:
			if key == Key.BTN_LEFT:
				self.enqueue(self.send_input, self.pack_input(
					0, 0, 0, MOUSEEVENTF.LEFTDOWN))
			elif key == Key.BTN_MIDDLE:
				self.enqueue(self.send_input, self.pack_input(
					0, 0, 0, MOUSEEVENTF.MIDDLEDOWN))
			elif key == Key.BTN_RIGHT:
				self.enqueue(self.send_input, self.pack_input(
					0, 0, 0, MOUSEEVENTF.RIGHTDOWN))
			elif key == Key.BTN_SIDE:
				self.enqueue(self.send_input, self.pack_input(
					0, 0, XBUTTON1, MOUSEEVENTF.XDOWN))
			elif key == Key.BTN_EXTRA:
				self.enqueue(self.send_input, self.pack_input(
					0, 0, XBUTTON2, MOUSEEVENTF.XDOWN))
			else:
				pass
		elif state == KeyState.RELEASED:
			if key == Key.BTN_LEFT:
				self.enqueue(self.send_input, self.pack_input(
					0, 0, 0, MOUSEEVENTF.LEFTUP))
			elif key == Key.BTN_MIDDLE:
				self.enqueue(self.send_input, self.pack_input(
					0, 0, 0, MOUSEEVENTF.MIDDLEUP))
			elif key == Key.BTN_RIGHT:
				self.enqueue(self.send_input, self.pack_input(
					0, 0, 0, MOUSEEVENTF.RIGHTUP))
			elif key == Key.BTN_SIDE:
				self.enqueue(self.send_input, self.pack_input(
					0, 0, XBUTTON1, MOUSEEVENTF.XUP))
			elif key == Key.BTN_EXTRA:
				self.enqueue(self.send_input, self.pack_input(
					0, 0, XBUTTON2, MOUSEEVENTF.XUP))
			else:
				pass
		else:
			raise RuntimeError('Invalid state')

	def get_button_state(self, button):

		output = windll.user32.GetAsyncKeyState(button.vk)
		return KeyState(bool(output >> 8))

	@property
	def position(self):

		point = Point()
		windll.user32.GetCursorPos(byref(point))
		return MousePos(point.x, point.y)
