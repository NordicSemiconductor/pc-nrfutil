from Queue import Empty
import logging
import os
import time
import sys

from click.testing import CliRunner
from behave import then, given, when

from nordicsemi.__main__ import cli, int_as_text_to_int


logger = logging.getLogger(__file__)

STDOUT_TEXT_WAIT_TIME = 50  # Number of seconds to wait for expected output from stdout


@given(u'user types \'{command}\'')
def step_impl(context, command):
    args = command.split(' ')
    assert args[0] == 'nrfutil'

    exec_args = args[1:]

    runner = CliRunner()
    context.runner = runner
    context.args = exec_args


@then(u'output contains \'{stdout_text}\' and exit code is {exit_code}')
def step_impl(context, stdout_text, exit_code):
    result = context.runner.invoke(cli, context.args)
    logger.debug("exit_code: %s, output: \'%s\'", result.exit_code, result.output)
    assert result.exit_code == int_as_text_to_int(exit_code)
    assert result.output != None
    assert result.output.find(stdout_text) >= 0