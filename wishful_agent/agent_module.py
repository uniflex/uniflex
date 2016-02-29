import logging
import zmq
import random
import sys
import time
import threading
import wishful_framework as msgs
try:
   import cPickle as pickle
except:
   import pickle

__author__ = "Piotr Gawlowicz, Mikolaj Chwalisz"
__copyright__ = "Copyright (c) 2015, Technische Universität Berlin"
__version__ = "0.1.0"
__email__ = "{gawlowicz, chwalisz}@tkn.tu-berlin.de"


class discover_controller(object):
    def __init__(self, ):
        self.discover_controller = True

    def __call__(self, f):
        f._discover_controller = self.discover_controller
        return f

class loop(object):
    def __init__(self, ):
        self.loop = True

    def __call__(self, f):
        f._loop = self.loop
        return f


class on_start(object):
    def __init__(self, ):
        self.onStart = True

    def __call__(self, f):
        f._onStart = self.onStart
        return f


class on_exit(object):
    def __init__(self):
        self.onExit = True

    def __call__(self, f):
        f._onExit = self.onExit
        return f


class on_connected(object):
    def __init__(self):
        self.onConnected = True

    def __call__(self, f):
        f._onConnected = self.onConnected
        return f


class on_disconnected(object):
    def __init__(self):
        self.onDisconnected = True

    def __call__(self, f):
        f._onDisconnected = self.onDisconnected
        return f


class bind_function(object):
    def __init__(self, upiFunc):
        fname = upiFunc.__name__
        self.upi_fname = set([fname])

    def __call__(self, f):
        f._upi_fname = self.upi_fname
        return f

def build_module(module_class):
    original_methods = module_class.__dict__.copy()
    for name, method in original_methods.iteritems():
        if hasattr(method, '_upi_fname'):
            #add UPI alias for the function
            for falias in method._upi_fname - set(original_methods):
                setattr(module_class, falias, method)
    return module_class


class AgentModule(object):
    def __init__(self):
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))

        self.id = None
        self.name = self.__class__.__name__
        self.capabilities = []

        #discover UPI function implementation and create upi_capabilities list
        func_name = [method for method in dir(self) if callable(getattr(self, method)) and hasattr(getattr(self, method), '_upi_fname')]
        self.upi_callbacks = {list(getattr(self, method)._upi_fname)[0] : method for method in func_name}
        self.upis_capabilities = self.upi_callbacks.keys()
        
        #interface to be used in UPI functions, it is set before function call
        self.interface = None


    def get_capabilities(self):
        return self.upis_capabilities


    def send_to_module(self, msgContainer):
        self.log.debug("Module {} received cmd".format(self.__class__.__name__))
        result = self.process_cmds(msgContainer)
        self.log.debug("Module {} return value".format(self.__class__.__name__))
        return result


    def get_controller(self):
        #discover controller discovery function
        funcs = [method for method in dir(self) if callable(getattr(self, method)) and hasattr(getattr(self, method), '_discover_controller')]
        fname = funcs[0]
        func = getattr(self, fname)
        if func:
            return func()
        else:
            return


    def execute_function(self, func):
        loop = hasattr(func, '_loop')
        if loop:
            self.threads = threading.Thread(target=func)
            self.threads.setDaemon(True)
            self.threads.start()
        else:
            func()


    def start(self):
        #discover all functions that have to be executen on start
        funcs = [method for method in dir(self) if callable(getattr(self, method)) and hasattr(getattr(self, method), '_onStart')]
        for fname in funcs:
            f = getattr(self, fname)
            self.execute_function(f)


    def exit(self):
        #discover all functions that have to be executen on exit
        funcs = [method for method in dir(self) if callable(getattr(self, method)) and hasattr(getattr(self, method), '_onExit')]
        for fname in funcs:
            f = getattr(self, fname)
            self.execute_function(f)


    def connected(self):
        #discover all functions that have to be executen on connected
        funcs = [method for method in dir(self) if callable(getattr(self, method)) and hasattr(getattr(self, method), '_onConnected')]
        for fname in funcs:
            f = getattr(self, fname)
            self.execute_function(f)


    def disconnected(self):
        #discover all functions that have to be executen on disconnected
        funcs = [method for method in dir(self) if callable(getattr(self, method)) and hasattr(getattr(self, method), '_onDisconnected')]
        for fname in funcs:
            f = getattr(self, fname)
            self.execute_function(f)


    def process_cmds(self, msgContainer):
        assert len(msgContainer) == 3
        group = msgContainer[0]
        cmdDesc = msgContainer[1]
        kwargs = msgContainer[2]
        
        self.log.debug("Process msg: {}:{}".format(cmdDesc.type, cmdDesc.func_name))
        command = cmdDesc.func_name

        #set interface before UPI function call, so we can use self.interface in function
        self.interface = None
        if cmdDesc.HasField('interface'):
            self.interface = cmdDesc.interface

        response = None
        #TODO: check if function is available
        func = getattr(self, command)

        my_args = ()
        if kwargs:
            my_args = kwargs['args']
            my_kwargs = kwargs['kwargs']

        retVal = func(*my_args)

        #TODO: add exception handling
        #try:
        #    retVal = func(*my_args)
        #except Exception as e:
        #    retVal = e

        if retVal is not None:
            group = None
            respDesc = msgs.CmdDesc()
            respDesc.type = cmdDesc.type
            respDesc.func_name = cmdDesc.func_name
            respDesc.call_id = cmdDesc.call_id
            
            #Serialize return value
            respDesc.serialization_type = msgs.CmdDesc.PICKLE
            serialized_retVal = pickle.dumps(retVal)
            response = [group, respDesc.SerializeToString(), serialized_retVal]

        return response