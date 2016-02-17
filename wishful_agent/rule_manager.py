import logging
import wishful_framework as wf

__author__ = "Piotr Gawlowicz, Anatolij Zubow"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "{gawlowicz, zubow}@tkn.tu-berlin.de"

class RuleManager(object):
    def __init__(self, agent):
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))
        self.agent = agent
        self.jobScheduler = agent.jobScheduler
        self.rules = {}
        self.id_generator = 0

    def generateId(self):
        self.id_generator = self.id_generator + 1
        return self.id_generator

    def add_rule(self, ruleDesc):
        ruleId = self.generateId()
        ruleObj = wf.Rule(self, ruleDesc)
        self.rules[ruleId] = ruleObj
        return ruleId

    def remove_rule(self, ruleId):
        if ruleId in self.rules:
            self.rules[ruleId].stop()
            del self.rules[ruleId]

    def execute_command(self, upi_type, msgContainter):
        module_name = self.agent.get_module_name_by_type(upi_type)[0]
        return self.agent.send_msg_to_module(module_name, msgContainter)

    def schedule_next_event(self, rule, execTime):
        self.agent.jobScheduler.add_job(rule.triggerEvent, 'date', run_date=execTime)

    def send_to_controller(self, msgContainter):
        pass