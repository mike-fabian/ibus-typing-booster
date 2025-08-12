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

'''A module with utilites to use ollama
'''

from typing import Callable
from typing import Optional
from typing import Dict
from typing import Set
from typing import Any
import sys
import logging
import ollama

LOGGER = logging.getLogger('ibus-typing-booster')

def pull_model(
    model_name: str,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> bool:
    '''Download an Ollama model with optional progress reporting.

    :param model_name:        Name of the model to download
    :param progress_callback: Function to call with progress updates

    :return: True if successful, False otherwise
    '''
    try:
        response = ollama.pull(model_name, stream=True)
        for progress in response:
            if progress_callback:
                # Handle different response types
                if isinstance(progress, dict):
                    progress_callback(progress)
                elif hasattr(progress, 'dict'):
                    progress_callback(progress.dict())
                else:
                    # Convert object to dictionary
                    progress_dict = {}
                    if hasattr(progress, '__dict__'):
                        progress_dict = vars(progress)
                    else:
                        # Fallback: try to get common attributes
                        for attr in ['status', 'total', 'completed', 'error']:
                            if hasattr(progress, attr):
                                progress_dict[attr] = getattr(progress, attr)
                    progress_callback(progress_dict)
        return True
    except Exception as error: # pylint: disable=broad-except
        if progress_callback:
            progress_callback({'error': str(error), 'status': 'error'})
        return False

def normalize_model_name(model_name: str) -> str:
    '''Normalize model name to include explicit tag'''
    if ':' not in model_name:
        return f'{model_name}:latest'
    return model_name

def get_pulled_models() -> Set[str]:
    '''Get set of all downloaded model names'''
    try:
        result = ollama.list()
        return {model['model'] for model in result.get('models', [])}
    except Exception as error: # pylint: disable=broad-except
        LOGGER.exception('Error getting model list: %s', error)
        return set()

def is_model_pulled(requested_model: str) -> bool:
    '''Check whether a model has been pulled already.'''
    downloaded = get_pulled_models()
    if requested_model in downloaded:
        return True
    if normalize_model_name(requested_model) in downloaded:
        return True
    return False

if __name__ == "__main__":
    LOG_HANDLER = logging.StreamHandler(stream=sys.stderr)
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.addHandler(LOG_HANDLER)
    import doctest
    (FAILED, _ATTEMPTED) = doctest.testmod()
    sys.exit(FAILED)
