import logging
from enum import IntEnum

from uniflex.core import modules

__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2017, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "gawlowicz@tkn.tu-berlin.de"


# ACID
# atomicity: execute all commands in transaction or any
# - some commands like send_packet() cannot be reverted, we have two categories revertable and unrevertable
# consistency: allow only valid data (if int required do not allow string), difficult in python
# - if connection to controller is broken after commit, revert the commit
# - if controller can reach some nodes and some not it also reverts the transaction
# isolation: lock all entities on can_commit, only single controller can send commands
# durability: dump commands to file so they can survice the reboot (node crush)

class TransactionStatus(IntEnum):
    EMPTY = 1
    COMMITED = 2
    ROLLED_BACK = 3
    SUCCESS = 4


class Transaction(object):
    """docstring for Transaction"""
    def __init__(self):
        super(Transaction, self).__init__()
        self.tasks = []
        self.rollbackIfConnectionLost_ = False
        self.connectionLostTimeout = 0

        self.transactionStatus = TransactionStatus.EMPTY

        self.entities = []

    def add_task(self, task):
        self.tasks.append(task)

    def _sort_tasks_by_entity(self):
        pass

    def _can_commit(self):
        # check if all nodes are ready for commit
        return True

    def _pre_commit(self):
        # deliver tasks to all nodes
        return True

    def _do_commit(self):
        # execute commit
        # schedule this call to be executed in few seconds
        # it is required in case of inband control
        return True

    def _rollback(self):
        # rollback last commit
        return True

    def rollback_if_connection_lost(self, value, timeout):
        self.rollbackIfConnectionLost_ = value
        self.connectionLostTimeout = timeout

    def commit(self):
        self.transactionStatus = TransactionStatus.COMMITED

        self._sort_tasks_by_entity()

        try:
            # all steps can raise an exception
            self._can_commit()
            self._pre_commit()
            self._do_commit()
            self.transactionStatus = TransactionStatus.SUCCESS

        except Exception as e:
            self._rollback()
            self.transactionStatus = TransactionStatus.ROLLED_BACK
            return

    def get_status(self):
        return self.transactionStatus

    def is_executed(self):
        if self.transactionStatus == TransactionStatus.SUCCESS:
            return True
        else:
            return False

    def is_rolled_back(self):
        if self.transactionStatus == TransactionStatus.ROLLED_BACK:
            return True
        else:
            return False


class EntityTasks(object):
    """docstring for EntityTasks"""
    def __init__(self):
        super(EntityTasks, self).__init__()
        self.entity = None
        self.tasks = []


class Task(object):
    """docstring for Task"""
    def __init__(self):
        super(Task, self).__init__()
        self.entities = []
        self.save_point = {}
        self.function = {}

    def set_entities(self, entities):
        self.entities = entities

    def set_save_point_func(self, func, args=[]):
        self.save_point["function"] = func
        self.save_point["args"] = args

    def set_save_point_value(self, args=[]):
        self.save_point["args"] = args

    def set_function(self, func, args=[]):
        self.function["function"] = func
        self.function["args"] = args


class TransactionModule(modules.ControlApplication):
    def __init__(self):
        super(TransactionModule, self).__init__()
        self.log = logging.getLogger('TransactionModule')
        self.state = None
        self.tasks = []

        # check if journal file exist, if so, load and execute commands

    def rx_can_commit(self):
        pass

    def rx_pre_commit(self):
        pass

    def rx_do_commit(self):
        pass
