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
