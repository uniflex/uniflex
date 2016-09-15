import sys
import uuid
import logging

from .common import get_ip_address  # TODO: remove ip or iface
from .module_manager import ModuleManager
from .transport_channel import TransportChannel
from .node_manager import NodeManager
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

        # node manager
        self.nodeManager = NodeManager(self)
        self.moduleManager.add_module_obj(
            "node_manager", self.nodeManager)

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

    def load_config(self, config, configPath=None):
        self.log.debug("Config: {}, path: {}".format(config, configPath))

        if configPath:
            sys.path.append(configPath)

        agent_config = config['agent_config']

        if 'name' in agent_config:
            self.name = agent_config['name']

        if 'info' in agent_config:
            self.info = agent_config['info']

        if 'iface' in agent_config:
            self.iface = agent_config['iface']
            self.ip = get_ip_address(self.iface)

        if 'type' in agent_config:
            self.agentType = agent_config['type']

        dl = None
        ul = None
        if "dl" in agent_config:
            dl = agent_config["dl"]
        if "downlink" in agent_config:
            dl = agent_config["downlink"]
        if "ul" in agent_config:
            ul = agent_config["ul"]
        if "uplink" in agent_config:
            ul = agent_config["uplink"]

        if self.agentType is not 'local':
            self.transport = TransportChannel(self)
            self.moduleManager.add_module_obj(
                "transport_channel", self.transport)
            self.transport.set_downlink(dl)
            self.transport.set_uplink(ul)
            self.transport._nodeManager = self.nodeManager
            self.nodeManager._transportChannel = self.transport

        self.nodeManager.create_local_node(self)

        # load control programs
        if "controllers" in config:
            controllers = config['controllers']
            for controllerName, params in controllers.items():
                pyModuleName = params.get('module', None)
                if not pyModuleName:
                    myfile = params.get('file', None)
                    pyModuleName = myfile.split('.')[0]
                pyClassName = params['class_name']
                kwargs = {}
                if 'kwargs' in params:
                    kwargs = params['kwargs']

                self.moduleManager.register_module(
                    controllerName, pyModuleName, pyClassName,
                    None, kwargs)

        # load modules
        if "modules" in config:
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
