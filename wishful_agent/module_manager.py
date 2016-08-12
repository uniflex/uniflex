import logging
import inspect

__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "gawlowicz@tkn.tu-berlin.de"


class ModuleManager(object):
    def __init__(self, agent):
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))

        self.agent = agent
        self.moduleIdGen = 0

        self.modules = {}
        self._event_handlers = {}
        self._function_handlers = {}

    def my_import(self, module_name):
        pyModule = __import__(module_name)
        globals()[module_name] = pyModule
        return pyModule

    def generate_new_module_id(self):
        newId = self.moduleIdGen
        self.moduleIdGen = self.moduleIdGen + 1
        return newId

    def register_module(self, moduleName, pyModuleName,
                        className, device=None, kwargs={}):
        self.log.debug("Add new module: {}:{}:{}:{}".format(
            moduleName, pyModuleName, className, device))

        pyModule = self.my_import(pyModuleName)
        wishful_module_class = getattr(pyModule, className)
        wishfulModule = wishful_module_class(**kwargs)
        wishfulModule.set_device(device)

        return self.add_module_obj(moduleName, wishfulModule)

    def add_module_obj(self, moduleName, wishfulModule):
        self.log.debug("Add new module: {}:{}"
                       .format(moduleName, wishfulModule))

        moduleId = self.generate_new_module_id()
        wishfulModule.id = moduleId
        wishfulModule.set_module_manager(self)
        wishfulModule.set_agent(self.agent)
        self.register_event_handlers(wishfulModule)
        self.register_function_handlers(wishfulModule)

        self.modules[moduleId] = wishfulModule
        return wishfulModule

    # TODO: can be integrated with new event passing mechanism
    def start(self):
        self.log.debug("Notify START to modules".format())
        for module in list(self.modules.values()):
            module.start()

    def exit(self):
        self.log.debug("Notify EXIT to modules".format())
        for module in list(self.modules.values()):
            module.exit()

    def connected(self):
        self.log.debug("Notify CONNECTED to modules".format())
        for module in list(self.modules.values()):
            module.connected()

    def disconnected(self):
        self.log.debug("Notify DISCONNECTED to modules".format())
        for module in list(self.modules.values()):
            module.disconnected()

    def register_event_handlers(self, i):
        for _k, handler in inspect.getmembers(i, inspect.ismethod):
            if hasattr(handler, 'callers'):
                for ev_cls, c in handler.callers.items():
                    self._event_handlers.setdefault(ev_cls, [])
                    self._event_handlers[ev_cls].append(handler)
                    i.events.append(handler.__name__)

    def get_event_handlers(self, ev, state=None):
        ev_cls = ev.__class__
        handlers = self._event_handlers.get(ev_cls, [])
        return handlers

    def send_event(self, event):
        handlers = self.get_event_handlers(event)
        for handler in handlers:
            try:
                handler(event)
            except:
                self.log.exception('Exception occurred during handler '
                                   'processing. Backtrace from offending '
                                   'handler [%s] servicing event [%s] follows',
                                   handler.__name__, event.__class__.__name__)

    def register_function_handlers(self, i):
        for _k, handler in inspect.getmembers(i, inspect.ismethod):
            if hasattr(handler, '_upiFunc_'):
                if handler._upiFunc_:
                    self._function_handlers.setdefault(handler._upiFunc_, [])
                    self._function_handlers[handler._upiFunc_].append(handler)
                    i.functions.append(handler.__name__)

    def get_function_handlers(self, upiFunc, state=None):
        handlers = self._function_handlers.get(upiFunc, [])
        return handlers

    def execute_function(self, upiFunc, device=None, args=[], kwargs={}):
        handlers = self.get_function_handlers(upiFunc)
        callNumber = 0
        returnValue = None

        for handler in handlers:
            try:
                module = handler.__self__
                myDevice = module.get_device()

                # filter based on device present:
                # if device is not required execute function
                if myDevice is None and device is None:
                    self.log.info("Execute function: {} in module: {}"
                                  " without device"
                                  .format(upiFunc, module.__class__.__name__))

                    # if there is function that has to be
                    # called before UPI function, call
                    if hasattr(handler, '_before'):
                        before_func = getattr(handler, "_before")
                        before_func()

                    returnValue = handler(*args, **kwargs)
                    callNumber = callNumber + 1

                    # if there is function that has to be
                    # called after UPI function, call
                    if hasattr(handler, '_after'):
                        after_func = getattr(handler, "_after")
                        after_func()

                # if devices match execute function
                elif myDevice == device:
                    self.log.info("Execute function: {} in module: {}"
                                  " with device: {}"
                                  .format(upiFunc,
                                          module.__class__.__name__, device))

                    # if there is function that has to be
                    # called before UPI function, call
                    if hasattr(handler, '_before'):
                        before_func = getattr(handler, "_before")
                        before_func()

                    returnValue = handler(*args, **kwargs)
                    callNumber = callNumber + 1

                    # if there is function that has to be
                    # called after UPI function, call
                    if hasattr(handler, '_after'):
                        after_func = getattr(handler, "_after")
                        after_func()

                # otherwise go to next module
                else:
                    continue

            except:
                self.log.debug('Exception occurred during handler '
                               'processing. Backtrace from offending '
                               'handler [%s] servicing UPI function '
                               '[%s] follows',
                               handler.__name__, upiFunc)
                raise

        self.log.info("Function: {} was called {} times"
                      .format(upiFunc, callNumber))
        # TODO: if callNum == 0 rise an exeption?
        return returnValue
