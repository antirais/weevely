from weevely import utils
from weevely.core import messages
from weevely.core import modules
from weevely.core.loggers import log
from weevely.core.module import Module
from weevely.core.vectors import PhpCode


class Info(Module):
    """Collect system information."""

    aliases = ["whoami", "hostname", "pwd", "uname"]

    default_provider = "http://ifconfig.me/"

    extended_vectors = ["server_soft", "server_ip", "ini_path", "tmp_path", "free_space", "dir_sep"]

    def init(self):
        self.register_info({"author": ["Emilio Pinna"], "license": "GPLv3"})

        self.register_vectors(
            [
                PhpCode("print(@$_SERVER['DOCUMENT_ROOT']);", "document_root"),
                PhpCode("@print(getcwd());", "pwd"),
                PhpCode("print(empty(Phar::running(false))?__DIR__:dirname(Phar::running(false)));", "script_folder"),
                PhpCode("print(@$_SERVER['SCRIPT_NAME']);", "script"),
                PhpCode("print(@$_SERVER['PHP_SELF']);", "php_self"),
                PhpCode(
                    """
                    if(is_callable('posix_getpwuid')&&is_callable('posix_geteuid')) {
                        $u=@posix_getpwuid(@posix_geteuid());
                        if($u){
                            $u=$u['name'];
                        } else {
                            $u=getenv('username');
                        }
                        print($u);
                    }
                """,
                    "whoami",
                ),
                PhpCode("print(@gethostname());", "hostname"),
                PhpCode("$v=@ini_get('open_basedir'); if($v) print($v);", "open_basedir"),
                PhpCode("print(@ini_get('disable_functions'));", "disable_functions"),
                PhpCode("print(@php_ini_loaded_file());", "ini_path"),
                PhpCode("print(@sys_get_temp_dir());", "tmp_path"),
                PhpCode(
                    "print(@disk_free_space(dirname(empty(Phar::running(false))?__DIR__:Phar::running(false))));",
                    "free_space",
                    postprocess=lambda x: utils.prettify.format_size(int(x)),
                ),
                PhpCode(
                    "print(@ini_get('safe_mode') ? 1 : 0);",
                    "safe_mode",
                    postprocess=lambda x: True if x == "1" else False,
                ),
                PhpCode("print(@$_SERVER['SERVER_SOFTWARE']);", "server_soft"),
                PhpCode("print(@php_uname());", "uname"),
                PhpCode("print(@php_uname('s') . ' ' . @php_uname('m'));", "os"),
                PhpCode("print(@$_SERVER['REMOTE_ADDR']);", "client_ip"),
                PhpCode("print(@file_get_contents('${provider}'));", "server_ip"),
                PhpCode("print(@$_SERVER['SERVER_NAME']);", "server_name"),
                PhpCode(
                    "print(@ini_get('max_execution_time'));",
                    "max_execution_time",
                    postprocess=lambda x: int(x) if x and x.isdigit() else False,
                ),
                PhpCode("@print(DIRECTORY_SEPARATOR);", "dir_sep"),
                PhpCode(
                    """
                    $v='';
                    if(function_exists('phpversion')) {
                        $v=phpversion();
                    } elseif(defined('PHP_VERSION')) {
                        $v=PHP_VERSION;
                    } elseif(defined('PHP_VERSION_ID')) {
                        $v=PHP_VERSION_ID;
                    }
                    print($v);
                """,
                    "php_version",
                ),
            ]
        )

        self.register_arguments(
            [
                {
                    "name": "-info",
                    "help": "Select information (possible values are: %s)" % (", ".join(self.vectors.get_names())),
                    "choices": self.vectors.get_names(),
                    "default": [],
                    "nargs": "+",
                    "metavar": "arg",
                },
                {
                    "name": "-extended",
                    "help": "Get more info. Slower. (extended info: %s)" % (", ".join(self.extended_vectors)),
                    "action": "store_true",
                    "default": False,
                },
                {
                    "name": "-provider",
                    "help": "The URL to get server_ip from (default: %s)" % self.default_provider,
                    "metavar": "http://...",
                    "default": self.default_provider,
                },
            ]
        )

    def run(self, **kwargs):
        vectors = self.args.get("info")

        if not vectors and not self.args.get("extended"):
            vectors = [i for i in self.vectors.get_names() if i not in self.extended_vectors]

        result = self.vectors.get_results(
            names=vectors,
            results_to_store=("whoami", "hostname", "dir_sep", "os", "script_folder", "server_ip"),
            format_args={"provider": self.args.get("provider")},
        )

        # Returns a string when a single information is requested,
        # else returns a dictionary containing all the results.
        info = self.args.get("info")
        if info and len(info) == 1:
            return result[info[0]]
        return result

    def run_alias(self, args, cmd):
        if self.session["default_shell"] != "shell_sh":
            log.debug(messages.module.running_the_alias_s % self.name)
            return self.run_cmdline("-info %s" % cmd)
        modules.loaded["shell_sh"].run_cmdline("%s -- %s" % (cmd, args))
