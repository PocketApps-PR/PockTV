# -*- coding: utf-8 -*-
"""Sonidos de la interfaz (mover / elegir / volver): archivos WAV cortos en la carpeta sounds/.
Se abre un dispositivo de audio de SDL solo cuando hace falta y se cierra antes de reproducir video."""
import ctypes
import os
import time
import traceback
import wave

import sdl2


class Sound(object):
    def __init__(self, folder, log):
        self.dir = folder
        self.log = log
        self.dev = 0
        self.dead = False
        self.cache = {}
        self.last = 0.0

    def _wav(self, style, kind):
        k = (style, kind)
        d = self.cache.get(k)
        if d is None:
            try:
                w = wave.open(os.path.join(self.dir, "%s_%s.wav" % (style, kind)), "rb")
                d = w.readframes(w.getnframes())
                w.close()
            except Exception:
                d = b""
            self.cache[k] = d
        return d

    def _open(self):
        if self.dev or self.dead:
            return bool(self.dev)
        try:
            if not sdl2.SDL_WasInit(sdl2.SDL_INIT_AUDIO):
                sdl2.SDL_InitSubSystem(sdl2.SDL_INIT_AUDIO)
            want = sdl2.SDL_AudioSpec(44100, sdl2.AUDIO_S16LSB, 1, 1024)
            have = sdl2.SDL_AudioSpec(0, 0, 0, 0)
            self.dev = sdl2.SDL_OpenAudioDevice(None, 0, want, ctypes.byref(have), 0)
            if self.dev:
                sdl2.SDL_PauseAudioDevice(self.dev, 0)
            else:
                self.dead = True
                self.log("sonido: no se pudo abrir el audio: %s" % sdl2.SDL_GetError())
        except Exception:
            self.dead = True
            self.log("sonido: error\n" + traceback.format_exc())
        return bool(self.dev)

    def play(self, style, kind):
        if not style or style == "off":
            return
        try:
            d = self._wav(style, kind)
            if not d or not self._open():
                return
            now = time.time()
            if kind == "move" and now - self.last < 0.04:
                return
            if sdl2.SDL_GetQueuedAudioSize(self.dev) > 0:     # pulsaciones rapidas: corta el anterior, no se acumulan
                sdl2.SDL_ClearQueuedAudio(self.dev)
            self.last = now
            sdl2.SDL_QueueAudio(self.dev, d, len(d))
        except Exception:
            self.dead = True
            self.log("sonido: error\n" + traceback.format_exc())

    def close(self):
        """Deja terminar el sonido en curso (hasta 0.35 s) y libera el dispositivo."""
        if not self.dev:
            return
        try:
            end = time.time() + 0.35
            while time.time() < end and sdl2.SDL_GetQueuedAudioSize(self.dev) > 0:
                time.sleep(0.02)
            sdl2.SDL_CloseAudioDevice(self.dev)
        except Exception:
            pass
        self.dev = 0
