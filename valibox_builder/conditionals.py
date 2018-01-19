import os
from .util import *

# If a conditional's perform() returns True, skip the step it is attached to
# unless skip_if_false is True
class CmdOutputConditional:
    def __init__(self, cmd, expected, skip_if_false=False, directory=None):
        self.cmd = cmd
        self.expected = expected
        self.skip_if_false = skip_if_false
        self.directory = directory

    def perform(self):
        if self.directory is None:
            output = basic_cmd_output(cmd)
        else:
            with gotodir(self.directory):
                output = basic_cmd_output(self.cmd)
        if self.skip_if_false:
            return output != self.expected
        else:
            return output == expected

    def __str__(self):
        return "IF '%s' is %s'%s'" % (self.cmd, "not " if self.skip_if_false else "", self.expected)

class DirExistsConditional:
    def __init__(self, directory):
        self.directory = directory

    def perform(self):
        return os.path.exists(self.directory)

    def __str__(self):
        return "IF directory %s does not exist" % self.directory
