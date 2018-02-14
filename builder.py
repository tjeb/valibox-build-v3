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
import collections
import datetime
import os
import subprocess
import sys

from valibox_builder.util import *
from valibox_builder.conditionals import *
from valibox_builder.steps import *

from valibox_builder.builder import BuildConfig, Builder, StepBuilder

DEFAULT_CONFIG = collections.OrderedDict((
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

def build_steps(config):
    sb = StepBuilder()

    #
    # LEDE sources
    #
    steps = []
    if config.getboolean("LEDE", "update_git"):
        sb.add_cmd("git clone https://github.com/lede-project/source lede-source").if_dir_not_exists('lede-source')
        sb.add_cmd("git fetch").at("lede-source")
        sb.add(GitBranchStep(config.get("LEDE", "source_branch"), "lede-source"))
        # pull errors if the 'branch' is a detached head, so it may fail
        sb.add_cmd("git pull").at("lede-source").may_fail()

    #
    # SIDN Package feed sources
    #
    sidn_pkg_feed_dir = "sidn_openwrt_pkgs"
    if config.getboolean("sidn_openwrt_pkgs", "update_git"):
        sb.add_cmd("git clone https://github.com/SIDN/sidn_openwrt_pkgs %s" % sidn_pkg_feed_dir).if_dir_not_exists('sidn_openwrt_pkgs')
        sb.add_cmd("git fetch").at("sidn_openwrt_pkgs")
        sb.add(GitBranchStep(config.get("sidn_openwrt_pkgs", "source_branch"), "sidn_openwrt_pkgs"))
        sb.add_cmd("git pull").at("sidn_openwrt_pkgs").may_fail()

    #
    # SPIN Sources (if we build from local checkout)
    # If we build SPIN locally, we need to check it out as well (
    # (and perform magic with the sidn_openwrt_pkgs checkout)
    #
    if config.getboolean("SPIN", "local"):
        if config.getboolean("SPIN", "update_git"):
            sb.add_cmd("git clone https://github.com/SIDN/spin").if_dir_not_exists("spin")

            # only relevant if we use a local build of spin
            sb.add_cmd("git fetch").at("spin")
            sb.add(GitBranchStep(config.get("SPIN", "source_branch"), "spin"))
            sb.add_cmd("git pull").at("spin").may_fail()

        # Create a local release tarball from the checkout, and
        # update the PKGHASH and location in the package feed data
        # TODO: there are a few hardcoded values assumed here and in the next few steps
        sb.add_cmd("./create_tarball.sh -n").at("spin")
        sb.add_cmd("rm -f dl/spin-0.6-beta.tar.gz").at("lede-source")

        # Set that in the pkg feed data; we do not want to change the repository, so we make a copy and update that
        orig_sidn_pkg_feed_dir = sidn_pkg_feed_dir
        sidn_pkg_feed_dir = sidn_pkg_feed_dir + "_local"
        sb.add_cmd("git checkout-index -a -f --prefix=../%s/" % sidn_pkg_feed_dir).at(orig_sidn_pkg_feed_dir)

        sb.add(UpdatePkgMakefile(sidn_pkg_feed_dir, "spin/Makefile", "/tmp/spin-0.6-beta.tar.gz"))

    #
    # Update general package feeds in LEDE
    #
    sb.add(UpdateFeedsConf("lede-source", sidn_pkg_feed_dir))
    if config.getboolean('LEDE', 'update_all_feeds'):
        # Always update all feeds
        sb.add_cmd("./scripts/feeds update -a").at("lede-source")
        sb.add_cmd("./scripts/feeds install -a").at("lede-source")
    else:
        # Only update sidn feed if the rest have been installed already
        sb.add_cmd("./scripts/feeds update sidn").at("lede-source").if_dir_exists("package/feeds/packages")
        sb.add_cmd("./scripts/feeds install -a -p sidn").at("lede-source").if_dir_exists("package/feeds/packages")

        # Update all feeds if they haven't been installed already
        sb.add_cmd("./scripts/feeds update -a").at("lede-source").if_dir_not_exists("package/feeds/packages")
        sb.add_cmd("./scripts/feeds install -a").at("lede-source").if_dir_not_exists("package/feeds/packages")


    #
    # Determine target devices
    #
    target_device = config.get('LEDE', 'target_device')
    if target_device == 'all':
        targets = [ 'gl-ar150', 'gl-mt300a', 'gl-6416' ]
    else:
        targets = [ target_device ]

    #
    # Prepare the version string of the release
    #
    version_string = config.get("Release", "version_string")
    if config.getboolean("Release", "beta"):
        dt = datetime.datetime.now()
        version_string += "-beta-%s" % dt.strftime("%Y%m%d%H%M")
    if config.get("Release", "file_suffix") != "":
        version_string += "_%s" % config.get("Release", "file_suffix")

    #
    # Build the LEDE image(s)
    #
    for target in targets:
        valibox_build_tools_dir = get_valibox_build_tools_dir()
        sb.add_cmd("cp -r ../%s/devices/%s/files ./files" % (valibox_build_tools_dir, target)).at( "lede-source")
        sb.add(ValiboxVersionStep(version_string)).at("lede-source")
        sb.add_cmd("cp ../%s/devices/%s/diffconfig ./.config" % (valibox_build_tools_dir, target)).at("lede-source")
        sb.add_cmd("make defconfig").at("lede-source")
        build_cmd = "make"
        if config.getboolean("LEDE", "verbose_build"):
            build_cmd += " -j1 V=s"
        sb.add_cmd(build_cmd).at("lede-source")

    #
    # And finally, move them into a release directory structure
    #
    if config.getboolean("Release", "create_release"):
        changelog_file = config.get("Release", "changelog_file")
        if changelog_file == "":
            changelog_file = os.path.abspath(get_valibox_build_tools_dir()) + "/Valibox_Changelog.txt";

        sb.add(CreateReleaseStep(targets, os.path.abspath(get_valibox_build_tools_dir()),
                    version_string, changelog_file,
                    config.get("Release", "target_directory")).at("lede-source"))

    return sb.steps


# Return the directory of this toolkit; needed to get device information
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

    config = BuildConfig(args.config, DEFAULT_CONFIG)
    builder = Builder(build_steps(config))

    if args.build:
        builder.perform_steps()
    elif args.restart:
        builder.last_step = 1
        builder.perform_steps()
    elif args.edit:
        EDITOR = os.environ.get('EDITOR','vim')
        config.save_config()
        subprocess.call([EDITOR, config.config_file])
    elif args.print_steps:
        builder.print_steps()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
