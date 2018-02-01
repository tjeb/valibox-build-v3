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
import configparser
import collections
import datetime
import sys

from valibox_builder.util import *
from valibox_builder.conditionals import *
from valibox_builder.steps import *


class BuildConfig:
    CONFIG_FILE = ".valibox_build_config"

    # format: section, name, default

    DEFAULTS = collections.OrderedDict((
        ('main', collections.OrderedDict((
        ))),
        ('LEDE', collections.OrderedDict((
                    ('update_git', True),
                    ('source_branch', 'lede-17.01'),
                    ('target_device', 'all'),
                    ('update_all_feeds', False),
                    ('verbose_build', False),
        ))),
        ('sidn_openwrt_pkgs', collections.OrderedDict((
                    ('update_git', True),
                    ('source_branch', 'release-1.4'),
        ))),
        ('SPIN', collections.OrderedDict((
                    ('local', False),
                    ('update_git', True),
                    ('source_branch', 'master'),
        ))),
        ('Release', collections.OrderedDict((
                    ('create_release', False),
                    ('version_string', '1.5'),
                    ('changelog_file', ''),
                    ('target_directory', 'valibox_release'),
                    ('beta', True),
                    ('file_suffix', "")
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

    def getboolean(self, section, option):
        return self.config.getboolean(section, option)


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


        #
        # Basic repository checkouts
        #
        steps = []
        if self.config.getboolean("LEDE", "update_git"):
            steps.append(CmdStep("git clone https://github.com/lede-project/source lede-source",
                                 conditional=DirExistsConditional('lede-source')
            ))
            branch = self.config.get("LEDE", "source_branch")
            steps.append(CmdStep("git fetch", "lede-source"))
            steps.append(CmdStep("git checkout %s" % branch, "lede-source",
                                 conditional=CmdOutputConditional('git rev-parse --abbrev-ref HEAD', branch, False, 'lede-source')
                        ))
            steps.append(CmdStep("git pull", "lede-source"))

        sidn_pkg_feed_dir = "sidn_openwrt_pkgs"
        if self.config.getboolean("sidn_openwrt_pkgs", "update_git"):
            steps.append(CmdStep("git clone https://github.com/SIDN/sidn_openwrt_pkgs %s" % sidn_pkg_feed_dir,
                                 conditional=DirExistsConditional('sidn_openwrt_pkgs')
            ))
            steps.append(CmdStep("git fetch", "sidn_openwrt_pkgs"))
            branch = self.config.get("sidn_openwrt_pkgs", "source_branch")
            steps.append(CmdStep("git checkout %s" % branch, "sidn_openwrt_pkgs",
                                 conditional=CmdOutputConditional('git rev-parse --abbrev-ref HEAD', branch, False, 'sidn_openwrt_pkgs')
                        ))
            steps.append(CmdStep("git pull", "lede-source"))
        # If we build SPIN locally, we need to check it out as well (
        # (and perform magic with the sidn_openwrt_pkgs checkout)
        if self.config.getboolean("SPIN", "local"):
            if self.config.getboolean("SPIN", "update_git"):
                steps.append(CmdStep("git clone https://github.com/SIDN/spin",
                                     conditional=DirExistsConditional('spin')
                ))
                # only relevant if we use a local build of spin (TODO)
                steps.append(CmdStep("git fetch", "spin"))
                # TODO: make a SelectGitBranch step?
                branch = self.config.get("SPIN", "source_branch")
                steps.append(CmdStep("git checkout %s" % branch, "spin",
                                     conditional=CmdOutputConditional('git rev-parse --abbrev-ref HEAD', branch, False, 'spin')
                            ))
                steps.append(CmdStep("git pull", "spin", may_fail=True))

            # Create a local release tarball from the checkout, and
            # update the PKGHASH and location in the package feed data
            # TODO: there are a few hardcoded values assumed here and in the next few steps
            steps.append(CmdStep("./create_tarball.sh -n", directory="spin"))
            steps.append(CmdStep("rm -f dl/spin-0.6-beta.tar.gz", directory="lede-source"))

            # Set that in the pkg feed data; we do not want to change the repository, so we make a copy and update that
            orig_sidn_pkg_feed_dir = sidn_pkg_feed_dir
            sidn_pkg_feed_dir = sidn_pkg_feed_dir + "_local"
            print("[XX] COPYING FEEDS SOURCE FROM '%s' TO '%s'" % (orig_sidn_pkg_feed_dir,sidn_pkg_feed_dir))
            #steps.append(CmdStep("cp -rf %s %s" % (orig_sidn_pkg_feed_dir, sidn_pkg_feed_dir)))
            steps.append(CmdStep("git checkout-index -a -f --prefix=../%s/" % sidn_pkg_feed_dir, orig_sidn_pkg_feed_dir))

            steps.append(UpdatePkgMakefile(sidn_pkg_feed_dir, "spin/Makefile", "/tmp/spin-0.6-beta.tar.gz"))

        steps.append(UpdateFeedsConf("lede-source", sidn_pkg_feed_dir))
        if self.config.getboolean('LEDE', 'update_all_feeds'):
            steps.append(CmdStep("./scripts/feeds update -a", "lede-source"))
            steps.append(CmdStep("./scripts/feeds install -a", "lede-source"))
        else:
            steps.append(CmdStep("./scripts/feeds update sidn", "lede-source"))
            steps.append(CmdStep("./scripts/feeds install -a -p sidn", "lede-source"))
        target_device = self.config.get('LEDE', 'target_device')
        if target_device == 'all':
            targets = [ 'gl-ar150', 'gl-mt300a', 'gl-6416' ]
        else:
            targets = [ target_device ]

        version_string = self.config.get("Release", "version_string")
        if self.config.getboolean("Release", "beta"):
            dt = datetime.datetime.now()
            version_string += "-beta-%s" % dt.strftime("%Y%m%d%H%M")
        if self.config.get("Release", "file_suffix") != "":
            version_string += "_%s" % self.config.get("Release", "file_suffix")

        for target in targets:
            valibox_build_tools_dir = get_valibox_build_tools_dir()
            steps.append(CmdStep("cp -r ../%s/devices/%s/files ./files" % (valibox_build_tools_dir, target), "lede-source"))
            steps.append(ValiboxVersionStep(version_string, directory="lede-source"))
            steps.append(CmdStep("cp ../%s/devices/%s/diffconfig ./.config" % (valibox_build_tools_dir, target), "lede-source"))
            steps.append(CmdStep("make defconfig", "lede-source"))
            build_cmd = "make"
            if self.config.getboolean("LEDE", "verbose_build"):
                print(type(self.config.getboolean("LEDE", "verbose_build")))
                build_cmd += " -j1 V=s"
            steps.append(CmdStep(build_cmd, "lede-source"))

        if self.config.getboolean("Release", "create_release"):
            changelog_file = self.config.get("Release", "changelog_file")
            if changelog_file == "":
                changelog_file = os.path.abspath(get_valibox_build_tools_dir()) + "/Valibox_Changelog.txt";

            steps.append(CreateReleaseStep(version_string, changelog_file,
                                           self.config.get("Release", "target_directory"),
                                           "lede-source"
                                           ))
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
        builder.print_steps()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
