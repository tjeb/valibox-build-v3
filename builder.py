#!/usr/bin/python3

#
# build tool helper
#

# There are many moving parts, and while building one release
# for one specific architecture isn't that hard, we need to
# be able to build images based on different branches from different
# sources, etc.
#
# This toolkit was created to unify the multiple scripts we had to
# build the images
#

# Todo:
# - maybe split up into several minitools?
#   e.g. 'create-config, show-config, show-commands, run/continue'?
#   and/or curses based setup?
# start with command line tools

import argparse
import os
import subprocess
import shlex
import configparser
import collections
import sys

from valibox_builder.util import *
from valibox_builder.conditionals import *
from valibox_builder.steps import *

#
# Helper functions for dealing with copying files
#
class BuildConfig:
    CONFIG_FILE = ".valibox_build_config"

    # format: section, name, default

    DEFAULTS = collections.OrderedDict((
        ('main', collections.OrderedDict((
            ('LEDE branch', 'master'),
            ('sidn_openwrt_packages branch', 'master'),
            ('SPIN branch', 'master'),
            ('local SPIN code', False),
            ('Update all feeds', False),
            ('asdf', False),
            ('target architecture', 'all')
        ))),
        ('SPIN', collections.OrderedDict((
                    ('foo', 'bar'),
        ))),
    ))

    def __init__(self, config_file):
        if config_file is not None:
            self.config_file = config_file
        else:
            self.config_file = BuildConfig.CONFIG_FILE
        self.config = configparser.SafeConfigParser(dict_type=collections.OrderedDict)
        self.config.read_dict(self.DEFAULTS)
        self.config.read(self.config_file)

    def save_config(self):
        with open(self.config_file, 'w') as configfile:
            self.config.write(configfile)

    def show_main_options(self):
        for option, value in self.config['main'].items():
            print("%s: %s" % (option, value))

    def get(self, section, option):
        return self.config.get(section, option)

class Builder:
    """
    This class creates and performs the actual steps in the configured
    build process
    """
    def __init__(self, builder_config):
        self.config = builder_config
        self.steps = []
        self.build_steps()
        self.read_last_step()

    def read_last_step(self):
        self.last_step = None
        if os.path.exists("./.last_step"):
            with open(".last_step") as inf:
                line = inf.readline()
                self.last_step = int(line)

    def get_last_step(self):
        return self.last_step

    # read or create the config
    def check_config():
        pass

    # build a full list of steps from the set configuration
    def build_steps(self):
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
        branch = self.config.get("main", "SPIN branch")
        steps.append(CmdStep("git checkout %s" % branch, "spin",
                             conditional=CmdOutputConditional('git rev-parse --abbrev-ref HEAD', branch, True, 'spin')
                    ))
        steps.append(CmdStep("git pull", "spin"))
        steps.append(UpdateFeedsConf("lede-source"))
        if self.config.get('main', 'Update all feeds'):
            steps.append(CmdStep("./scripts/feeds update -a", "lede-source"))
            steps.append(CmdStep("./scripts/feeds install -a", "lede-source"))
        target_arch = self.config.get('main', 'target architecture')
        if target_arch == 'all':
            targets = [ 'gl-ar150', 'gl-mt300a', 'gl-6416' ]
        else:
            targets = [ target_arch ]
        for target in targets:
            valibox_build_tools_dir = get_valibox_build_tools_dir()
            steps.append(CmdStep("cp -r ../%s/devices/%s/files ./files" % (valibox_build_tools_dir, target), "lede-source"))
            steps.append(CmdStep("cp ../%s/devices/%s/diffconfig ./.config" % (valibox_build_tools_dir, target), "lede-source"))
            steps.append(CmdStep("make defconfig", "lede-source"))
            steps.append(CmdStep("make", "lede-source"))

        self.steps = steps

    def print_steps(self):
        i = 1
        for s in self.steps:
            print("%s:\t%s" % (i, s))
            i += 1

    def save_last_step(self):
        with open(".last_step", "w") as out:
            out.write("%d\n" % self.last_step)

    def perform_steps(self):
        failed_step = None
        if self.last_step is None:
            self.last_step = 1
        for step in self.steps[self.last_step - 1:]:
            self.save_last_step()
            print("step %d: %s" % (self.last_step, step))
            if not step.perform():
                print("step %d FAILED: %s" % (self.last_step, step))
                return self.last_step
            self.last_step += 1

def get_valibox_build_tools_dir():
    return os.path.dirname(__file__)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--build', action="store_true", help='Start or continue the build from the latest step in the last run')
    parser.add_argument('-r', '--restart', action="store_true", help='(Re)start the build from the first step')
    parser.add_argument('-e', '--edit', action="store_true", help='Edit the build configuration options')
    parser.add_argument('-c', '--config', default=BuildConfig.CONFIG_FILE, help="Specify the build config file to use (defaults to %s)" % BuildConfig.CONFIG_FILE)
    #parser.add_argument('--check', action="store_true", help='Check the build configuration options')
    parser.add_argument('--print-steps', action="store_true", help='Print all the steps that would be performed')
    args = parser.parse_args()

    config = BuildConfig(args.config)
    builder = Builder(config)

    if args.build:
        builder.perform_steps()
    elif args.restart:
        builder.last_step = 1
        builder.perform_steps()
    elif args.edit:
        EDITOR = os.environ.get('EDITOR','vim') #that easy!
        config.save_config()
        subprocess.call([EDITOR, config.config_file])
    elif args.print_steps:
        print("steps:")
        builder.print_steps()
    else:
        parser.print_help()


    #do_build()

if __name__ == "__main__":
    main()
