import uuid
import logging
import inspect
from queue import Queue, Empty
from threading import Thread
from functools import partial
from . import events

__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universität Berlin"
__version__ = "0.1.0"
__email__ = "gawlowicz@tkn.tu-berlin.de"


def _listify(may_list):
    if may_list is None:
        may_list = []
    if not isinstance(may_list, list):
        may_list = [may_list]
    return may_list


def _is_method(f):
    return inspect.isfunction(f) or inspect.ismethod(f)


def on_event(ev_cls, dispatchers=None):
    def _set_ev_cls_dec(handler):
        if 'callers' not in dir(handler):
            handler.callers = {}
        for e in _listify(ev_cls):
            handler.callers[e] = e.__module__
        return handler
    return _set_ev_cls_dec


on_start = partial(on_event, events.AgentStartEvent)
on_exit = partial(on_event, events.AgentExitEvent)
on_connected = partial(on_event, events.ConnectionEstablishedEvent)
on_disconnected = partial(on_event, events.ConnectionLostEvent)


def run_in_thread():
    def _set_ev_cls_dec(handler):
        if '_run_in_thread_' not in dir(handler):
            handler._run_in_thread_ = True
        return handler
    return _set_ev_cls_dec


def on_first_call_to_module():
    def _set_ev_cls_dec(handler):
        if '_first_call_' not in dir(handler):
            handler._first_call_ = {}
        return handler
    return _set_ev_cls_dec


def before_call(func):
    def _set_ev_cls_dec(handler):
        if '_before_call_' not in dir(handler):
            handler._before_call_ = func
        return handler
    return _set_ev_cls_dec


def after_call(func):
    def _set_ev_cls_dec(handler):
        if '_after_call_' not in dir(handler):
            handler._after_call_ = func
        return handler
    return _set_ev_cls_dec


def on_function(upiFunc):
    def _set_ev_cls_dec(handler):
        if '_upiFunc_' not in dir(handler):
            handler._upiFunc_ = None
        handler._upiFunc_ = upiFunc.__module__ + "." + upiFunc.__name__
        return handler
    return _set_ev_cls_dec


bind_function = on_function


def event_enable(event):
    def _set_ev_cls_dec(handler):
        if '_event_enable_' not in dir(handler):
            handler._event_enable_ = None
        handler._event_enable_ = event.__module__ + "." + event.__name__
        return handler
    return _set_ev_cls_dec


def event_disable(event):
    def _set_ev_cls_dec(handler):
        if '_event_disable_' not in dir(handler):
            handler._event_disable_ = None
        handler._event_disable_ = event.__module__ + "." + event.__name__
        return handler
    return _set_ev_cls_dec


def service_start(service):
    def _set_ev_cls_dec(handler):
        if '_service_start_' not in dir(handler):
            handler._service_start_ = None
        handler._service_start_ = service.__module__ + "." + service.__name__
        return handler
    return _set_ev_cls_dec


def service_stop(service):
    def _set_ev_cls_dec(handler):
        if '_service_stop_' not in dir(handler):
            handler._service_stop_ = None
        handler._service_stop_ = service.__module__ + "." + service.__name__
        return handler
    return _set_ev_cls_dec


def build_module(module_class):
    original_methods = module_class.__dict__.copy()
    for name, method in original_methods.items():
        if hasattr(method, '_upi_fname'):
            # add UPI alias for the function
            for falias in method._upi_fname - set(original_methods):
                setattr(module_class, falias, method)
    return module_class


class ModuleWorker(Thread):
    def __init__(self, module):
        super().__init__()
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))
        self.module = module
        self.taskQueue = Queue()
        self.setDaemon(True)
        self.running = True
        self.start()

    def run(self):
        while self.running:
            try:
                (func, event) = self.taskQueue.get(0.2)
                if not self.running:
                    break

                if event:
                    func(event)
                else:
                    func()
            except Empty:
                continue
            except:
                raise

            self.taskQueue.task_done()

    def stop(self):
        self.running = False

    def add_task(self, func, event):
        self.taskQueue.put((func, event))


class UniFlexModule(object):
    def __init__(self):
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))

        self._enabled = False
        self.worker = ModuleWorker(self)
        self.uuid = str(uuid.uuid4())
        self.id = None
        self.name = self.__class__.__name__
        self.agent = None
        self.localNode = None
        self.moduleManager = None

        self.callIdGen = 0
        self.callbacks = {}

        self.attributes = []
        self.functions = []
        self.in_events = []
        self.out_events = []
        self.services = []
        self.firstCallToModule = False

        # TODO: move to DeviceModule
        self.device = None
        self.deviceId = None

        # TODO: move to ControllerModule (ControllerApp)
        # node container
        self._nodes = {}

    def set_agent(self, agent):
        self.agent = agent

    def set_module_manager(self, mm):
        self.moduleManager = mm

    def send_event(self, event):
        # stamp event with module
        if not event.srcModule:
            event.srcModule = self
        # stamp event with node
        if not event.srcNode:
            event.srcNode = self.agent.nodeManager.get_local_node()
        self.moduleManager.send_event(event)

    def get_device(self):
        return self.device

    def get_attributes(self):
        return self.attributes

    def get_functions(self):
        return self.functions

    def get_in_events(self):
        return self.in_events

    def get_out_events(self):
        return self.out_events

    def get_services(self):
        return self.services

    # TODO: move to ControllerModule (ControllerApp)
    def _add_node(self, node):
        self._nodes[node.uuid] = node
        return True

    def _remove_node(self, node):
        if node.uuid in self._nodes:
            del self._nodes[node.uuid]
            return True
        return False

    def get_nodes(self):
        return list(self._nodes.values())

    def get_node(self, idx):
        return list(self._nodes.values())[idx]

    def get_node_by_uuid(self, uuid):
        return self._nodes.get(uuid, None)

    def get_node_by_hostname(self, hostname):
        for n in self._nodes:
            if n.hostname == hostname:
                return n
        return None


class CoreModule(UniFlexModule):
    def __init__(self):
        super(CoreModule, self).__init__()


class AgentModule(UniFlexModule):
    def __init__(self):
        super(AgentModule, self).__init__()


class DeviceModule(UniFlexModule):
    def __init__(self):
        super(DeviceModule, self).__init__()


class ControllerModule(UniFlexModule):
    def __init__(self):
        super(ControllerModule, self).__init__()


class Application(ControllerModule):
    def __init__(self):
        super(Application, self).__init__()