#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import logging
from uniflex.core import exceptions

__author__ = "Zubow"
__copyright__ = "Copyright (c) 2015, Technische Universität Berlin"
__version__ = "0.1.0"
__email__ = "{zubow}@tkn.tu-berlin.de"

log = logging.getLogger('uniflex_test.main')


def main():

    log.info('Starting testing excpetions')
    log.info('%s' % str(dir()))
    try:
        raise exceptions.AgentNotAvailable(id='123')
    except exceptions.UniFlexException as we:
        print(we)

    try:
        raise exceptions.InvalidArgumentException(
            func_name='radio.get_noise')
    except exceptions.UniFlexException as we:
        print(we)

    try:
        raise exceptions.UnsupportedFunctionException(
            func_name='radio.get_noise', conn_module='wifi_ath9k')
    except exceptions.UniFlexException as we:
        print(we)

    try:
        raise exceptions.SchedulingFunctionCallsInThePastException(
            func_name='radio.get_noise')
    except exceptions.UniFlexException as we:
        print(we)

    try:
        raise exceptions.FunctionExecutionFailedException(
            func_name='radio.get_noise', err_msg='wrong iw version')
    except exceptions.UniFlexException as we:
        print(we)


if __name__ == "__main__":

    log_level = logging.INFO  # default
    logging.basicConfig(level=log_level,
        format='%(asctime)s - %(name)s.%(funcName)s() - %(levelname)s - %(message)s')
    try:
        main()
    except Exception as e:
        log.error(e)
    finally:
        log.debug("Exit")
