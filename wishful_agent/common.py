import inspect
import copy
import threading
import logging
import datetime
import netifaces as ni
from netifaces import AF_INET
import wishful_upis as upis
from .core import upis_builder

__author__ = "Piotr Gawlowicz, Anatolij Zubow"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "{gawlowicz|zubow}@tkn.tu-berlin.de"


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
    try:
        # AZU: old code was for Linux only; does not work with OSX
        # new solution is platform independent
        val = ni.ifaddresses(ifname)[AF_INET][0]['addr']
        return val
    except Exception as e:
        print("Failed to get IP address of iface: {} {}".format(ifname, e))
        raise e


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
        self._callId = None
        self._blocking = True
        self._exec_time = None
        self._timeout = None
        self._callback = None


class ControllableUnit(object):
    def __init__(self):
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))

        self.uuid = None
        self.id = None
        self.module_id = None
        self.name = None
        self.module_name = None
        self.node = None

        self._callingCtx = CallingContext()
        self._clear_call_context()
        self._currentNode = None

        # UPIs
        builder = upis_builder.UpiBuilder(self)
        self.radio = builder.create_upi(upis.radio.Radio, "radio")
        self.net = builder.create_upi(upis.net.Network, "net")
        self.mgmt = builder.create_upi(upis.mgmt.Mgmt, "mgmt")
        self.context = builder.create_upi(upis.context.Context, "context")

        # containers for unit description
        self.attributes = []
        self.functions = []
        self.in_events = []
        self.out_events = []
        self.services = []

    def __str__(self):
        string = ("  Module: {}\n"
                  "    ID: {} \n"
                  "    UUID: {} \n"
                  .format(self.module_name, self.module_id, self.uuid))

        string = string + "    Attributes:\n"
        for k in self.attributes:
            string = string + "      {}\n".format(k)
        string = string + "    Functions:\n"
        for k in self.functions:
            string = string + "      {}\n".format(k)
        string = string + "    Consumes Events:\n"
        for k in self.in_events:
            string = string + "      {}\n".format(k)
        string = string + "    Generates Events:\n"
        for k in self.out_events:
            string = string + "      {}\n".format(k)
        string = string + "    Services:\n"
        for k in self.services:
            string = string + "      {}\n".format(k)
        return string

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

    def _clear_call_context(self):
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

    def is_enabled(self):
        return True

    def start(self):
        pass

    def stop(self):
        pass

    def send_event(self, event):
        self.log.info("{}".format(event.__class__.__name__))

    def send_cmd_event(self, ctx):
        self.log.debug("{}:{}".format(ctx._upi_type, ctx._upi))

    def get_upi_string(self, event):
        className = None
        if inspect.isclass(event):
            className = event.__name__
        else:
            className = event.__class__.__name__

        return event.__module__ + '.' + className

    def cmd_wrapper(self, upi_type, fname, *args, **kwargs):
        self._callingCtx._upi_type = "function"
        self._callingCtx._upi = fname
        self._callingCtx._args = args
        self._callingCtx._kwargs = kwargs

        ctxCopy = copy.copy(self._callingCtx)
        self._clear_call_context()
        cmdEvent = upis.mgmt.CommandEvent(ctx=ctxCopy)
        cmdEvent.srcModule = threading.currentThread().module
        cmdEvent.srcNode = self._currentNode

        return self.send_cmd_event(cmdEvent)

    def enable_event(self, event, *args, **kwargs):
        self._callingCtx._upi_type = "event_enable"
        self._callingCtx._upi = self.get_upi_string(event)
        self._callingCtx._args = args
        self._callingCtx._kwargs = kwargs

        ctxCopy = copy.copy(self._callingCtx)
        self._clear_call_context()
        cmdEvent = upis.mgmt.CommandEvent(ctx=ctxCopy)
        cmdEvent.srcModule = threading.currentThread().module
        cmdEvent.srcNode = self._currentNode

        return self.send_cmd_event(cmdEvent)

    def disable_event(self, event):
        self._callingCtx._upi_type = "event_disable"
        self._callingCtx._upi = self.get_upi_string(event)
        self._callingCtx._args = []
        self._callingCtx._kwargs = {}

        ctxCopy = copy.copy(self._callingCtx)
        self._clear_call_context()
        cmdEvent = upis.mgmt.CommandEvent(ctx=ctxCopy)
        cmdEvent.srcModule = threading.currentThread().module
        cmdEvent.srcNode = self._currentNode

        return self.send_cmd_event(cmdEvent)

    def is_event_enabled(self, event):
        pass

    def start_service(self, service, *args, **kwargs):
        self._callingCtx._upi_type = "service_start"
        self._callingCtx._upi = self.get_upi_string(service)
        self._callingCtx._args = args
        self._callingCtx._kwargs = kwargs

        ctxCopy = copy.copy(self._callingCtx)
        self._clear_call_context()
        cmdEvent = upis.mgmt.CommandEvent(ctx=ctxCopy)
        cmdEvent.srcModule = threading.currentThread().module
        cmdEvent.srcNode = self._currentNode

        return self.send_cmd_event(cmdEvent)

    def stop_service(self, service):
        self._callingCtx._upi_type = "service_stop"
        self._callingCtx._upi = self.get_upi_string(service)
        self._callingCtx._args = []
        self._callingCtx._kwargs = {}

        ctxCopy = copy.copy(self._callingCtx)
        self._clear_call_context()
        cmdEvent = upis.mgmt.CommandEvent(ctx=ctxCopy)
        cmdEvent.srcModule = threading.currentThread().module
        cmdEvent.srcNode = self._currentNode

        return self.send_cmd_event(cmdEvent)

    def is_service_enabled(self, service):
        pass

    def is_upi_supported(self, upiType, upiName):
        self.log.info("Checking call: {}.{} for device {} in node {}"
                      .format(upiType, upiName, self.name, self.node.hostname))

        return True
        myModule = self._module

        if upiType == "function":
            if upiName in myModule.functions:
                return True
        elif upiType == "event_enable":
            return True
        else:
            return True

        return False
