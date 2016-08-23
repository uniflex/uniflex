import uuid
import logging

from .common import get_ip_address  # TODO: remove ip or iface
from .module_manager import ModuleManager
from .transport_channel import SlaveTransportChannel
from .transport_channel import MasterTransportChannel
from .executor import CommandExecutor

__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "gawlowicz@tkn.tu-berlin.de"


class Agent(object):
    def __init__(self):
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))

        self.config = None
        self.uuid = str(uuid.uuid4())
        self.name = None
        self.info = None
        self.iface = None
        self.ip = None

        self.moduleManager = ModuleManager(self)

        # command executor with scheduler
        self.moduleManager.add_module_obj(
            "command_executor", CommandExecutor(self))

        # extention of event bus
        self.transport = None

    def set_agent_info(self, name=None, info=None, iface=None, ip=None):
        self.name = name
        self.info = info
        self.iface = iface
        self.ip = ip

        if self.ip is None and self.iface:
            self.ip = get_ip_address(self.iface)

    def add_module(self, moduleName, pyModule, className,
                   device=None, kwargs={}):

        return self.moduleManager.register_module(
            moduleName, pyModule, className, device, kwargs)

    def load_config(self, config):
        self.log.debug("Config: {0}".format(config))

        agent_info = config['agent_config']

        if 'name' in agent_info:
            self.name = agent_info['name']

        if 'info' in agent_info:
            self.info = agent_info['info']

        if 'iface' in agent_info:
            self.iface = agent_info['iface']
            self.ip = get_ip_address(self.iface)

        if 'type' in agent_info:
            self.agentType = agent_info['type']

        dl = None
        ul = None
        if "dl" in agent_info:
            dl = agent_info["dl"]
        if "downlink" in agent_info:
            dl = agent_info["downlink"]
        if "ul" in agent_info:
            ul = agent_info["ul"]
        if "uplink" in agent_info:
            ul = agent_info["uplink"]

        if self.agentType == 'master':
            self.transport = MasterTransportChannel(self)
            self.moduleManager.add_module_obj(
                "transport_channel", self.transport)
            self.transport.set_downlink(dl)
            self.transport.set_uplink(ul)

        elif self.agentType == 'slave':
            self.transport = SlaveTransportChannel(self)
            self.moduleManager.add_module_obj(
                "transport_channel", self.transport)
        else:
            self.transport = None

        # load control programs
        controllers = config['controllers']
        for controllerName, params in controllers.items():
            pyModuleName = params['module']
            pyClassName = params['class_name']
            kwargs = {}
            if 'kwargs' in params:
                kwargs = params['kwargs']

            self.moduleManager.register_module(
                controllerName, pyModuleName, pyClassName,
                None, kwargs)

        # load modules
        moduleDesc = config['modules']
        for moduleName, m_params in moduleDesc.items():

            controlled_devices = []
            if 'devices' in m_params:
                controlled_devices = m_params['devices']

            kwargs = {}
            if 'kwargs' in m_params:
                kwargs = m_params['kwargs']

            pyModuleName = m_params['module']
            className = m_params['class_name']

            if controlled_devices:
                for device in controlled_devices:
                    self.moduleManager.register_module(
                        moduleName, pyModuleName, className,
                        device, kwargs)
            else:
                self.moduleManager.register_module(
                    moduleName, pyModuleName, className,
                    None, kwargs)

    def run(self):
        self.log.debug("Agent starts all modules".format())
        # nofity START to modules
        self.moduleManager.start()

    def stop(self):
        self.log.debug("Stop all modules")
        # nofity EXIT to modules
        self.moduleManager.exit()
