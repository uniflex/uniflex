import logging
import subprocess
import zmq.green as zmq
import random

__author__ = "Piotr Gawlowicz, Mikolaj Chwalisz"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "{gawlowicz, chwalisz}@tkn.tu-berlin.de"

class AgentModule(object):
    def __init__(self, name, path, args):
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))
        self.name = name
        self.path = path
        self.args = args
        self.port = None

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

        self.log.debug("Server for {0} started on port: {1} ".format(self.name, self.port))

    def start_module_process(self):
        cmd = [self.path,
               '--port', str(self.port)
               ]
        cmd.extend(filter(None, self.args))
        self.pid = subprocess.Popen(cmd)
        self.log.debug("Module: {0}, with args: {1}, PID: {2} started".format(self.name, self.args, self.pid.pid))

    def kill_module_subprocess(self):
        self.pid.kill()
        pass


    def send_msg_to_module(self, msgContainer):
        self.log.debug("Module: {0} sends msg".format(self.name))
        self.socket.send_multipart(msgContainer)