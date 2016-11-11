import inspect
import copy
import threading
import logging
import datetime
from . import events

__author__ = "Piotr Gawlowicz, Anatolij Zubow"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "{gawlowicz|zubow}@tkn.tu-berlin.de"


class CallingContext(object):
    def __init__(self):
        # function call context
        self._type = None
        self._name = None
        self._args = None
        self._kwargs = None
        self._callId = None
        self._blocking = True
        self._exec_time = None
        self._timeout = None
        self._callback = None


class ModuleProxy(object):
    def __init__(self):
        '''
        Module proxy does not contain any functions of remote object,
        they are created at runtime upon reception of remote object description
        '''
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))

        self.uuid = None
        self.type = None
        self.name = None
        self.node = None

        self._callIdGen = 0

        self._callingCtx = CallingContext()
        self._clear_call_context()
        self._currentNode = None

        # containers for unit description
        self.functions = []
        self.in_events = []
        self.out_events = []

    def __call__(self, method, *args, **kwargs):
        # some magis is here :)
        return self.cmd_wrapper(ftype="function",
                                fname=method, args=args, kwargs=kwargs)

    def __getattr__(self, method):
        # but most magic is here :)
        return lambda *args, **kwargs: self(method, *args, **kwargs)

    def __str__(self):
        string = ("  Module: {}\n"
                  "    Name: {} \n"
                  "    UUID: {} \n"
                  .format(self.type, self.name, self.uuid))

        string = string + "    Functions:\n"
        for k in self.functions:
            string = string + "      {}\n".format(k)
        string = string + "    Consumes Events:\n"
        for k in self.in_events:
            string = string + "      {}\n".format(k)
        string = string + "    Generates Events:\n"
        for k in self.out_events:
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
        self._callingCtx._type = None
        self._callingCtx._name = None
        self._callingCtx._args = None
        self._callingCtx._kwargs = None
        self._callingCtx._callId = None
        self._callingCtx._blocking = True
        self._callingCtx._exec_time = None
        self._callingCtx._timeout = None
        self._callingCtx._callback = None

    def generate_call_id(self):
        self._callIdGen = self._callIdGen + 1
        return self._callIdGen

    def is_enabled(self):
        return True

    def start(self):
        pass

    def stop(self):
        pass

    def send_event(self, event):
        self.log.info("{}".format(event.__class__.__name__))

    def send_cmd_event(self, ctx):
        self.log.debug("{}:{}".format(ctx._type, ctx._name))

    def get_name_string(self, event):
        className = None
        if inspect.isclass(event):
            className = event.__name__
        else:
            className = event.__class__.__name__

        return event.__module__ + '.' + className

    def _send_cmd_event(self, ctx):
        cmdEvent = events.CommandEvent(ctx=ctx)
        cmdEvent.srcModule = threading.currentThread().module
        cmdEvent.srcNode = self._currentNode
        cmdEvent.dstModule = self.uuid
        return self.node.send_cmd_event(cmdEvent)

    def cmd_wrapper(self, ftype, fname, *args, **kwargs):
        self._callingCtx._type = "function"
        self._callingCtx._name = fname
        self._callingCtx._args = args
        self._callingCtx._kwargs = kwargs
        self._callingCtx._callId = self.generate_call_id()

        ctxCopy = copy.copy(self._callingCtx)
        self._clear_call_context()
        return self._send_cmd_event(ctxCopy)

    def is_func_supported(self, ftype, fName):
        self.log.info("Checking call: {}.{} for device {} in node {}"
                      .format(ftype, fName, self.name, self.node.hostname))

        return True
        myModule = self._module

        if ftype == "function":
            if fName in myModule.functions:
                return True
        elif ftype == "event_enable":
            return True
        else:
            return True

        return False


class DeviceProxy(ModuleProxy):
    def __str__(self):
        string = super().__str__()
        desc = ("    Device: {} \n"
                .format(self.name))
        string = string + desc
        return string


class ProtocolProxy(ModuleProxy):
    """docstring for ProtocolProxy"""
    pass


class ApplicationProxy(ModuleProxy):
    """docstring for ApplicationProxy"""
    pass
