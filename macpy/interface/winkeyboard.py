from __future__ import print_function
import traceback
import time
import atexit
from threading import Thread
try:
	from queue import Queue, Empty
except ImportError:
	from Queue import Queue, Empty
from collections import deque
from ctypes import WINFUNCTYPE, windll, wintypes, byref, create_unicode_buffer
from ctypes import POINTER, sizeof
from ctypes import c_int, c_short, c_void_p, c_byte, c_uint, c_wchar, c_bool
from ..key import Key, KeyState, Modifiers
from ..constant.windows import WH_KEYBOARD_LL, PM_REMOVE, LLKHF_INJECTED, KeyWM
from ..constant.windows import MOD, WM_HOTKEY, KEYEVENTF, InputType
from ..types.structures import KBDLLHOOKSTRUCT, INPUT, INPUTunion, KEYBDINPUT
from ..types.tuples import KeyEvent
from ..event import KeyboardEvent, HotKey, HotString


class WinKeyboard(object):

	windll.user32.GetAsyncKeyState.argtypes = (c_int, )
	windll.user32.GetAsyncKeyState.restype = c_short
	windll.user32.GetForegroundWindow.argtypes = ()
	windll.user32.GetForegroundWindow.restype = c_void_p
	windll.user32.GetWindowThreadProcessId.argtypes = (c_void_p, POINTER(c_int))
	windll.user32.GetWindowThreadProcessId.restype = c_int
	windll.user32.GetKeyboardLayout.argtypes = (c_int, )
	windll.user32.GetKeyboardLayout.restype = c_void_p
	windll.user32.GetKeyState.argtypes = (c_int, )
	windll.user32.GetKeyState.restype = c_short
	windll.user32.ToUnicodeEx.argtypes = (
		c_uint, c_uint, POINTER(c_byte*256), c_wchar*4, c_int, c_uint, c_void_p)
	windll.user32.ToUnicodeEx.restype = c_int
	windll.user32.RegisterHotKey.argtypes = (c_void_p, c_int, c_uint, c_uint)
	windll.user32.RegisterHotKey.restype = c_bool
	windll.user32.UnregisterHotKey.argtypes = (c_void_p, c_int)
	windll.user32.UnregisterHotKey.restype = c_bool
	windll.user32.SendInput.argtypes = (c_uint, c_void_p, c_int)
	windll.user32.SendInput.restype = c_uint

	def __init__(self):

		self.queue = Queue()
		self.mainloop = Thread(
			target=self._mainloop, name='WinKeyboard mainloop')
		self.mainloop.start()
		self.hook = None
		self.hk_queue = Queue()
		self.hotkeys = None
		self.input = deque(maxlen=128)
		self.hotstrings = {}

	def _mainloop(self):

		while True:
			method, args = self.queue.get()
			if method is None:
				break
			try:
				method(*args)
			except Exception as e:
				print('Error in WinKeyboard mainloop: \n',
					''.join(
						traceback.format_exception(type(e), e, e.__traceback__)))
			self.queue.task_done()

	def enqueue(self, method, *args):

		self.queue.put_nowait((method, args))

	def close(self):

		self.enqueue(None)
		if self.hook and self.hook.is_alive():
			self.uninstall_keyboard_hook()
		if self.hotkeys and self.hotkeys.is_alive():
			self.uninit_hotkeys()

	def get_key_state(self, key):

		output = windll.user32.GetAsyncKeyState(key.vk)
		return KeyState(bool(output >> 8))

	def install_keyboard_hook(self, callback, grab=False):

		self.hook_stop = False
		self.hook_callback = callback
		self.hook_grab = grab
		self.hook = Thread(target=self._hook, name='WinKeyboard hook loop')
		self.hook.start()

	def uninstall_keyboard_hook(self):

		self.hook_stop = True

	def _hook(self):

		def low_level_handler(nCode, wParam, lParam):

			kbdllhook = lParam.contents
			event = KeyEvent(
				wParam, kbdllhook.vkCode, kbdllhook.scanCode, kbdllhook.flags)
			self.enqueue(self.process_event, event)
			if not self.hook_grab or event.flags & LLKHF_INJECTED:
				return windll.user32.CallNextHookEx(hID, nCode, wParam, lParam)
			else:
				return True

		try:
			CMPFUNC = WINFUNCTYPE(c_int, c_int, c_int, POINTER(KBDLLHOOKSTRUCT))
			hPointer = CMPFUNC(low_level_handler)
			windll.kernel32.GetModuleHandleW.restype = wintypes.HMODULE
			windll.kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR, )
			windll.user32.SetWindowsHookExW.argtypes = (c_int, wintypes.HANDLE, wintypes.HMODULE, wintypes.DWORD)
			hID = windll.user32.SetWindowsHookExW(
				WH_KEYBOARD_LL, hPointer,
				windll.kernel32.GetModuleHandleW(None), 0)
			atexit.register(windll.user32.UnhookWindowsHookEx, hID)
			while not self.hook_stop:
				wm_msg = windll.user32.PeekMessageW(
					None, None, 0, 0, PM_REMOVE)
				time.sleep(0.005)
		except Exception as e:
			print('Error in WinKeyboard hook loop: \n',
				''.join(traceback.format_exception(type(e), e, e.__traceback__)))
		finally:
			windll.user32.UnhookWindowsHookEx(hID)

	def process_event(self, event):

		if event.flags & LLKHF_INJECTED:
			return

		mods = {
			'SHIFT': False, 'ALTGR': False, 'CTRL': False, 'ALT': False,
			'META': False}
		locks = {'NUMLOCK': False, 'CAPSLOCK': False, 'SCROLLLOCK': False}
		hwnd = windll.user32.GetForegroundWindow()
		threadID = windll.user32.GetWindowThreadProcessId(hwnd, None)
		HKL = windll.user32.GetKeyboardLayout(threadID)
		lpKeyState = (c_byte * 256)()
		leftctrl = windll.user32.GetKeyState(Key.KEY_LEFTCTRL.vk)
		rightalt = windll.user32.GetKeyState(Key.KEY_RIGHTALT.vk)
		if leftctrl and rightalt:
			mods['ALTGR'] = True
			lpKeyState[Key.KEY_LEFTCTRL.vk] = leftctrl
			lpKeyState[Key.KEY_RIGHTALT.vk] = rightalt
		for mod in mods:
			Mod = getattr(Modifiers, mod, None)
			if Mod:
				if mod in {'CTRL', 'ALT'}:
					vk = Mod[0].vk
					state = windll.user32.GetKeyState(vk)
					lpKeyState[vk] = state
					if bool((state >> 8) & 128):
						mods[mod] = True
				else:
					vk = Mod[0].vk
					state = windll.user32.GetKeyState(vk)
					lpKeyState[vk] = state
					if bool((state >> 8) & 128):
						mods[mod] = True
		numlock = windll.user32.GetKeyState(Key.KEY_NUMLOCK.vk)
		lpKeyState[Key.KEY_NUMLOCK.vk] = numlock
		if numlock & 1:
			locks['NUMLOCK'] = True
		capslock = windll.user32.GetKeyState(Key.KEY_CAPSLOCK.vk)
		lpKeyState[Key.KEY_CAPSLOCK.vk] = capslock
		if capslock & 1:
			locks['CAPSLOCK'] = True
		scrolllock = windll.user32.GetKeyState(Key.KEY_SCROLLLOCK.vk)
		lpKeyState[Key.KEY_SCROLLLOCK.vk] = scrolllock
		if scrolllock & 1:
			locks['SCROLLLOCK'] = True
		wchar = create_unicode_buffer(4)
		nchar = windll.user32.ToUnicodeEx(
			event.vk, event.scancode, byref(lpKeyState), wchar, 4, 0, HKL)
		if nchar > 0:
			char = wchar.value
		else:
			char = None
		keystate = (KeyState.PRESSED
			if KeyWM(event.message) in {KeyWM.WM_KEYDOWN, KeyWM.WM_SYSKEYDOWN}
			else KeyState.RELEASED)
		self.enqueue(self.hook_callback, KeyboardEvent(
			Key.from_vk(event.vk), keystate, char, mods, locks))

		if keystate == KeyState.PRESSED and self.hotstrings and char:
			self.input.append(char)
			string = ''.join(self.input)
			for hotstring in self.hotstrings:
				if (string.endswith(hotstring.string)
						and not hotstring.triggers):
					retstring = HotString(
						hotstring.string, hotstring.triggers)
					self.enqueue(self.hotstrings[hotstring], retstring)
					self.input.clear()
				elif (string[:-1].endswith(hotstring.string)
						and string[-1] in hotstring.triggers):
					retstring = HotString(
						hotstring.string, hotstring.triggers, string[-1])
					self.enqueue(self.hotstrings[hotstring], retstring)
					self.input.clear()

	def init_hotkeys(self):

		self.hotkeys = Thread(
			target=self._hotkeys, name='WinKeyboard hotkey loop')
		self.hk_ids = {}
		self.hk_callbacks = {}
		self.hotkeys.start()

	def hk_enqueue(self, register, hotkey, callback):

		self.hk_queue.put_nowait((register, hotkey, callback))

	def uninit_hotkeys(self):

		if self.hotkeys and self.hotkeys.is_alive():
			self.hk_enqueue(None, None, None)

	def _hotkeys(self):

		try:
			while True:
				try:
					register, hotkey, callback = self.hk_queue.get_nowait()
					if register is None and hotkey is None and callback is None:
						break
					elif register:
						self._register_hotkey(hotkey, callback)
					else:
						self._unregister_hotkey(hotkey)
				except Empty:
					pass
				wm_msg = wintypes.MSG()
				if windll.user32.PeekMessageW(
					byref(wm_msg), None, 0, 0, PM_REMOVE):
						if wm_msg.message == WM_HOTKEY:
							try:
								hotkey = self.hk_ids[wm_msg.wParam]
								ret = HotKey(hotkey.key, hotkey.modifiers)
								self.enqueue(self.hk_callbacks[hotkey], ret)
							except KeyError:
								pass
				time.sleep(0.3)
		finally:
			for hotkey in tuple(self.hk_callbacks.keys()):
				self._unregister_hotkey(hotkey)

	def _register_hotkey(self, hotkey, callback):

		try:
			id_ = max(self.hk_ids) + 1
		except ValueError:
			id_ = 1
		mods = 0
		for modkey in hotkey.modifiers:
			for Mod in Modifiers:
				if modkey in Mod:
					mods |= getattr(MOD, Mod.name)
		if windll.user32.RegisterHotKey(None, id_, mods, hotkey.key.vk):
			self.hk_ids[id_] = hotkey
			self.hk_callbacks[hotkey] = callback

	def register_hotkey(self, key, modifiers, callback):

		mods = set()
		for mod in modifiers:
			for Mod in Modifiers:
				if mod in Mod:
					mods.add(Mod[0])
		hotkey = HotKey(key, mods)
		self.hk_enqueue(True, hotkey, callback)
		return hotkey

	def _unregister_hotkey(self, hotkey):

		try:
			id_ = next(k for k, v in self.hk_ids.items() if v == hotkey)
			windll.user32.UnregisterHotKey(None, id_)
			del self.hk_ids[id_]
			del self.hk_callbacks[hotkey]
		except StopIteration:
			pass

	def unregister_hotkey(self, hotkey):

		self.hk_enqueue(False, hotkey, None)

	def register_hotstring(self, string, triggers, callback):

		if self.hook and self.hook.is_alive():
			hotstring = HotString(string, triggers)
			self.hotstrings[hotstring] = callback
			return hotstring
		else:
			raise RuntimeError('Keyboard hook not installed')

	def unregister_hotstring(self, hotstring):

		if hotstring in self.hotstrings:
			del self.hotstrings[hotstring]

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

	def keypress(self, key, state=None):

		if state is None:
			self.enqueue(self.send_input, self.pack_input(key.vk, 0))
			self.enqueue(
				self.send_input, self.pack_input(key.vk, KEYEVENTF.KEYUP))
		elif state == KeyState.PRESSED:
			self.enqueue(self.send_input, self.pack_input(key.vk, 0))
		elif state == KeyState.RELEASED:
			self.enqueue(
				self.send_input, self.pack_input(key.vk, KEYEVENTF.KEYUP))
		else:
			raise TypeError('Invalid state')

	def _type(self, string):

		flags = KEYEVENTF.UNICODE
		for char in string:
			self.send_input(self.pack_input(ord(char), flags))
			self.send_input(self.pack_input(ord(char), flags | KEYEVENTF.KEYUP))

	def type(self, string):

		self.enqueue(self._type, string)
