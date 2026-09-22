"""
AirPlay Audio Sender
====================

Envia el audio del sistema de Windows a un HomePod (u otro receptor
AirPlay/RAOP) sin necesidad de instalar nada ni de usar un driver de audio
virtual.

Como funciona:
  1. Captura el audio que Windows ya esta reproduciendo, usando la API nativa
     WASAPI en modo "loopback" (a traves de la libreria `soundcard`). Esto no
     requiere ningun driver adicional: es una funcion del propio Windows.
  2. Empaqueta ese audio como un flujo WAV "en vivo" (ver live_wav_stream.py).
  3. Usa `pyatv` (libreria de codigo abierto para AirPlay/RAOP) para
     descubrir el HomePod en la red, emparejarse una sola vez, y transmitirle
     el audio en tiempo real.

Uso:
    python app.py

Compilado como .exe portable con PyInstaller, se ejecuta igual, sin consola
de Python visible (ver README.md para instrucciones de compilacion).
"""

import asyncio
import sys
import threading

import numpy as np
import soundcard as sc

import pyatv
from pyatv.const import Protocol
from pyatv.storage.file_storage import FileStorage

from live_wav_stream import LiveWavStream

# --- Configuracion de captura de audio ---
SAMPLE_RATE = 48000     # frecuencia a la que capturamos de Windows
CHANNELS = 2
BLOCKSIZE = 960         # ~20ms por bloque a 48000Hz: buen balance latencia/CPU
BYTES_PER_SAMPLE = 2    # convertimos a PCM de 16 bits antes de empaquetar


def audio_capture_thread(live_stream: LiveWavStream, stop_event: threading.Event) -> None:
    """Hilo que captura el audio de salida de Windows (loopback) y lo empuja
    al flujo en vivo que pyatv esta leyendo."""
    try:
        speaker = sc.default_speaker()
        mic = sc.get_microphone(speaker.id, include_loopback=True)
    except Exception as exc:  # pragma: no cover - depende del hardware real
        print(f"\n[ERROR] No se pudo abrir el dispositivo de audio para captura: {exc}")
        live_stream.stop()
        return

    print(f"Capturando el audio de: {speaker.name}")

    try:
        with mic.recorder(samplerate=SAMPLE_RATE, channels=CHANNELS, blocksize=BLOCKSIZE) as rec:
            while not stop_event.is_set():
                data = rec.record(numframes=BLOCKSIZE)  # float32, forma (frames, canales)
                pcm16 = np.clip(data * 32767.0, -32768, 32767).astype("<i2")
                live_stream.push(pcm16.tobytes())
    except Exception as exc:  # pragma: no cover - depende del hardware real
        print(f"\n[ERROR] Fallo durante la captura de audio: {exc}")
    finally:
        live_stream.stop()


async def discover_devices(storage):
    loop = asyncio.get_event_loop()
    print("Buscando dispositivos AirPlay en la red (5 segundos)...")
    devices = await pyatv.scan(loop, protocol={Protocol.RAOP}, storage=storage)
    return devices


async def ensure_paired(config, loop, storage) -> bool:
    """Empareja con el dispositivo si todavia no tenemos credenciales
    guardadas de una vez anterior. Devuelve True si quedo listo para
    transmitir."""
    service = config.get_service(Protocol.RAOP)
    if service is None:
        print("Este dispositivo no soporta el protocolo de audio RAOP.")
        return False

    if service.credentials:
        print("Ya emparejado anteriormente (usando credenciales guardadas).")
        return True

    print(f"\nEmparejando con '{config.name}' por primera vez...")
    pairing = await pyatv.pair(config, Protocol.RAOP, loop, storage=storage)
    try:
        await pairing.begin()
        if pairing.device_provides_pin:
            pin = input(
                "Introduce el codigo PIN que muestra o anuncia el HomePod: "
            ).strip()
            pairing.pin(pin)
        else:
            pairing.pin(1234)
        await pairing.finish()

        if pairing.has_paired:
            print("Emparejamiento exitoso.")
            return True
        else:
            print("El emparejamiento no se completo. Intenta de nuevo.")
            return False
    finally:
        await pairing.close()


async def stream_to_device(config, loop, stop_event: threading.Event) -> None:
    atv = await pyatv.connect(config, loop)
    live_stream = LiveWavStream(SAMPLE_RATE, CHANNELS, BYTES_PER_SAMPLE)

    capture_thread = threading.Thread(
        target=audio_capture_thread, args=(live_stream, stop_event), daemon=True
    )
    capture_thread.start()

    print(f"\nTransmitiendo el audio de Windows a '{config.name}'.")
    print("Presiona Ctrl+C en esta ventana para detener.\n")

    try:
        await atv.stream.stream_file(live_stream)
    finally:
        stop_event.set()
        pending = atv.close()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)


async def main() -> None:
    loop = asyncio.get_event_loop()
    storage = FileStorage.default_storage(loop)
    await storage.load()

    devices = await discover_devices(storage)
    if not devices:
        print(
            "\nNo se encontro ningun dispositivo AirPlay.\n"
            "Verifica que el HomePod y esta computadora esten en la misma red Wi-Fi,"
            " y que ningun firewall este bloqueando el descubrimiento (puerto UDP 5353,"
            " mDNS/Bonjour)."
        )
        return

    print("\nDispositivos encontrados:")
    for i, d in enumerate(devices):
        print(f"  [{i}] {d.name}  ({d.address})")

    while True:
        try:
            idx = int(input("\nElige el numero del dispositivo al que quieres transmitir: ").strip())
            config = devices[idx]
            break
        except (ValueError, IndexError):
            print("Numero invalido, intenta de nuevo.")

    paired = await ensure_paired(config, loop, storage)
    await storage.save()
    if not paired:
        return

    stop_event = threading.Event()
    try:
        await stream_to_device(config, loop, stop_event)
    except KeyboardInterrupt:
        stop_event.set()
    finally:
        await storage.save()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDetenido por el usuario.")
    input("\nPresiona Enter para salir...")
