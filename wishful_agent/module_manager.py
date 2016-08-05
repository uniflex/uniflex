import logging
import inspect

__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "gawlowicz@tkn.tu-berlin.de"


def _has_caller(meth):
    return hasattr(meth, 'callers')


class ModuleManager(object):
    def __init__(self, agent):
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))

        self.agent = agent
        self.moduleIdGen = 0
        self.ifaceIdGen = 0

        self.modules = {}
        self.interfaces = {}
        self.iface_to_module_mapping = {}
        self.modules_without_iface = []

        self._event_handlers = {}

    def my_import(self, module_name):
        pyModule = __import__(module_name)
        globals()[module_name] = pyModule
        return pyModule

    def generate_new_module_id(self):
        newId = self.moduleIdGen
        self.moduleIdGen = self.moduleIdGen + 1
        return newId

    def generate_new_iface_id(self):
        newId = self.ifaceIdGen
        self.ifaceIdGen = self.ifaceIdGen + 1
        return newId

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

    def get_iface_id(self, name):
        for k, v in self.interfaces.items():
            if v == name:
                return k
        return None

    def add_local_control_program_manager(self, wishfulModule):
        self.add_module_obj("localControlProgramManager", wishfulModule)
        self.localControlProgramManager = wishfulModule

    def register_event_handlers(self, i):
        for _k, handler in inspect.getmembers(i, inspect.ismethod):
            if _has_caller(handler):
                for ev_cls, c in handler.callers.items():
                    self._event_handlers.setdefault(ev_cls, [])
                    self._event_handlers[ev_cls].append(handler)

    def get_event_handlers(self, ev, state=None):
        ev_cls = ev.__class__
        handlers = self._event_handlers.get(ev_cls, [])
        return handlers

    def add_module_obj(self, moduleName, wishfulModule, interfaces=None):
        self.log.debug("Add new module: {}:{}:{}".format(
            moduleName, wishfulModule, interfaces))

        moduleId = self.generate_new_module_id()
        wishfulModule.id = moduleId
        wishfulModule.set_module_manager(self)
        wishfulModule.set_agent(self.agent)
        self.register_event_handlers(wishfulModule)

        self.modules[moduleId] = wishfulModule

        if interfaces is None:
            self.modules_without_iface.append(wishfulModule)
            return wishfulModule

        for iface in interfaces:
            if iface not in list(self.interfaces.values()):
                iface_id = self.generate_new_iface_id()
                self.interfaces[iface_id] = str(iface)

            if iface_id not in self.iface_to_module_mapping:
                self.iface_to_module_mapping[iface_id] = [wishfulModule]
            else:
                self.iface_to_module_mapping[iface_id].append(wishfulModule)

        return wishfulModule

    def register_module(self, moduleName, pyModuleName,
                        className, devices, kwargs):
        self.log.debug("Add new module: {}:{}:{}:{}".format(
            moduleName, pyModuleName, className, devices))

        pyModule = self.my_import(pyModuleName)
        wishful_module_class = getattr(pyModule, className)
        for device in devices:
            wishfulModule = wishful_module_class(**kwargs)
        else:
            wishfulModule = wishful_module_class(**kwargs)

        return self.add_module_obj(moduleName, wishfulModule, devices)

    def find_upi_modules(self, cmdDesc):
        iface = None
        modules = []
        if cmdDesc.HasField('interface'):
            iface = cmdDesc.interface

        if iface:
            ifaceId = self.get_iface_id(str(iface))
            modules = self.iface_to_module_mapping[ifaceId]
        else:
            modules = self.modules_without_iface

        return modules

    def send_to_local_ctr_programs_manager(self, msgContainer):
        assert self.localControlProgramManager
        localControlProgramId = msgContainer[0]
        if localControlProgramId in self.localControlProgramManager.controlPrograms:
            localCP = self.localControlProgramManager.controlPrograms[
                localControlProgramId]
            localCP.recv_cmd_response(msgContainer)

    def send_cmd_to_module(self, msgContainer, localControllerId=None):
        cmdDesc = msgContainer[1]
        modules = self.find_upi_modules(cmdDesc)

        functionFound = False
        for module in modules:
            if cmdDesc.func_name in module.get_capabilities():
                functionFound = True
                retVal = module.send_to_module(msgContainer)
                if retVal and not localControllerId:
                    self.agent.send_upstream(retVal)
                elif retVal and localControllerId:
                    retVal[0] = localControllerId
                    self.agent.send_to_local_ctr_program(retVal)
                break

        if not functionFound:
            print("function not supported EXCEPTION",
                  cmdDesc.func_name, cmdDesc.interface)

    def send_cmd_to_module_blocking(self, msgContainer):
        cmdDesc = msgContainer[1]
        modules = self.find_upi_modules(cmdDesc)

        retVal = None
        functionFound = False
        for module in modules:
            if cmdDesc.func_name in module.get_capabilities():
                functionFound = True
                retVal = module.send_to_module(msgContainer)
                return retVal

        if not functionFound:
            print("function not supported EXCEPTION",
                  cmdDesc.func_name, cmdDesc.interface)

    def get_module(self, msgContainer):
        cmdDesc = msgContainer[1]
        modules = self.find_upi_modules(cmdDesc)

        myModule = None
        for module in modules:
            if cmdDesc.func_name in module.get_generators():
                myModule = module

        return myModule

    def get_generator(self, msgContainer):
        cmdDesc = msgContainer[1]
        modules = self.find_upi_modules(cmdDesc)

        myGenerator = None
        for module in modules:
            if cmdDesc.func_name in module.get_generators():
                myGenerator = getattr(module, cmdDesc.func_name)

        return myGenerator

    def get_capabilities(self):
        return {"modules": self.modules,
                "interfaces": self.interfaces,
                "iface_to_module_mapping": self.iface_to_module_mapping,
                "modules_without_iface": self.modules_without_iface}

    def is_upi_supported(self, iface, upi_type, fname):
        modules = []

        if iface:
            ifaceId = self.get_iface_id(str(iface))
            modules = self.iface_to_module_mapping[ifaceId]
        else:
            modules = self.modules_without_iface

        for module in modules:
            if fname in module.get_functions():
                return True

        # check if function is generator
        for module in modules:
            if fname in module.get_generators():
                raise Exception(
                    "UPI: {}:{} is generator,"
                    "please call with generator API".format(upi_type, fname))

        # check if function requires iface
        if iface:
            modules = self.modules_without_iface
            for module in modules:
                if fname in module.get_capabilities():
                    raise Exception(
                        "UPI function: {}:{} "
                        "cannot be called with iface".format(upi_type, fname))

        raise Exception("UPI function: {}:{} not "
                        "supported for iface: {}, "
                        "please install proper module".format(
                            upi_type, fname, iface))

        return False

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
