import uuid
import logging
import inspect
from queue import Queue, Empty
from threading import Thread
from functools import partial
from uniflex.core.common import is_func_implemented
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
        self.name = self.__class__.__name__
        self.agent = None
        self.localNode = None
        self.moduleManager = None

        self.callIdGen = 0
        self.callbacks = {}

        self.functions = []
        self.in_events = []
        self.out_events = []
        self.firstCallToModule = False

        if not isinstance(self, CoreModule):
            funcs = [m for m in dir(self) if _is_method(getattr(self, m))]

            filterFunc = set(["set_agent", "set_module_manager",
                              "send_event", "get_device",
                              "get_functions", "get_in_events",
                              "get_out_events",
                              "_add_node", "_remove_node",
                              "get_nodes", "get_node",
                              "get_node_by_uuid",
                              "get_node_by_hostname",
                              "__init__", "recv_msgs"])

            funcs = sorted(list(set(funcs) - filterFunc))

            # filter not implemented funcs
            funcs = [getattr(self, f) for f in funcs]
            funcs = filter(is_func_implemented, funcs)
            funcs = [f.__name__ for f in funcs]
            # filter private functions starring with _
            funcs = filter(lambda x: not x.startswith("_"), funcs)
            self.functions = funcs

        # TODO: move to DeviceModule
        self.device = None

    def set_agent(self, agent):
        self.agent = agent

    def set_module_manager(self, mm):
        self.moduleManager = mm

    def get_device(self):
        return self.device

    def get_functions(self):
        return self.functions

    def get_in_events(self):
        return self.in_events

    def get_out_events(self):
        return self.out_events

    def send_event(self, event, mode="GLOBAL"):
        """
        Sent event using one of two modes: nodebroadcast
        and global-broadcast.
        Returns True if succeeded; otherwise False
        """
        # stamp event with module
        if not event.srcModule:
            event.srcModule = self
        # stamp event with node
        if not event.srcNode:
            event.srcNode = self.agent.nodeManager.get_local_node()
        self.moduleManager.send_event(event)


class CoreModule(UniFlexModule):
    def __init__(self):
        super(CoreModule, self).__init__()


class DeviceModule(UniFlexModule):
    def __init__(self):
        super(DeviceModule, self).__init__()


class ProtocolModule(UniFlexModule):
    def __init__(self):
        super(ProtocolModule, self).__init__()


class ApplicationModule(UniFlexModule):
    def __init__(self):
        super(ApplicationModule, self).__init__()


class ControlApplication(UniFlexModule):
    def __init__(self):
        super(ControlApplication, self).__init__()
        self._nodes = {}

    def get_local_node(self):
        """
        Get NodeProxy object for local node , i.e. the one
        that runs Application.
        Returns NodeProxy object.
        """
        return self.localNode

    def subscribe_for_events(self, eventType, callback, mode):
        """
        Subscribe for events of specific type using one of
        two modes:
        - node-broadcast — subscribe for events of specific
        type generated on local node
        - global-broadcast – subscribe for events of specific
        type generated at any node in network
        The callback function will be called on reception
        of event.
        Note: If event type is not specified, application
        subscribes for events of all types.
        Returns True if succeeded; otherwise False
        """
        pass

    def unsubscribe_from_events(self, eventType):
        """
        Unsubscribe from event from specific type. If
        event type is not given, unsubscribe from all
        event types.
        Returns True if succeeded; otherwise False
        """
        pass

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
