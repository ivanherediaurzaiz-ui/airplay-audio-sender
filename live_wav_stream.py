"""
LiveWavStream: presenta un flujo de audio en vivo (que nunca "termina") como si
fuera un archivo WAV, para que pyatv (a traves de miniaudio) pueda decodificarlo
igual que un .wav normal, chunk a chunk, sin conocer la duracion total de
antemano.
"""

import io
import queue
import struct


class LiveWavStream(io.BufferedIOBase):
    def __init__(self, sample_rate: int, channels: int, bytes_per_sample: int = 2):
        super().__init__()
        self.sample_rate = sample_rate
        self.channels = channels
        self.bytes_per_sample = bytes_per_sample
        self._queue = queue.Queue(maxsize=200)
        self._pending = b""
        self._header_sent = False
        self._stopped = False

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False

    def read(self, size: int = -1) -> bytes:
        if self._stopped and self._queue.empty() and not self._pending:
            return b""

        chunks = []
        if not self._header_sent:
            chunks.append(self._make_wav_header())
            self._header_sent = True

        got = sum(len(c) for c in chunks)
        while size == -1 or got < size:
            if self._pending:
                chunks.append(self._pending)
                got += len(self._pending)
                self._pending = b""
                if size != -1:
                    break
                continue

            item = self._queue.get()
            if item is None:
                self._stopped = True
                break
            chunks.append(item)
            got += len(item)
            if size != -1:
                break

        data = b"".join(chunks)
        if size != -1 and len(data) > size:
            self._pending = data[size:] + self._pending
            data = data[:size]
        return data

    def push(self, pcm_bytes: bytes) -> None:
        if pcm_bytes:
            self._queue.put(pcm_bytes)

    def stop(self) -> None:
        self._queue.put(None)

    def _make_wav_header(self) -> bytes:
        byte_rate = self.sample_rate * self.channels * self.bytes_per_sample
        block_align = self.channels * self.bytes_per_sample
        bits_per_sample = self.bytes_per_sample * 8
        huge = 0x7FFFFFFF
        return struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF", huge, b"WAVE",
            b"fmt ", 16, 1, self.channels, self.sample_rate,
            byte_rate, block_align, bits_per_sample,
            b"data", huge,
        )
