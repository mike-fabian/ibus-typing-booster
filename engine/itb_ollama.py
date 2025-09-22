# vim:et sts=4 sw=4
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2015-2025 Mike FABIAN <mfabian@redhat.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>
'''
A module with utilites to use ollama
'''

from typing import Callable
from typing import Optional
from typing import Dict
from typing import List
from typing import Generator
from typing import Set
from typing import Union
from typing import Any
from typing import cast
import sys
# pylint: disable=wrong-import-position
if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal
# pylint: enable=wrong-import-position
import os
import re
import json
import threading
import logging
import shutil
import subprocess
import functools
import httpx

LOGGER = logging.getLogger('ibus-typing-booster')

class ItbOllamaClient:
    '''A class to provide a simple interface to Ollama.

    `ramalama` can also be used, but it *must* be started like this:

    `ramalama serve --network=host -p 11434 <model>`

    The `--network=host` option is *required* and the
    `--api=llama-stack` option *must* *not* be used.
    '''
    def __init__(
        self,
        timeout: float = 60.0,
    ) -> None:
        '''Initialize the ItbOllamaClient class'''
        self._host = os.environ.get('OLLAMA_HOST') or 'http://localhost:11434'
        self._client: Optional[httpx.Client] = None
        self._server: Literal['ollama', 'ramalama', ''] = ''
        self._version = ''
        self._error = ''
        self._ramalama_shortnames: Dict[str, str] = {}
        try:
            self._client = httpx.Client(base_url=self._host, timeout=timeout)
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception('Failed to create httpx.Client: %s', error)
            self._client = None
        if self._client is None:
            return
        try:
            self._client.get('')
        except httpx.ConnectError as error:
            LOGGER.error('Failed to connect to server: %s', error)
            self._error = str(error)
            return
        resp = self._client.get('/api/version')
        if resp.status_code == httpx.codes.OK:
            self._server = 'ollama'
            self._version = resp.json().get('version', '')
        resp = self._client.get('/v1/models')
        if resp.status_code == httpx.codes.OK:
            data = resp.json().get('data', [])
            for model_dict in data:
                if model_dict.get('owned_by', '') == 'library':
                    self._server = 'ollama'
                if model_dict.get('owned_by', '') == 'llamacpp':
                    self._server = 'ramalama'
        if self._server == 'ramalama':
            self._ramalama_shortnames = get_ramalama_shortnames()
            self._version = get_ramalama_version()

    def get_error(self) -> str:
        '''Return an error string'''
        return self._error

    def get_host(self) -> str:
        '''Return the host of the server.'''
        return self._host

    def get_server(self) -> str:
        '''Return the detected server name.'''
        return self._server

    def get_version(self) -> str:
        '''Return the version number of the server'''
        return self._version

    def models(self) -> Dict[str, Any]:
        '''(Verbosely) list models available on the server.'''
        if self._client is None or self._server == '':
            return {}
        resp = self._client.get('/v1/models')
        resp.raise_for_status()
        return cast(Dict[str, Any], resp.json())

    def model_ids(self) -> Set[str]:
        '''Get set of all model ids available on the server'''
        return {model['id'] for model in self.models().get('data', [])}

    def is_available(self, model: str) -> bool:
        '''Check whether a model is available on the server'''
        available = [self.short_name(x) for x in self.model_ids()]
        if self.short_name(model) in available:
            return True
        return False

    def short_name(self, model: str) -> str:
        '''Normalize a ollama or ramalama model name to the shortest version

        For example:

        'mistral:latest' -> 'mistral'
        'hf://ggml-org/gemma-3-4b-it-GGUF' -> 'gemma3'
        'ggml-org/gemma-3-4b-it-GGUF' -> 'gemma3'
        '''
        if model.endswith(':latest'):
            model = model[:-7]
        if self._server == 'ramalama':
            if model in self._ramalama_shortnames:
                return model
            model_without_prefix = re.sub(r'^[a-z]+://', '', model)
            for shortname, longname in self._ramalama_shortnames.items():
                longname_without_prefix = re.sub(r'^[a-z]+://', '', longname)
                if model_without_prefix == longname_without_prefix:
                    return shortname
            return model_without_prefix
        return model

    def pull(
        self,
        model: str,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        stop_event: Optional[threading.Event] = None,
    ) -> bool:
        '''Pull a model with optional progress callback (streaming).'''
        if self._server != 'ollama' or self._client is None:
            return False
        client = self._client # narrow Optional[httpx.Client] → httpx.Client
        try:
            with client.stream('POST', '/api/pull', json={'name': model}) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if stop_event is not None and stop_event.is_set():
                        LOGGER.info('Ollama pull stopped by event.')
                        return False
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        data = {'raw': line,
                                'status': 'error',
                                'error': 'JSONDecodeError'}
                    if progress_callback:
                        progress_callback(data)
                    if 'error' in data:
                        return False
            return True
        except Exception as error: # pylint: disable=broad-except
            if progress_callback:
                progress_callback({'error': str(error), 'status': 'error'})
        return False

    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        stream: bool = False,
    ) -> Union[Generator[Dict[str, Any], None, None], Dict[str, Any]]:
        '''
        Send a chat request.
        - messages = [{'role': 'user', 'content': 'Hello'}]
        - If stream=True, yields events as they arrive.
        - If stream=False, returns the full response once.
        '''
        if self._client is None or self._server == '':
            return {}
        client = self._client # narrow Optional[httpx.Client] → httpx.Client
        endpoint = '/v1/chat/completions'
        body = {'model': model, 'messages': messages, 'stream': stream}
        if stream:
            def event_stream() -> Generator[Dict[str, Any], None, None]:
                with client.stream('POST', endpoint, json=body) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line.lstrip('data:'))
                            if isinstance(data, dict):
                                yield data
                            else:
                                yield {'data': data}
                        except json.JSONDecodeError:
                            yield {'raw': line}
            return event_stream()
        resp = client.post(endpoint, json=body)
        resp.raise_for_status()
        return cast(Dict[str, Any], resp.json())

    def close(self) -> None:
        '''Close the HTTP connection pool.'''
        if self._client:
            self._client.close()
            self._client = None

@functools.lru_cache(maxsize=None)
def get_ramalama_shortnames() -> Dict[str, str]:
    '''Get the shortnames dictionary from `ramalama info`'''
    ramalama_binary = shutil.which('ramalama')
    if ramalama_binary:
        try:
            result = subprocess.run(
                [ramalama_binary, 'info'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='utf-8', check=True)
            data = json.loads(result.stdout.strip())
            shortnames = data.get('Shortnames', {})
            return cast(Dict[str, str], shortnames.get('Names', {}))
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Exception when calling %s: %s',
                ramalama_binary, error)
    return {}

@functools.lru_cache(maxsize=None)
def get_ramalama_version() -> str:
    '''Get the ramalama version from `ramalama version`'''
    ramalama_binary = shutil.which('ramalama')
    version = ''
    if ramalama_binary:
        try:
            version = subprocess.check_output(
                [ramalama_binary, 'version'],
                stderr=subprocess.STDOUT).decode('utf-8').strip()
        except (subprocess.CalledProcessError, FileNotFoundError) as error:
            LOGGER.exception(
                'Exception when calling %s: %s',
                ramalama_binary, error)
            return ''
    return re.sub(r'[^\d.]', '', version)

if __name__ == '__main__':
    LOG_HANDLER = logging.StreamHandler(stream=sys.stderr)
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.addHandler(LOG_HANDLER)
    import doctest
    (FAILED, _ATTEMPTED) = doctest.testmod()
    sys.exit(FAILED)
