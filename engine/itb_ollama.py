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
import os
import sys
import json
import threading
import logging
import httpx

LOGGER = logging.getLogger('ibus-typing-booster')

class ItbOllamaClient:
    '''A class to provide a simple interface to Ollama.'''
    def __init__(
        self,
        timeout: float = 60.0,
    ) -> None:
        '''Initialize the ItbOllamaClient class'''
        host = os.environ.get('OLLAMA_HOST') or 'http://localhost:11434'
        self._client: Optional[httpx.Client] = None
        try:
            self._client = httpx.Client(base_url=host, timeout=timeout)
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception('Failed to create ollama client: %s', error)
            self._client = None

    def is_connected(self) -> bool:
        '''Quick check if the client is usable.'''
        return self._client is not None

    def list(self) -> Dict[str, Any]:
        '''(Verbosely) list models available on the server.'''
        if self._client is None:
            return {}
        resp = self._client.get('/api/tags')
        resp.raise_for_status()
        return cast(Dict[str, Any], resp.json())

    def list_models(self) -> Set[str]:
        '''Get set of all model names available on the server'''
        return {model['model'] for model in self.list().get('models', [])}

    def is_available(self, model: str) -> bool:
        '''Check whether a model is available on the server'''
        available = self.list_models()
        if model in available:
            return True
        if ':' not in model and f'{model}:latest' in available:
            return True
        return False

    def pull(
        self,
        model: str,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        stop_event: Optional[threading.Event] = None,
    ) -> bool:
        '''Pull a model with optional progress callback (streaming).'''
        if self._client is None:
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
        if self._client is None:
            return {}
        client = self._client # narrow Optional[httpx.Client] → httpx.Client
        endpoint = '/api/chat'
        body = {'model': model, 'messages': messages, 'stream': stream}
        if stream:
            def event_stream() -> Generator[Dict[str, Any], None, None]:
                with client.stream('POST', endpoint, json=body) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
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

if __name__ == '__main__':
    LOG_HANDLER = logging.StreamHandler(stream=sys.stderr)
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.addHandler(LOG_HANDLER)
    import doctest
    (FAILED, _ATTEMPTED) = doctest.testmod()
    sys.exit(FAILED)
