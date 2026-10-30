"""專注時的白噪音：貓咪呼嚕聲、雨聲、壁爐柴火聲（只在專注時播放，音量很小）。

聲音是第一次用到時用程式合成的（不需要額外的音檔），存成 WAV 放在暫存資料夾，
再用 macOS 內建的 afplay 循環播放；休息或停止番茄鐘就停下來。
"""
import math
import os
import random
import shutil
import struct
import tempfile
import wave

from PySide6.QtCore import QObject, QProcess

SOUNDS = ["off", "purr", "rain", "fire"]
RATE = 22050
SECONDS = 8
VOLUME = "0.35"


def _lowpass(samples, k):
    out, y = [], 0.0
    for x in samples:
        y += k * (x - y)
        out.append(y)
    return out


def _normalize(samples, peak=0.5):
    m = max(1e-6, max(abs(v) for v in samples))
    return [v / m * peak for v in samples]


def _loopable(samples, fade=RATE // 2):
    """頭尾交叉淡入淡出，循環播放時才不會有接縫。"""
    n = len(samples) - fade
    out = samples[:n]
    for i in range(fade):
        t = i / fade
        out[i] = out[i] * t + samples[n + i] * (1 - t)
    return out


def synth(kind, seed=7):
    rnd = random.Random(seed)
    n = RATE * SECONDS + RATE // 2
    noise = [rnd.uniform(-1, 1) for _ in range(n)]
    if kind == "purr":
        # 低沉的呼嚕：很低頻的噪音，每秒震動約 25 下，跟著呼吸一吸一吐
        base = _lowpass(_lowpass(noise, 0.02), 0.05)
        out = []
        for i, v in enumerate(base):
            t = i / RATE
            flutter = 0.55 + 0.45 * math.sin(2 * math.pi * 24 * t)
            breath = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(2 * math.pi * t / 2.6))
            out.append(v * flutter * breath)
        out = _normalize(out, 0.6)
    elif kind == "rain":
        # 綿綿細雨：柔和的粉紅噪音，加上一點一點的雨滴聲
        soft = _lowpass(noise, 0.18)
        out = [v * 0.5 for v in soft]
        for _ in range(SECONDS * 40):
            pos = rnd.randrange(0, n - 200)
            amp = rnd.uniform(0.15, 0.5)
            for j in range(120):
                out[pos + j] += amp * math.exp(-j / 18) * math.sin(j * rnd.uniform(0.6, 1.2))
        out = _normalize(_lowpass(out, 0.5), 0.5)
    else:
        # 壁爐：低沉的火焰聲，偶爾劈啪一下
        low = _lowpass(_lowpass(noise, 0.03), 0.08)
        out = [v * 0.8 for v in low]
        for _ in range(SECONDS * 6):
            pos = rnd.randrange(0, n - 600)
            amp = rnd.uniform(0.3, 0.9)
            for j in range(rnd.randint(40, 500)):
                out[pos + j] += amp * math.exp(-j / 30) * rnd.uniform(-1, 1)
        out = _normalize(out, 0.55)
    return _loopable(out)


def wav_path(kind):
    folder = os.path.join(tempfile.gettempdir(), "meowmentum-sounds")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{kind}-v1.wav")
    if not os.path.exists(path):
        data = synth(kind)
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, v)) * 32000)) for v in data))
    return path


class FocusSound(QObject):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        kind = str(settings.value("focus_sound", "off"))
        self.kind = kind if kind in SOUNDS else "off"
        self.proc = None
        self.playing = False

    def available(self):
        return shutil.which("afplay") is not None

    def set_kind(self, kind):
        self.kind = kind
        self.settings.setValue("focus_sound", kind)
        if self.playing:
            self.stop()
            self.start()

    def start(self):
        if self.kind == "off" or not self.available():
            return
        self.playing = True
        self._play()

    def _play(self):
        if not self.playing:
            return
        self.proc = QProcess(self)
        self.proc.finished.connect(lambda *_: self._play())       # 播完再播一次：循環
        self.proc.start("afplay", ["-v", VOLUME, wav_path(self.kind)])

    def stop(self):
        self.playing = False
        if self.proc is not None:
            try:
                self.proc.finished.disconnect()
            except Exception:
                pass
            self.proc.kill()
            self.proc = None
