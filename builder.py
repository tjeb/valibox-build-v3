#!/usr/bin/python3

#
# build tool helper
#

# There are many moving parts, and while building one release
# for one specific architecture isn't that hard, we need to
# be able to build images based on different branches from different
# sources, etc.
#

# by default, present the options

import argparse
import os
import subprocess
import shlex
import configparser
import collections
import sys

#
# General utility classes and functions
#
class gotodir:
    def __init__(self, directory):
        self.go_to_dir = directory
        self.orig_dir = None

    def __enter__(self):
        self.orig_dir = os.getcwd()
        os.chdir(self.go_to_dir)
        return self

    def __exit__(self, *args):
        if self.orig_dir is not None:
            os.chdir(self.orig_dir)

def basic_cmd(cmd, may_fail = False):
    print("Running: %s" % cmd)
    rcode = subprocess.call(shlex.split(cmd))
    if may_fail:
        return True
    else:
        return rcode == 0

def basic_cmd_output(cmd):
    p = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE)
    (stdout, _) = p.communicate()
    return stdout.decode("utf-8").join("\n")

def _find_getch():
    try:
        import termios
    except ImportError:
        # Non-POSIX. Return msvcrt's (Windows') getch.
        import msvcrt
        return msvcrt.getch

    # POSIX system. Create and return a getch that manipulates the tty.
    import sys, tty
    def _getch():
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

    return _getch

getch = _find_getch()

#
# Helper functions for dealing with git repositories
#
class Step():
    pass

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

#
# Helper functions for dealing with copying files
#
class Config:
    CONFIG_FILE = ".valibox_build_config"

    # format: section, name, default

    DEFAULTS = collections.OrderedDict((
        ('main', collections.OrderedDict((
            ('LEDE branch', 'master'),
            ('sidn_openwrt_packages branch', 'master'),
            ('local SPIN code', False),
            ('Update all feeds', False),
            ('use make -j1 V=s', False),
            ('target architecture', 'all')
        ))),
        ('SPIN', collections.OrderedDict((
                    ('foo', 'bar'),
        ))),
    ))

    def __init__(self):
        self.config = configparser.SafeConfigParser(dict_type=collections.OrderedDict)
        self.config.read_dict(self.DEFAULTS)
        self.config.read(self.CONFIG_FILE)

    def save_config(self):
        with open(self.CONFIG_FILE, 'w') as configfile:
            self.config.write(configfile)

    def show_main_options(self):
        for option, value in self.config['main'].items():
            print("%s: %s" % (option, value))

    def get(self, section, option):
        return self.config.get(section, option)

# read or create the config
def check_config():
    pass

# build a full list of steps from the set configuration
def build_steps(config):
    # When to use if here and when to use a Conditional class:
    # If the condition can be determined statically (like, say, from
    # the config), then use if here.
    # If it has to be determined dynamically (like, say, which branch was
    # checked out, or data from a file that may need to be created in
    # an earlier step) use a Conditional

    steps = []
    steps.append(CmdStep("git clone https://github.com/lede-project/source lede-source",
                         conditional=DirExistsConditional('lede-source')
    ))
    steps.append(CmdStep("git clone https://github.com/SIDN/sidn_openwrt_pkgs",
                         conditional=DirExistsConditional('sidn_openwrt_pkgs')
    ))
    steps.append(CmdStep("git clone https://github.com/SIDN/spin",
                         conditional=DirExistsConditional('spin')
    ))
    branch = config.get("main", "SPIN branch")
    steps.append(CmdStep("git checkout %s" % branch, "spin",
                         conditional=CmdOutputConditional('git rev-parse --abbrev-ref HEAD', branch, True, 'spin')
                ))
    steps.append(CmdStep("git pull", "spin"))
    steps.append(UpdateFeedsConf("lede-source"))
    if config.get('main', 'Update all feeds'):
        steps.append(CmdStep("./scripts/feeds update -a", "lede-source"))
        steps.append(CmdStep("./scripts/feeds install -a", "lede-source"))
    target_arch = config.get('main', 'target architecture')
    if target_arch == 'all':
        targets = [ 'gl-ar150', 'gl-mt300a', 'gl-6416' ]
    else:
        targets = [ target_arch ]
    for target in targets:
        steps.append(CmdStep("cp -r ../../valibox_build_tools/arch/%s/files ./files" % target, "lede-source"))
        steps.append(CmdStep("cp ../../valibox_build_tools/arch/%s/diffconfig ./.config" % target, "lede-source"))
        steps.append(CmdStep("make defconfig", "lede-source"))
        steps.append(CmdStep("make", "lede-source"))
    return steps

def print_steps(steps):
    i = 1
    for s in steps:
        print("%s:\t%s" % (i, s))
        i += 1

def perform_steps(steps, last_step):
    failed_step = None
    for step in steps[last_step - 1:]:
        with open(".last_step", "w") as out:
            out.write("%d\n" % last_step)
        print("step %d: %s" % (last_step, step))
        if not step.perform():
            print("step %d FAILED: %s" % (last_step, step))
            return last_step
        last_step += 1

def show_help():
    print("[s] show all steps for the current configuration")
    print("[e] edit the configuration")
    print("[q] quit")
    print("[c] continue the build process from last time")
    print("[b] start the build process from the first step")
    print("[?] show this help")

def get_user_command():
    sys.stdout.write("[seqcb?]\n")
    c = getch()
    return c

def main():
    #check_config()
    #perform_steps(steps)
    config = Config()
    config.show_main_options()
    steps = build_steps(config)

    failed_step = None
    last_step = 1
    if os.path.exists("./.last_step"):
        with open(".last_step") as inf:
            line = inf.readline()
            last_step = int(line)
    if last_step != 1:
        print("Last run did not finish; last step was %d, use [c] to continue from this step" % last_step)
        print("Step was %d:\t%s" % (last_step, steps[last_step-1]))

    while True:
        c = get_user_command()
        if c == 'q':
            sys.exit(0)
            break
        elif c == 's':
            print_steps(steps)
        elif c == 'c':
            failed_step = perform_steps(steps, last_step)
            if failed_step is not None:
                print("[ERROR] step %d failed" % failed_step)
                print("%s" % steps[failed_step-1])
            else:
                if os.path.exists(".last_step"):
                    os.remove(".last_step")
            break
        elif c == 'b':
            last_step = 1
            failed_step = perform_steps(steps, last_step)
            if failed_step is not None:
                print("[ERROR] step %d failed" % failed_step)
                print("%s" % steps[failed_step-1])
            else:
                if os.path.exists(".last_step"):
                    os.remove(".last_step")
            break
        elif c == '?':
            show_help()
        else:
            print("Unknown command: %s\n" % c)
    #config.save_config()


if __name__ == "__main__":
    main()
