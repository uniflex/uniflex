import logging
import subprocess
import zmq.green as zmq
import random
import wishful_framework as msgs

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
        self.ifaceIdGen = 0
        
        self.discoveryModule = None
        self.localControlProgramManager = None

        self.modules = {}
        self.interfaces = {}
        self.iface_to_module_mapping = {}
        self.modules_without_iface = []


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
        for k,v in self.interfaces.items():
            if v == name:
                return k

        return None


    def add_module(self, moduleName, pyModuleName, className, interfaces, kwargs):
        self.log.debug("Add new module: {}:{}:{}:{}".format(moduleName, pyModuleName, className, interfaces))

        pyModule = self.my_import(pyModuleName)
        wishful_module_class = getattr(pyModule, className)

        #add single module, that do not need interface
        if interfaces == None:
            wishful_module = wishful_module_class(**kwargs)
            moduleId = self.generate_new_module_id()
            wishful_module.id = moduleId
            wishful_module.set_agent(self.agent)

            self.modules[moduleId] = wishful_module
            self.modules_without_iface.append(wishful_module)

            if moduleName == "discovery":
                self.discoveryModule = wishful_module
            elif pyModuleName == "wishful_module_local_control" and className == "LocalControlModule":
                self.localControlProgramManager = wishful_module

            return wishful_module

        #create and add module for each interface
        for iface in interfaces:
            #create interface dict (id:name)
            if iface not in list(self.interfaces.values()):
                iface_id = self.generate_new_iface_id()
                self.interfaces[iface_id] = str(iface)

            #create module object
            wishful_module = wishful_module_class(**kwargs)
            moduleId = self.generate_new_module_id()
            wishful_module.id = moduleId
            wishful_module.set_agent(self.agent)
            wishful_module.interface = iface

            self.modules[moduleId] = wishful_module

            #add module to interface's module list
            if not iface_id in self.iface_to_module_mapping:
                self.iface_to_module_mapping[iface_id] = [wishful_module]
            else:
                self.iface_to_module_mapping[iface_id].append(wishful_module)

        return wishful_module


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
            localCP = self.localControlProgramManager.controlPrograms[localControlProgramId]
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
            print("function not supported EXCEPTION", cmdDesc.func_name, cmdDesc.interface)

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
            print ("function not supported EXCEPTION", cmdDesc.func_name, cmdDesc.interface)


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