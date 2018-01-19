# valibox-build-v3
temporary repository to play around with new valibox build system

This contains standard configurations for specific architectures and devices, and i am experimenting with a python wrapper to replace all the various shell scripts.

Main intended features:
    - collect and store configurations without having a clone of lede-source
    - build from scratch, but also from existing checkouts
    - remember last build configuration
    - resume build if failed or stopped, possibly with slightly altered settings (like -j1 V=s)
    - options between 'build from repo' or 'build from local' (for example for spin)


Prerequisites

* Python 3
* ...

Usage

Create a new directory to build/download in, and run builder.py from that directory:

    mkdir valibox_build
    cd valibox_build
    /path/to/valibox-build-tools/builder.py

This will only create a configuration file, and not actually start building yet. You can change settings with the -e option (or edit the configuration file, which defaults to .valibox_build_config in the current directory). See below for documentation on all the configuration options.

    /path/to/valibox-build-tools/builder.py -e

You can start the build by using -b. If any step along the way fails, or the process is otherwise interrupted, you can restart from the latest build step with the same command.

    /path/to/valibox-build-tools/builder.py -b

If you want to restart from the first step, you can use -r.

    /path/to/valibox-build-tools/builder.py -r


Configuration options
