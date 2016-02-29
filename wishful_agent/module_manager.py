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
        for module in self.modules.values():
            module.start()


    def exit(self):
        self.log.debug("Notify EXIT to modules".format())
        for module in self.modules.values():
            module.exit()


    def connected(self):
        self.log.debug("Notify CONNECTED to modules".format())
        for module in self.modules.values():
            module.connected()

    def disconnected(self):
        self.log.debug("Notify DISCONNECTED to modules".format())
        for module in self.modules.values():
            module.disconnected()


    def get_iface_id(self, name):
        for k,v in self.interfaces.iteritems():
            if v == name:
                return k

        return None


    def add_module(self, moduleName, pyModuleName, className, interfaces):
        self.log.debug("Add new module: {}:{}:{}:{}".format(moduleName, pyModuleName, className, interfaces))

        moduleId = self.generate_new_module_id()

        pyModule = self.my_import(pyModuleName)
        wishful_module = getattr(pyModule, className)()
        wishful_module.id = moduleId

        self.modules[moduleId] = wishful_module

        if moduleName == "discovery":
            self.discoveryModule = wishful_module

        if interfaces == None:
            self.modules_without_iface.append(wishful_module)
            return 

        for iface in interfaces:
            if iface not in self.interfaces.values():
                iface_id = self.generate_new_iface_id()
                self.interfaces[iface_id] = str(iface)

            if not iface_id in self.iface_to_module_mapping:
                self.iface_to_module_mapping[iface_id] = [wishful_module]
            else:
                self.iface_to_module_mapping[iface_id].append(wishful_module)


    def send_cmd_to_module(self, msgContainer):
        cmdDesc = msgContainer[1]

        iface = None
        if cmdDesc.HasField('interface'):
            iface = cmdDesc.interface

        #find UPI module
        if iface:
            ifaceId = self.get_iface_id(str(iface))
            print ifaceId
            modules = self.iface_to_module_mapping[ifaceId]
        else:
            modules = self.modules_without_iface

        functionFound = False
        for module in modules:
            if cmdDesc.func_name in module.get_capabilities():
                functionFound = True
                retVal = module.send_to_module(msgContainer)
                if retVal:
                    self.agent.send_to_controller(retVal)
                break
        
        if not functionFound:
            print "function not supported EXCEPTION", cmdDesc.func_name, cmdDesc.interface