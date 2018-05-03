#!/usr/bin/env python3

from __future__ import print_function
try:
	from queue import Queue
except ImportError:
	from Queue import Queue
from threading import Thread, enumerate as thread_enum
import traceback
from Xlib import display, X
from evdev import InputDevice, list_devices, ecodes, UInput
from libinput import LibInput, ContextType, EventType, ButtonState
from libinput import PointerAxis as LIPAxis, PointerAxisSource
from ..key import Key, KeyState, Modifiers as Mods
from ..event import PointerAxis as mPAxis
from ..event import PointerEventMotion, PointerEventButton, PointerEventAxis
from ..types.tuples import MousePos


class EvPointer(object):

	def __init__(self):

		self.xdisplay = display.Display()
		screen = self.xdisplay.screen()
		self.screen_width = screen.width_in_pixels
		self.screen_height = screen.height_in_pixels
		self.xroot = screen.root
		pointer = self.xroot.query_pointer()

		self.position = MousePos(pointer.root_x, pointer.root_y)

		devices = [InputDevice(fn) for fn in list_devices()]
		self.pointer_devs = []
		self.keyboard_devs = []
		for device in devices:
			caps = device.capabilities()
			if ecodes.EV_REL in caps:
				self.pointer_devs.append(device)
			elif ecodes.EV_ABS in caps:
				self.pointer_devs.append(device)
			elif ecodes.EV_KEY in caps:
				self.keyboard_devs.append(device)

		self.queue = Queue()
		self.mainloop = Thread(target=self._mainloop, name='EvPointer mainloop')
		self.mainloop.start()
		self.stop = False
		self.hook_callback = None
		self.hook = Thread(target=self._hook, name='EvPointer hook loop')
		self.hook.start()

		caps = {
			ecodes.EV_REL: (
				ecodes.REL_X, ecodes.REL_Y, ecodes.REL_WHEEL, ecodes.REL_HWHEEL),
			ecodes.EV_KEY: (
				ecodes.BTN_LEFT, ecodes.BTN_RIGHT, ecodes.BTN_MIDDLE,
				ecodes.BTN_SIDE, ecodes.BTN_EXTRA)}
		self.uinput = UInput(caps, name='macpy pointer')

	def close(self):

		self.uinput.close()
		self.enqueue(None)
		if self.hook and self.hook.is_alive():
			self.stop = True

	def _hook(self):

		li = LibInput(ContextType.PATH)
		for device in self.pointer_devs:
			li.add_device(device.fn)

		for event in li.events:
			if self.stop:
				break

			mods = {
				'SHIFT': False,
				'ALTGR': False,
				'CTRL': False,
				'ALT': False,
				'META': False}
			active_mods = set()
			for device in self.keyboard_devs:
				active_mods |= set(device.active_keys())
			for key in active_mods:
				key = Key.from_ec(key)
				if key in Mods.SHIFT:
					mods['SHIFT'] = True
				elif key in Mods.CTRL:
					mods['CTRL'] = True
				elif key in Mods.ALT:
					mods['ALT'] = True
				elif key in Mods.META:
					mods['META'] = True

			if event.type == EventType.POINTER_MOTION:
				dx, dy = event.delta
				x = self.position.x + round(dx)
				y = self.position.y + round(dy)
				if x < 0:
					x = 0
				elif x > (self.screen_width - 1):
					x = self.screen_width - 1
				if y < 0:
					y = 0
				elif y > (self.screen_height - 1):
					y = self.screen_height - 1
				self.position = MousePos(x, y)
				if self.hook_callback:
					self.enqueue(self.hook_callback, PointerEventMotion(
						self.position.x, self.position.y, mods))
			elif event.type == EventType.POINTER_MOTION_ABSOLUTE:
				x, y = event.transform_absolute_coords(
					self.screen_width, self.screen_height)
				self.position = MousePos(round(x), round(y))
				if self.hook_callback:
					self.enqueue(self.hook_callback, PointerEventMotion(
						self.position.x, self.position.y, mods))
			elif event.type == EventType.POINTER_BUTTON:
				button = Key.from_ec(event.button)
				state = KeyState(event.button_state.value)
				if self.hook_callback:
					self.enqueue(self.hook_callback, PointerEventButton(
						self.position.x, self.position.y, button, state, mods))
			elif event.type == EventType.POINTER_AXIS:
				if event.has_axis(LIPAxis.SCROLL_VERTICAL):
					axis = mPAxis.VERTICAL
					value = event.get_axis_value(LIPAxis.SCROLL_VERTICAL)
				else:
					axis = mPAxis.HORIZONTAL
					value = event.get_axis_value(LIPAxis.SCROLL_HORIZONTAL)
				if self.hook_callback:
					self.enqueue(self.hook_callback, PointerEventAxis(
						self.position.x, self.position.y, value, axis, mods))

	def install_pointer_hook(self, callback, grab=False):

		self.hook_callback = callback

	def uninstall_pointer_hook(self):

		self.hook_callback = None

	def _mainloop(self):

		while True:
			method, args = self.queue.get()
			if method is None:
				break
			try:
				method(*args)
			except Exception as e:
				print(
					'Error in EvPointer mainloop: \n',
					''.join(traceback.format_exception(
						type(e), e, e.__traceback__)))
			self.queue.task_done()

	def enqueue(self, method, *args):

		self.queue.put_nowait((method, args))

	def _warp(self, x, y, relative=False):

		if relative:
			dx = x
			dy = y
		else:
			dx = x - self.position.x
			dy = y - self.position.y
		self.uinput.write(ecodes.EV_REL, ecodes.REL_X, dx)
		self.uinput.write(ecodes.EV_REL, ecodes.REL_Y, dy)
		self.uinput.syn()

	def warp(self, x, y, relative=False):

		self.enqueue(self._warp, x, y, relative)

	def _scroll(self, axis, value):

		if axis is mPAxis.VERTICAL:
			self.uinput.write(ecodes.EV_REL, ecodes.REL_WHEEL, -value)
		elif axis is mPAxis.HORIZONTAL:
			self.uinput.write(ecodes.EV_REL, ecodes.REL_HWHEEL, value)
		else:
			raise TypeError('Invalid axis type')
		self.uinput.syn()

	def scroll(self, axis, value):

		self.enqueue(self._scroll, axis, value)

	def _click(self, key, state=None):

		if state is None:
			self.uinput.write(ecodes.EV_KEY, key.ec.value, 1)
			self.uinput.write(ecodes.EV_KEY, key.ec.value, 0)
		elif state is KeyState.PRESSED:
			self.uinput.write(ecodes.EV_KEY, key.ec.value, 1)
		elif state is KeyState.RELEASED:
			self.uinput.write(ecodes.EV_KEY, key.ec.value, 0)
		self.uinput.syn()

	def click(self, key, state=None):

		self.enqueue(self._click, key)

	def get_button_state(self, button):

		active_keys = set()
		for dev in self.pointer_devs:
			active_keys |= set(dev.active_keys())
		if button.ec in active_keys:
			return KeyState.PRESSED
		else:
			return KeyState.RELEASED
