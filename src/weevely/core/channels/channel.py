import re
import ssl
import traceback
import urllib.error
import urllib.parse
import urllib.request

from urllib.error import HTTPError
from urllib.error import URLError

import socks
import sockshandler

from weevely import utils
from weevely.core import messages
from weevely.core.loggers import dlog
from weevely.core.loggers import log
from weevely.core.weexceptions import ChannelException


url_dissector = re.compile(
    r"^(https?|socks4|socks5)://"  # http:// or https://
    # domain...
    r"((?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"
    r"localhost|"  # localhost...
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
    r":(\d+)?"  # optional port
    r"(?:/?|[/?]\S+)$",
    re.IGNORECASE,
)


class Channel:
    def __init__(self, channel_name, session):
        """
        Import and instanciate dynamically the channel.

        Given the channel object Mychannel, this should be placed
        in module core.channels.mychannel.mychannel.
        """

        module_name = channel_name.lower()

        try:
            # Import module
            module = __import__(f"weevely.core.channels.{module_name}.{module_name}", fromlist=["*"])
            # Import object
            channel_object = getattr(module, channel_name)
        except Exception as e:
            traceback.print_exc()
            raise ChannelException(messages.channels.error_loading_channel_s % (channel_name)) from e

        self.session = session

        # Create channel instance
        self.channel_loaded = channel_object(self.session["url"], self.session["password"])

        self.channel_name = channel_name

        self.err_token = utils.strings.randstr(6) + b"ERR"
        self.re_error = re.compile(b"%s(.*?)%s" % (self.err_token, self.err_token), re.DOTALL)

    def _get_proxy(self):
        url_dissected = url_dissector.findall(self.session["proxy"])

        if url_dissected and len(url_dissected[0]) == 3:
            protocol, host, port = url_dissected[0]
            if protocol == "socks5":
                return (socks.PROXY_TYPE_SOCKS5, host, int(port))
            if protocol == "socks4":
                return (socks.PROXY_TYPE_SOCKS4, host, int(port))
            if protocol.startswith("http"):
                return (socks.PROXY_TYPE_HTTP, host, int(port))

        return None, None, None

    def _additional_handlers(self):
        handlers = []

        if self.session.get("proxy"):
            protocol, host, port = self._get_proxy()

            if protocol and host and port:
                handlers.append(sockshandler.SocksiPyHandler(protocol, host, port))
            else:
                raise ChannelException(messages.channels.error_proxy_format)

        # Skip certificate checks
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        ctx.verify_mode = ssl.CERT_NONE

        handlers.append(urllib.request.HTTPSHandler(context=ctx))

        return handlers

    def send(self, payload, catch_errors=True):
        response = b""
        code = 200
        error = ""

        human_error = ""

        virgin_payload = payload
        if catch_errors:
            # Wrap payload in try/catch to handle remote errors
            token = self.err_token.decode("utf-8")
            payload = (
                "try {"
                + payload
                + "}catch(Exception $e){"
                + f'echo "{token}".$e->getTrace()[0]["function"].": ".$e->getMessage()."{token}";'
                + "}"
            )

        try:
            response = self.channel_loaded.send(payload, self._additional_handlers())
        except socks.ProxyError as e:
            if e.socket_err and e.socket_err.errno:
                code = e.socket_err.errno
            if e.msg:
                error = str(e.msg)

            human_error = messages.module_shell_php.error_proxy

        except HTTPError as e:
            if e.code:
                code = e.code
            if e.reason:
                error = str(e.reason)

            if code == 404:
                human_error = messages.module_shell_php.error_404_remote_backdoor
            elif code == 500:
                human_error = messages.module_shell_php.error_500_executing
            elif code != 200:
                human_error = messages.module_shell_php.error_i_executing % code

        except URLError as e:
            code = 0
            if e.reason:
                error = str(e.reason)

            human_error = messages.module_shell_php.error_URLError_network

        if response:
            dlog.info("RESPONSE: %s" % repr(response))

        if response and catch_errors:
            # Parse remote errors
            remote_errors = self.re_error.findall(response)
            if remote_errors:
                response = self.re_error.sub(b"", response)
                error = b"\n".join(remote_errors).decode("utf-8", "replace")
                code = 500

        self._detect_syntax_error(virgin_payload)

        if human_error:
            log.warning(human_error)
            return response, code, error

        if error and code:
            log.warning("[ERR:%s] %s" % (code, error))
            return response, code, error

        return response, code, error

    def _detect_syntax_error(self, payload):
        """Detect syntax errors and warn user
        @TODO detect before sending, and ask confirmation
        @TODO use proper linter for corresponding vector
        """
        command_last_chars = utils.prettify.shorten(payload.rstrip(), keep_trailer=10)
        if command_last_chars and command_last_chars[-1] not in (";", "}"):
            log.warning(messages.module_shell_php.missing_php_trailer_s % command_last_chars)
