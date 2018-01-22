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
    def __init__(self, directory, feed_dir):
        self.directory = directory
        self.line_to_add = "src-link sidn %s\n" % os.path.abspath(feed_dir)

    def __str__(self):
        return "in %s: add '%s' to feeds.conf" % (self.directory, self.line_to_add.strip())

    def perform(self):
        with gotodir(self.directory):
            with open("feeds.conf", "w") as out_file:
                with open("feeds.conf.default", "r") as in_file:
                    for line in in_file.readlines():
                        out_file.write(line)
                    out_file.write(self.line_to_add)
        return True

class UpdatePkgMakefile(Step):
    def __init__(self, directory, makefile, tarfile):
        self.directory = directory
        self.makefile = makefile
        self.tarfile = tarfile

    def __str__(self):
        return "in %s: Update the LEDE package makefile %s to use %s as the source" % (self.directory, self.makefile, self.tarfile)

    def perform(self):
        with gotodir(self.directory):
            # First, get the hash of the tarfile
            hash_line = basic_cmd_output("sha256sum %s" % self.tarfile)
            if hash_line is None:
                # print error?
                return False
            hash_str = hash_line.split(" ")[0]

            # Read the makefile, and update it in a tmp file
            # should we use mktempfile for this, or is this ok?
            with open(self.makefile, "r") as infile:
                with open(self.makefile + ".tmp", "w") as outfile:
                    for line in infile.readlines():
                        if line.startswith("PKG_SOURCE_URL"):
                            outfile.write("PKG_SOURCE_URL:=file://%s\n" % self.tarfile)
                        elif line.startswith("PKG_HASH"):
                            outfile.write("PKG_HASH:=%s\n" % hash_str)
                        else:
                            outfile.write(line)
            # seems like we succeeded, overwrite the makefile
            return basic_cmd("cp %s %s" % (self.makefile + ".tmp", self.makefile))
