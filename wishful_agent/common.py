import sys
import inspect
import logging
import socket
import fcntl
import struct
import datetime
import wishful_upis as upis
from .core import upis_builder

__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "gawlowicz@tkn.tu-berlin.de"


def get_inheritors(klass):
    subclasses = {}
    work = [klass]
    while work:
        parent = work.pop()
        for child in parent.__subclasses__():
            if child not in subclasses:
                subclasses[str(child.__name__)] = child
                work.append(child)
    return subclasses


def get_inheritors_set(klass):
    subclasses = set()
    work = [klass]
    while work:
        parent = work.pop()
        for child in parent.__subclasses__():
            if child not in subclasses:
                subclasses.add(child)
                work.append(child)
    return subclasses


def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if sys.version_info.major >= 3:
        ifname = bytes(ifname[:15], 'utf-8')
    else:
        ifname = ifname[:15]

    val = socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', ifname)
    )[20:24])
    s.close()

    return val


class CallingContext(object):
    def __init__(self):
        # function call context
        self._src = None
        self._dst = None
        self._device = None
        self._upi_type = None
        self._upi = None
        self._args = None
        self._kwargs = None
        self._callId = "1"
        self._blocking = True
        self._exec_time = None
        self._timeout = None
        self._callback = None
        self._scope = None  # todo remove
        self._iface = None  # todo remove


class ControllableUnit(object):
    def __init__(self):
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))

        self._callingCtx = CallingContext()
        self._clear_call_context()
        # UPIs
        builder = upis_builder.UpiBuilder(self)
        self.radio = builder.create_upi(upis.radio.Radio, "radio")
        self.net = builder.create_upi(upis.net.Network, "net")
        self.mgmt = builder.create_upi(upis.mgmt.Mgmt, "mgmt")
        self.context = builder.create_upi(upis.context.Context, "context")

    def node(self, node):
        self._callingCtx._scope = node
        return self

    def nodes(self, nodelist):
        self._callingCtx._scope = nodelist
        return self

    def device(self, dev):
        self._callingCtx._iface = dev
        self._callingCtx._device = dev
        return self

    def iface(self, iface):
        self._callingCtx._iface = iface
        self._callingCtx._device = iface
        return self

    def blocking(self, value=True):
        self._callingCtx._blocking = value
        return self

    def exec_time(self, exec_time):
        self._callingCtx._exec_time = exec_time
        self._callingCtx._blocking = False
        return self

    def delay(self, delay):
        exec_time = datetime.datetime.now() + datetime.timedelta(seconds=delay)
        self._callingCtx._exec_time = exec_time
        self._callingCtx._blocking = False
        return self

    def timeout(self, value):
        self._callingCtx._timeout = value
        return self

    def callback(self, callback):
        self._callingCtx._callback = callback
        self._callingCtx._blocking = False
        return self

    def _clear_call_context(self, ctx=None):
        self._callingCtx._src = None
        self._callingCtx._dst = None
        self._callingCtx._device = None
        self._callingCtx._upi_type = None
        self._callingCtx._upi = None
        self._callingCtx._args = None
        self._callingCtx._kwargs = None
        self._callingCtx._callId = None
        self._callingCtx._blocking = True
        self._callingCtx._exec_time = None
        self._callingCtx._timeout = None
        self._callingCtx._callback = None
        self._callingCtx._scope = None  # todo remove
        self._callingCtx._iface = None  # todo remove
        if ctx:
            ctx._src = None
            ctx._dst = None
            ctx._device = None
            ctx._upi_type = None
            ctx._upi = None
            ctx._args = None
            ctx._kwargs = None
            ctx._callId = "1"
            ctx._blocking = True
            ctx._exec_time = None
            ctx._timeout = None
            ctx._callback = None
            ctx._scope = None  # todo remove
            ctx._iface = None  # todo remove

    def send_msg(self, ctx):
        self.log.debug("{}:{}".format(ctx._upi_type, ctx._upi))

    def cmd_wrapper(self, upi_type, fname, *args, **kwargs):
        self._callingCtx._upi_type = "function"
        self._callingCtx._upi = fname
        self._callingCtx._args = args
        self._callingCtx._kwargs = kwargs
        return self.send_msg(self._callingCtx)

    def get_upi_string(self, event):
        className = None
        if inspect.isclass(event):
            className = event.__name__
        else:
            className = event.__class__.__name__

        return event.__module__ + '.' + className

    def enable_event(self, event):
        self._callingCtx._upi_type = "event_enable"
        self._callingCtx._upi = self.get_upi_string(event)
        self._callingCtx._args = ["start"]
        self._callingCtx._kwargs = {}
        return self.send_msg(self._callingCtx)

    def disable_event(self, event):
        self._callingCtx._upi_type = "event_disable"
        self._callingCtx._upi = self.get_upi_string(event)
        self._callingCtx._args = ["stop"]
        self._callingCtx._kwargs = {}
        return self.send_msg(self._callingCtx)

    def is_event_enabled(self, event):
        pass

    def start_service(self, service):
        self._callingCtx._upi_type = "service_start"
        self._callingCtx._upi = self.get_upi_string(service)
        self._callingCtx._args = ["start"]
        self._callingCtx._kwargs = {}
        return self.send_msg(self._callingCtx)

    def stop_service(self, service):
        self._callingCtx._upi_type = "service_stop"
        self._callingCtx._upi = self.get_upi_string(service)
        self._callingCtx._args = ["stop"]
        self._callingCtx._kwargs = {}
        return self.send_msg(self._callingCtx)

    def is_service_enabled(self, service):
        pass

    def add_rule(self, rule):
        pass

    def del_rule(self, rule):
        pass
