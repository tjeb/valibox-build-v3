# valibox-build-v3
temporary repository to play around with new valibox build system

This contains standard configurations for specific architectures and devices, and i am experimenting with a python wrapper to replace all the various shell scripts.

Main intended features:
    - collect and store configurations without having a clone of lede-source
    - build from scratch, but also from existing checkouts
    - remember last build configuration
    - resume build if failed or stopped, possibly with slightly altered settings (like -j1 V=s)
    - options between 'build from repo' or 'build from local' (for example for spin)

