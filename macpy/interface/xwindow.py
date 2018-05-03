#!/usr/bin/env python3

import time
from threading import Thread
from six import with_metaclass
from Xlib import display, X, Xutil
from Xlib.protocol import event as xevent
from Xlib.error import BadWindow, DisplayNameError
from ..types.metawindow import MetaWindow
from ..constant.xatom import NET_WM_PID, NET_WM_VISIBLE_NAME, NET_WM_NAME
from ..constant.xatom import NET_CLIENT_LIST, NET_ACTIVE_WINDOW, WM_STATE
from ..constant.xatom import NET_WM_STATE, NET_WM_STATE_MAXIMIZED_VERT
from ..constant.xatom import NET_WM_STATE_MAXIMIZED_HORZ, NET_WM_STATE_REMOVE
from ..constant.xatom import NET_WM_STATE_ADD, NET_WM_STATE_TOGGLE
from ..constant.xatom import WM_CHANGE_STATE, NET_MOVERESIZE_WINDOW
from ..constant.xatom import NET_CLOSE_WINDOW
from ..event import WindowEventType as WinEType, WindowEvent, WindowState
from ..event import KeyboardEvent, PointerEventMotion, PointerEventButton
from ..event import PointerEventAxis, PointerAxis
from ..types.tuples import WinPos, WinSize
from ..types.dummy import Display
from .xhelper import XTranslate
from ..key import Key, KeyState

class XWindow(with_metaclass(MetaWindow)):

	try:
		disp = display.Display()
	except DisplayNameError:
		disp = Display()
	root = disp.screen().root

	hook = None

	def __init__(self, xid):

		try:
			self.xwindow = self.disp.create_resource_object('window', xid)
		except BadWindow:
			self.xwindow = None
		self.wm_class = self.get_wm_class()
		self.pid = self.get_pid()

		self.translate = XTranslate()
		self.rebuttonmap = {
			Key.BTN_LEFT: 1,
			Key.BTN_MOUSE: 1,
			Key.BTN_MIDDLE: 2,
			Key.BTN_RIGHT: 3,
			Key.BTN_SIDE: 8,
			Key.BTN_EXTRA: 9}

	def __hash__(self):

		return hash(self.xwindow.id)

	def get_wm_class(self):

		if self.xwindow:
			try:
				try:
					wm_class = self.xwindow.get_wm_class()
					if wm_class:
						return '{0}.{1}'.format(*wm_class)
				except AttributeError:
					return 'root.Root'
			except BadWindow:
				pass
		return None

	def get_pid(self):

		if self.xwindow:
			try:
				try:
					prop = self.xwindow.get_full_property(
						NET_WM_PID, X.AnyPropertyType)
					if prop:
						return prop.value[0]
				except AttributeError:
					pass
			except BadWindow:
				pass
		return None

	@property
	def title(self):

		def get_title(xwindow):

			try:
				if type(xwindow) is not int:
					prop = xwindow.get_full_property(
						NET_WM_VISIBLE_NAME, X.AnyPropertyType)
					if not prop:
						prop = xwindow.get_full_property(
							NET_WM_NAME, X.AnyPropertyType)
					if prop:
						if type(prop.value) is bytes:
							return prop.value.decode()
						else:
							return prop.value
					else:
						return get_title(xwindow.query_tree().parent)
			except BadWindow:
				pass
			return None

		if self.xwindow:
			return get_title(self.xwindow)
		return None

	@classmethod
	def install_window_hook(cls, callback):

		cls.stop = False
		cls.hook_callback = callback
		cls.hook_display = display.Display()
		cls.hook_root = cls.hook_display.screen().root
		cls.hook_root.change_attributes(event_mask=X.PropertyChangeMask)
		cls.hook = Thread(target=cls._hook, name='XWindow hook loop')
		cls.hook.start()

	@classmethod
	def uninstall_window_hook(cls):

		if cls.hook and cls.hook.is_alive():
			cls.stop = True
			cls.hook.join()
			cls.hook_display.close()
			del cls.hook_root
			del cls.hook_display

	@classmethod
	def _hook(cls):

		prop = cls.hook_root.get_full_property(
			NET_CLIENT_LIST, X.AnyPropertyType)
		xid_list = prop.value
		while not cls.stop:
			for nevent in range(cls.hook_display.pending_events()):
				event = cls.hook_display.next_event()
				if event.type == X.PropertyNotify:
					if event.atom == NET_ACTIVE_WINDOW:
						prop = cls.hook_root.get_full_property(
							NET_ACTIVE_WINDOW, X.AnyPropertyType)
						cls.hook_callback(WindowEvent(
							cls(prop.value[0]), WinEType.FOCUSED))
					if event.atom == NET_CLIENT_LIST:
						prop = cls.hook_root.get_full_property(
							NET_CLIENT_LIST, X.AnyPropertyType)
						for xid in prop.value:
							if xid not in xid_list:
								cls.hook_callback(WindowEvent(
									cls(xid), WinEType.CREATED))
						for xid in xid_list:
							if xid not in prop.value:
								cls.hook_callback(WindowEvent(
									cls(xid), WinEType.DESTROYED))
						xid_list = prop.value
		time.sleep(0.005)

	@classmethod
	def list_windows(cls):

		prop = cls.root.get_full_property(NET_CLIENT_LIST, X.AnyPropertyType)
		window_list = []
		for xid in prop.value:
			window_list.append(cls(xid))
		return tuple(window_list)

	@classmethod
	def get_active(cls):

		prop = cls.root.get_full_property(NET_ACTIVE_WINDOW, X.AnyPropertyType)
		return cls(prop.value[0])

	@classmethod
	def get_under_pointer(cls):

		def get_child(xwindow):

			children = xwindow.query_tree().children
			for child in children:
				window = cls(child.id)
				if window.wm_class:
					return window
			return None

		pointer = cls.root.query_pointer()
		xwindow = pointer.child
		window = cls(xwindow.id)
		if not window.wm_class:
			return get_child(xwindow)
		return window

	@classmethod
	def get_by_class(cls, wm_class):

		for window in cls.list_windows():
			if window.wm_class == wm_class:
				return window
		return None

	@classmethod
	def get_by_title(cls, title):

		for window in cls.list_windows():
			if title in window.title:
				return window
		return None

	@property
	def state(self):

		min_state = self.xwindow.get_full_property(WM_STATE, X.AnyPropertyType)
		if min_state.value[0] == Xutil.IconicState:
			return WindowState.MINIMIZED
		max_state = self.xwindow.get_full_property(
			NET_WM_STATE, X.AnyPropertyType)
		if (NET_WM_STATE_MAXIMIZED_VERT in max_state.value
				and NET_WM_STATE_MAXIMIZED_HORZ in max_state.value):
			return WindowState.MAXIMIZED
		return WindowState.NORMAL

	@property
	def position(self):

		geometry = self.xwindow.get_geometry()
		return WinPos(geometry.x, geometry.y)

	@property
	def size(self):

		geometry = self.xwindow.get_geometry()
		return WinSize(geometry.width, geometry.height)

	def client_message(self, atom, data):

		dataSize = 32
		mask = X.SubstructureRedirectMask | X.SubstructureNotifyMask
		ev = xevent.ClientMessage(
			window=self.xwindow,
			client_type=atom,
			data=(dataSize, data))
		self.root.send_event(ev, event_mask=mask)
		self.disp.flush()

	def activate(self):

		data = (1, X.CurrentTime, self.xwindow.id, 0, 0)
		self.client_message(NET_ACTIVE_WINDOW, data)

	def restore(self):

		self.activate()
		data = (
			NET_WM_STATE_REMOVE,
			NET_WM_STATE_MAXIMIZED_VERT,
			NET_WM_STATE_MAXIMIZED_HORZ,
			1, 0)
		self.client_message(NET_WM_STATE, data)

	def minimize(self):

		data = (Xutil.IconicState, 0, 0, 0, 0)
		self.client_message(WM_CHANGE_STATE, data)

	def maximize(self):

		data = (
			NET_WM_STATE_ADD,
			NET_WM_STATE_MAXIMIZED_VERT,
			NET_WM_STATE_MAXIMIZED_HORZ,
			1, 0)
		self.client_message(NET_WM_STATE, data)

	def resize(self, width, height):

		data = (
		# Gravity NW | x set | y set | width set | height set | source
			(1 | (0 << 8) | (0 << 9)
				| (width << 10) | (height << 11) | (1 << 12)),
			0, 0,
			width, height)
		self.client_message(NET_MOVERESIZE_WINDOW, data)

	def move(self, x, y):

		data = (
		# Gravity NW | x set | y set | width set | height set | source
			1 | (1 << 8) | (1 << 9) | (0 << 10) | (0 << 11) | (1 << 12),
			x, y,
			0, 0)
		self.client_message(NET_MOVERESIZE_WINDOW, data)

	def close(self):

		data = (X.CurrentTime, 1, 0, 0, 0)
		self.client_message(NET_CLOSE_WINDOW, data)

	def force_close(self):

		self.xwindow.kill_client()
		self.disp.flush()

	def send_event(self, event):

		mask = 0
		for mod, active in event.modifiers._asdict().items():
			if active:
				mask |= self.translate.modmask[mod]
		if isinstance(event, KeyboardEvent):
			self.send_key(event.key, event.state, mask)
		elif isinstance(event, PointerEventMotion):
			self.send_motion(event.position, mask)
		elif isinstance(event, PointerEventButton):
			self.send_button(event.position, event.button, event.state, mask)
		elif isinstance(event, PointerEventAxis):
			self.send_axis(event.position, event.value, event.axis, mask)
		else:
			raise TypeError('Unsupported event')

	def send_key(self, key, state, mask):

		if state is KeyState.PRESSED:
			ev = xevent.KeyPress(
				time=X.CurrentTime,
				root=self.root,
				window=self.xwindow,
				same_screen=True,
				child=X.NONE,
				root_x=0,
				root_y=0,
				event_x=0,
				event_y=0,
				state=mask,
				detail=key.ec + self.translate.min_keycode)
			self.xwindow.send_event(ev)
		elif state is KeyState.RELEASED:
			ev = xevent.KeyRelease(
				time=X.CurrentTime,
				root=self.root,
				window=self.xwindow,
				same_screen=True,
				child=X.NONE,
				root_x=0,
				root_y=0,
				event_x=0,
				event_y=0,
				state=mask,
				detail=key.ec + self.translate.min_keycode)
			self.xwindow.send_event(ev)
		else:
			raise TypeError('Unsupported state')
		self.disp.flush()

	def send_motion(self, position, mask):

		ev = xevent.MotionNotify(
			time=X.CurrentTime,
			root=self.root,
			window=self.xwindow,
			same_screen=True,
			child=X.NONE,
			root_x=0,
			root_y=0,
			event_x=position.x,
			event_y=position.y,
			state=mask,
			detail=0)
		self.xwindow.send_event(ev)
		self.disp.flush()

	def send_button(self, position, button, state, mask):

		if state is KeyState.PRESSED:
			ev = xevent.ButtonPress(
				time=X.CurrentTime,
				root=self.root,
				window=self.xwindow,
				same_screen=True,
				child=X.NONE,
				root_x=0,
				root_y=0,
				event_x=position.x,
				event_y=position.y,
				state=mask,
				detail=self.rebuttonmap[button])
			self.xwindow.send_event(ev)
		elif state is KeyState.RELEASED:
			ev = xevent.ButtonRelease(
				time=X.CurrentTime,
				root=self.root,
				window=self.xwindow,
				same_screen=True,
				child=X.NONE,
				root_x=0,
				root_y=0,
				event_x=position.x,
				event_y=position.y,
				state=mask,
				detail=self.rebuttonmap[button])
			self.xwindow.send_event(ev)
		else:
			raise TypeError('Unsupported state')
		self.disp.flush()

	def send_axis(self, position, value, axis, mask):

		if axis is PointerAxis.VERTICAL:
			if value < 0:
				button = 4
			else:
				button = 5
		elif axis is PointerAxis.HORIZONTAL:
			if value < 0:
				button = 6
			else:
				button = 7
		else:
			raise TypeError('Unsupported axis')

		pev = xevent.ButtonPress(
			time=X.CurrentTime,
			root=self.root,
			window=self.xwindow,
			same_screen=True,
			child=X.NONE,
			root_x=0,
			root_y=0,
			event_x=position.x,
			event_y=position.y,
			state=mask,
			detail=button)
		rev = xevent.ButtonRelease(
			time=X.CurrentTime,
			root=self.root,
			window=self.xwindow,
			same_screen=True,
			child=X.NONE,
			root_x=0,
			root_y=0,
			event_x=position.x,
			event_y=position.y,
			state=mask,
			detail=button)
		for i in range(abs(value)):
			self.xwindow.send_event(pev)
			self.xwindow.send_event(rev)
		self.disp.flush()
