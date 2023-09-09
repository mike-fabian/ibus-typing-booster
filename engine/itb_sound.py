# -*- coding: utf-8 -*-
# vim:et sts=4 sw=4
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2023 Mike FABIAN <mfabian@redhat.com>
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
Module to play simple error sounds
'''

from typing import Optional
from typing import Any
import sys
import os
import logging
import threading
import wave
import shutil
import subprocess
import mimetypes

LOGGER = logging.getLogger('ibus-typing-booster')

IMPORT_PYGAME_MIXER_SUCCESSFUL = False
try:
    import pygame.mixer
    IMPORT_PYGAME_MIXER_SUCCESSFUL = True
except (ImportError,):
    IMPORT_PYGAME_MIXER_SUCCESSFUL = False

IMPORT_PYAUDIO_SUCCESSFUL = False
try:
    import pyaudio # type: ignore
    IMPORT_PYAUDIO_SUCCESSFUL = True
except (ImportError,):
    IMPORT_PYAUDIO_SUCCESSFUL = False

IMPORT_SIMPLEAUDIO_SUCCESSFUL = False
try:
    import simpleaudio # type: ignore
    IMPORT_SIMPLEAUDIO_SUCCESSFUL = True
except (ImportError,):
    IMPORT_SIMPLEAUDIO_SUCCESSFUL = False

class SoundObject:
    '''
    Class to play sounds

    When pygames is used, this can play .wav and .mp3 files.
    When pyaudio is used, only .wav files work.
    '''
    def __init__(self,
                 path_to_sound_file: str,
                 audio_backend: str = 'automatic') -> None:
        self._path_to_sound_file: str = path_to_sound_file
        self._wav_file: Optional[wave.Wave_read] = None
        self._paudio: Optional[pyaudio.PyAudio] = None
        self._play_pyaudio_thread: Optional[threading.Thread] = None
        self._simpleaudio_wave_o: Optional[simpleaudio.WaveObject] = None
        self._simpleaudio_play_o: Optional[simpleaudio.shiny.PlayObject] = None
        self._aplay_binary: Optional[str] = None
        self._aplay_stdin = b''
        self._aplay_process: Optional[Any] = None
        self._play_aplay_thread: Optional[threading.Thread] = None
        self._supported_audio_backends = ('automatic', 'pygame', 'simpleaudio', 'aplay', 'pyaudio')
        self._requested_audio_backend = audio_backend
        self._audio_backend = ''
        if not os.path.isfile(self._path_to_sound_file):
            LOGGER.info('Sound file %s does not exist.', path_to_sound_file)
            return
        if not os.access(self._path_to_sound_file, os.R_OK):
            LOGGER.info('Sound file %s not readable.', path_to_sound_file)
            return
        if not self._requested_audio_backend in self._supported_audio_backends:
            LOGGER.error('Audio backend %s not supported, use one of %s',
                         audio_backend, self._supported_audio_backends)
            return
        self._audio_backend = getattr(self, f'_init_{self._requested_audio_backend}')()
        if self._audio_backend:
            LOGGER.info('Using audio backend %s', self._audio_backend)
        else:
            LOGGER.error('Could not init audio backend %s', self._requested_audio_backend)

    def _init_automatic(self) -> str:
        # Try 'pygame' first if possible it seems to be the best:
        if self._init_pygame():
            return 'pygame'
        # Try 'simpleaudio' for Python < 3.12.0, it used to work well
        # and has no dependencies.  But it is broken in Fedora 39,
        # see: https://bugzilla.redhat.com/show_bug.cgi?id=2237680
        # probably because Fedora 39 has Python 3.12.0rc2:
        if ((sys.version_info.major,
             sys.version_info.minor,
             sys.version_info.micro) < (3, 12, 0)):
            if self._init_simpleaudio():
                return 'simpleaudio'
        # Try 'aplay', it seems reliable:
        if self._init_aplay():
            return 'aplay'
        # Try 'pyaudio' as a last resort:
        # Broken for Python >= 3.10 if not updated to pyaudio >= 0.2.12
        # See: https://stackoverflow.com/questions/70344884)
        # Sometimes it seems to hang. Not often, but when this happens this is really bad
        if (IMPORT_PYAUDIO_SUCCESSFUL
            and
            (((sys.version_info.major,
               sys.version_info.minor,
               sys.version_info.micro) < (3, 10, 0))
             or
             (pyaudio.__version__
              and
              tuple(int(x) for x in pyaudio.__version__.split('.')) >= (0, 2, 12)))):
            if self._init_pyaudio():
                return 'pyaudio'
        # Nothing more to try ☹
        return ''

    def _init_pygame(self) -> str:
        if not IMPORT_PYGAME_MIXER_SUCCESSFUL:
            return ''
        try:
            pygame.mixer.init()
            if pygame.mixer.get_init():
                pygame.mixer.music.load(self._path_to_sound_file)
                return 'pygame'
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'pygame: cannot load sound file %s: %s',
                error.__class__.__name__, error)
        return ''

    def _init_pyaudio(self) -> str:
        if not IMPORT_PYAUDIO_SUCCESSFUL:
            return ''
        (mime_type, encoding) = mimetypes.guess_type(self._path_to_sound_file)
        if mime_type not in ('audio/x-wav',):
            LOGGER.error(
                'File %s has mime type %s and is not supported by simpleaudio',
                self._path_to_sound_file, mime_type)
            return ''
        try:
            self._wav_file = wave.open(self._path_to_sound_file, 'rb')
            self._paudio = pyaudio.PyAudio()
            self._stop_event_paudio: threading.Event = threading.Event()
            LOGGER.info('portaudio version = %s',
                        pyaudio.get_portaudio_version_text())
            return 'pyaudio'
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'pyaudio: cannot init wave object %s: %s',
                error.__class__.__name__, error)
        return ''

    def _init_simpleaudio(self) -> str:
        if not IMPORT_SIMPLEAUDIO_SUCCESSFUL:
            return ''
        (mime_type, encoding) = mimetypes.guess_type(self._path_to_sound_file)
        if mime_type not in ('audio/x-wav',):
            LOGGER.error(
                'File %s has mime type %s and is not supported by simpleaudio',
                self._path_to_sound_file, mime_type)
            return ''
        try:
            self._simpleaudio_wave_o = (
                simpleaudio.WaveObject.from_wave_file(self._path_to_sound_file))
            return 'simpleaudio'
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Initializing error sound object failed: %s: %s',
                error.__class__.__name__, error)
        return ''

    def _init_aplay(self) -> str:
        (mime_type, encoding) = mimetypes.guess_type(self._path_to_sound_file)
        if mime_type not in ('audio/x-wav',):
            LOGGER.error(
                'File %s has mime type %s and is not supported by aplay',
                self._path_to_sound_file, mime_type)
            return ''
        self._aplay_binary = shutil.which('aplay')
        if not self._aplay_binary:
            return ''
        with open (self._path_to_sound_file, mode='rb') as aplay_input:
            self._aplay_stdin = aplay_input.read()
            if self._aplay_stdin:
                return 'aplay'
        return ''

    def __del__(self) -> None:
        if self._paudio:
            self._paudio.terminate()
        if self._wav_file:
            self._wav_file.close()

    def _play_pyaudio_thread_function(self, stop_event: threading.Event) -> None:
        if not self._wav_file:
            LOGGER.error('wave.open(%s, \'rb\') did not work.',
                         self._path_to_sound_file)
            return
        if not self._paudio:
            LOGGER.error('pyaudio.PyAudio() did not work.')
            return
        LOGGER.info('Playing sound with pyaudio ...')
        stream = self._paudio.open(
            format=self._paudio.get_format_from_width(
                self._wav_file.getsampwidth()),
            channels=self._wav_file.getnchannels(),
            rate=self._wav_file.getframerate(),
            output=True)
        chunk_size = 1024
        self._wav_file.rewind()
        data = self._wav_file.readframes(chunk_size)
        while data and not stop_event.is_set():
            try:
                if not stream.is_active():
                    LOGGER.error('pyaudio stream is_active() is False')
                    break
                stream.write(data)
                data = self._wav_file.readframes(chunk_size)
            except (SystemError, OSError) as error:
                LOGGER.exception(
                    'Unexpected error playing wave object %s: %s',
                    error.__class__.__name__, error)
                LOGGER.error('If you see the '
                             '"SystemError: PY_SSIZE_T_CLEAN macro '
                             'must be defined for \'#\' formats" '
                             'message here, updating to pyaudio >= 0.2.12 '
                             'will probably fix the problem.'
                             'See https://stackoverflow.com/questions/70344884')
                break
        stream.stop_stream()
        stream.close()
        LOGGER.info('Done playing sound with pyaudio.')

    def _play_pyaudio(self) -> None:
        self._stop_event_paudio.clear()
        self._play_pyaudio_thread = threading.Thread(
            daemon=True,
            target=self._play_pyaudio_thread_function,
            args=(self._stop_event_paudio,))
        self._play_pyaudio_thread.start()

    def _is_playing_pyaudio(self) -> bool:
        if not self._play_pyaudio_thread:
            return False
        return self._play_pyaudio_thread.is_alive()

    def _stop_pyaudio(self) -> None:
        if not self._play_pyaudio_thread:
            return
        if (self._play_pyaudio_thread.is_alive()
            and not self._stop_event_paudio.is_set()):
            self._stop_event_paudio.set()
            self._play_pyaudio_thread.join()
            self._stop_event_paudio.clear()

    def _wait_done_pyaudio(self) -> None:
        if not self._play_pyaudio_thread:
            return
        if self._play_pyaudio_thread.is_alive():
            self._play_pyaudio_thread.join()

    def _play_simpleaudio(self) -> None:
        if not self._simpleaudio_wave_o:
            return
        try:
            self._simpleaudio_play_o = self._simpleaudio_wave_o.play()
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Initializing error sound object failed: %s: %s',
                error.__class__.__name__, error)

    def _is_playing_simpleaudio(self) -> bool:
        if not self._simpleaudio_play_o:
            return False
        return bool(self._simpleaudio_play_o.is_playing())

    def _stop_simpleaudio(self) -> None:
        if not self._simpleaudio_play_o:
            return
        self._simpleaudio_play_o.stop()
        # wait until it is really stopped, otherwise a call to
        # __is_playing_simpleaudio() might still return True:
        self._simpleaudio_play_o.wait_done()

    def _wait_done_simpleaudio(self) -> None:
        if not self._simpleaudio_play_o:
            return
        self._simpleaudio_play_o.wait_done()

    @staticmethod
    def _play_pygame() -> None:
        pygame.mixer.music.rewind()
        pygame.mixer.music.play()

    @staticmethod
    def _is_playing_pygame() -> bool:
        return pygame.mixer.music.get_busy()

    @staticmethod
    def _stop_pygame() -> None:
        pygame.mixer.music.stop()

    @staticmethod
    def _wait_done_pygame() -> None:
        while pygame.mixer.music.get_busy():
            pass

    def _play_aplay_thread_function(self) -> None:
        if not self._aplay_binary:
            return
        try:
            self._aplay_process = subprocess.Popen('aplay', shell=False,
                                                   stdin=subprocess.PIPE,
                                                   stderr=subprocess.PIPE,
                                                   stdout=subprocess.PIPE,
                                                   encoding=None,
                                                   errors=None,
                                                   text=None)
        except (OSError, ValueError) as error:
            LOGGER.exception(
                'cannot start aplay process %s: %s',
                error.__class__.__name__, error)
            return
        try:
            self._aplay_process.communicate(input=self._aplay_stdin,
                                            timeout=1000)
        except subprocess.TimeoutExpired as error:
            LOGGER.exception(
                'timeout piping sound file into aplay process%s: %s',
                error.__class__.__name__, error)
            self._aplay_process.kill()
            return
        try:
            self._aplay_process.terminate()
        except Exception as error:
            LOGGER.exception(
                'cannot terminate aplay process %s: %s',
                error.__class__.__name__, error)
            try:
                LOGGER.info('Trying to kill aplay process')
                self._aplay_process.kill()
                LOGGER.info('aplay process killed')
            except Exception as error:
                LOGGER.exception(
                    'cannot kill aplay process%s: %s',
                    error.__class__.__name__, error)

    def _play_aplay(self) -> None:
        self._play_aplay_thread = threading.Thread(
            daemon=True,
            target=self._play_aplay_thread_function)
        self._play_aplay_thread.start()

    def _is_playing_aplay(self) -> bool:
        if not self._play_aplay_thread:
            return False
        return self._play_aplay_thread.is_alive()

    def _stop_aplay(self) -> None:
        if not self._play_aplay_thread:
            return
        if (self._play_aplay_thread.is_alive()
            and self._aplay_process
            and self._aplay_process.poll() is None):
            try:
                self._aplay_process.terminate()
            except Exception as error:
                LOGGER.exception(
                'cannot terminate aplay process %s: %s',
                error.__class__.__name__, error)
                try:
                    LOGGER.info('Trying to kill aplay process')
                    self._aplay_process.kill()
                except Exception as error:
                    LOGGER.exception(
                        'cannot kill aplay process%s: %s',
                    error.__class__.__name__, error)
        if self._play_aplay_thread.is_alive():
            self._play_aplay_thread.join(timeout=0.1)
            if self._play_aplay_thread.is_alive():
                LOGGER.error('timeout stopping aplay thread')

    def _wait_done_aplay(self) -> None:
        if not self._play_aplay_thread:
            return
        if self._play_aplay_thread.is_alive():
            self._play_aplay_thread.join()

    def play(self) -> None:
        '''Play the sound'''
        if not self._audio_backend:
            LOGGER.error('Could not init any audio backend %s',
                         self._requested_audio_backend)
            return
        getattr(self, f'_play_{self._audio_backend}')()

    def is_playing(self) -> bool:
        '''Check whether the sound is currently playing'''
        if not self._audio_backend:
            LOGGER.error('Could not init any audio backend %s',
                         self._requested_audio_backend)
            return False
        return bool(getattr(self, f'_is_playing_{self._audio_backend}')())

    def stop(self) -> None:
        '''Stop playing of the sound'''
        if not self._audio_backend:
            LOGGER.error('Could not init any audio backend %s',
                         self._requested_audio_backend)
            return
        getattr(self, f'_stop_{self._audio_backend}')()

    def wait_done(self) -> None:
        '''Wait until the sound has been fully played'''
        if not self._audio_backend:
            LOGGER.error('Could not init any audio backend %s',
                         self._requested_audio_backend)
            return
        getattr(self, f'_wait_done_{self._audio_backend}')()

def run_tests() -> None:
    '''Run some simple tests'''

    audio_backend = 'automatic'
    # Testing a short sound:
    sound_object = SoundObject(
        #'/home/mfabian/sounds/japanese/今回もよろしくお願いします.wav',
        '/usr/share/ibus-typing-booster/data/coin9.wav',
        #'/home/mfabian/sounds/japanese/今回もよろしくお願いします.mp3',
        audio_backend=audio_backend)
    sound_object.play()
    sound_object.wait_done()
    sound_object.play()
    sound_object.wait_done()

    # Testing stopping in between with a longer sound file:

    import time # pylint: disable=import-outside-toplevel

    sound_object = SoundObject(
        '/home/mfabian/sounds/japanese/今回もよろしくお願いします.wav',
        audio_backend=audio_backend)
    sound_object.play()
    LOGGER.info('Sleeping ...')
    time.sleep(1)
    LOGGER.info('is playing %s', sound_object.is_playing())
    sound_object.stop()
    LOGGER.info('is playing %s', sound_object.is_playing())
    time.sleep(4)

if __name__ == "__main__":
    LOG_HANDLER = logging.StreamHandler(stream=sys.stderr)
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.addHandler(LOG_HANDLER)

    run_tests()
