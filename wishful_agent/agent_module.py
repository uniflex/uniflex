import logging
import subprocess
import zmq.green as zmq
import random

__author__ = "Piotr Gawlowicz, Mikolaj Chwalisz"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "{gawlowicz, chwalisz}@tkn.tu-berlin.de"

#TODO: create base class

class AgentInProcModule(object):
    def __init__(self, name, py_module_name, class_name, interfaces):
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))
        self.name = name
        self.class_name = class_name
        py_module = self.my_import(py_module_name)
        self.module = getattr(py_module, class_name)()
        self.socket = None #mockup
        self.interfaces = interfaces
        self.capabilities = []

    def my_import(self, module_name):
        pyModule = __import__(module_name)
        globals()[module_name] = pyModule
        return pyModule

    def send_msg_to_module(self, msgContainer):
        self.log.debug("InProcModule: {} sends msg".format(self.name))
        result = self.module.process_cmds(msgContainer)
        self.log.debug("InProcModule: {} return msgContainter".format(self.name))
        return result

    def exit(self):
        #mockup function
        pass


class AgentModule(object):
    def __init__(self, name, path, args, interfaces):
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))
        self.name = name
        self.path = path
        self.args = args
        self.port = None
        self.interfaces = interfaces
        self.capabilities = []

        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PAIR)

        self.start_server_for_module()
        self.start_module_process()
        pass

    def start_server_for_module(self):

        self.port = random.randint(5000, 10000)
        while True:
            try:
                self.socket.bind("tcp://*:%s" % self.port)
                break
            except:
                self.port = random.randint(5000, 10000)

        self.log.debug("Server for {} started on port: {} ".format(self.name, self.port))

    def start_module_process(self):
        cmd = [self.path,
               '--port', str(self.port)
               ]
        cmd.extend(filter(None, self.args))
        self.pid = subprocess.Popen(cmd)
        self.log.debug("Module: {}, with args: {}, PID: {} started".format(self.name, self.args, self.pid.pid))

    def exit(self):
        self.pid.kill()
        pass


    def send_msg_to_module(self, msgContainer):
        self.log.debug("OutProcModule: {} sends msg".format(self.name))
        self.socket.send_multipart(msgContainer)
        return None