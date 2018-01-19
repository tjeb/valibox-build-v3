from .util import *

class Step():
    pass

class CmdStep(Step):
    def __init__(self, cmd, directory=None, may_fail=False, skip_if=None, conditional=None):
        self.directory = directory
        self.cmd = cmd
        self.may_fail = may_fail
        self.skip_if = skip_if
        self.conditional = conditional

    def __str__(self):
        if self.directory is not None:
            step_str = "in %s: %s" % (self.directory, self.cmd)
        else:
            step_str = "in current dir: %s" % (self.cmd)
        if self.conditional is not None:
            return "%s\n\t%s" % (self.conditional, step_str)
        else:
            return step_str

    def perform(self):
        if self.skip_if is not None and self.skip_if:
            return True

        if self.conditional is not None:
            if self.conditional.perform():
                return True

        if self.directory is not None:
            with gotodir(self.directory):
                return basic_cmd(self.cmd, may_fail=self.may_fail)
        else:
            return basic_cmd(self.cmd, may_fail=self.may_fail)

class UpdateFeedsConf(Step):
    line_to_add = "src-link sidn ../sidn_openwrt_pkgs\n"

    def __init__(self, directory):
        self.directory = directory

    def __str__(self):
        return "in %s: add %s to feeds.conf" % (self.directory, self.line_to_add)

    def perform(self):
        with gotodir(self.directory):
            with open("feeds.conf", "w") as out_file:
                with open("feeds.conf.default", "r") as in_file:
                    for line in in_file.readlines():
                        out_file.write(line)
                    out_file.write(self.line_to_add)
        return True
