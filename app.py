"""
AirPlay Audio Sender
====================

Envia el audio del sistema de Windows a un HomePod (u otro receptor
AirPlay/RAOP) sin instalar nada ni usar un driver de audio virtual.

  1. Captura el audio de Windows con WASAPI en modo loopback (soundcard).
  2. Lo empaqueta como un flujo WAV "en vivo" (live_wav_stream.py).
  3. Usa pyatv para descubrir el HomePod y transmitirle el audio.
"""

import asyncio
import threading

import numpy as np
import soundcard as sc

import pyatv
from pyatv.const import Protocol, PairingRequirement
from pyatv.storage.file_storage import FileStorage

from live_wav_stream import LiveWavStream

SAMPLE_RATE = 48000
CHANNELS = 2
BLOCKSIZE = 960
BYTES_PER_SAMPLE = 2


def audio_capture_thread(live_stream, stop_event):
    """Captura el audio de salida de Windows (loopback) y lo empuja al flujo."""
    try:
        speaker = sc.default_speaker()
        mic = sc.get_microphone(speaker.id, include_loopback=True)
    except Exception as exc:
        print(f"\n[ERROR] No se pudo abrir el dispositivo de audio: {exc}")
        live_stream.stop()
        return

    print(f"Capturando el audio de: {speaker.name}")

    try:
        with mic.recorder(samplerate=SAMPLE_RATE, channels=CHANNELS, blocksize=BLOCKSIZE) as rec:
            while not stop_event.is_set():
                data = rec.record(numframes=BLOCKSIZE)
                pcm16 = np.clip(data * 32767.0, -32768, 32767).astype("<i2")
                live_stream.push(pcm16.tobytes())
    except Exception as exc:
        print(f"\n[ERROR] Fallo durante la captura de audio: {exc}")
    finally:
        live_stream.stop()


async def discover_devices(storage):
    loop = asyncio.get_event_loop()
    print("Buscando dispositivos AirPlay en la red (5 segundos)...")
    return await pyatv.scan(loop, protocol={Protocol.RAOP}, storage=storage)


async def ensure_paired(config, loop, storage):
    """Empareja solo si hace falta. Devuelve True si se puede transmitir."""
    service = config.get_service(Protocol.RAOP)
    if service is None:
        print("Este dispositivo no soporta el protocolo de audio RAOP.")
        return False

    if service.credentials:
        print("Ya emparejado anteriormente (usando credenciales guardadas).")
        return True

    if service.pairing in (PairingRequirement.NotNeeded, PairingRequirement.Optional):
        print("Este dispositivo no necesita emparejamiento.")
        return True

    if service.pairing in (PairingRequirement.Disabled, PairingRequirement.Unsupported):
        print(
            "El HomePod no permite emparejar desde este programa.\n"
            "En la app Casa (iPhone): manten presionado el HomePod > Ajustes > "
            "'Permitir acceso al altavoz' y elige 'Todos' o "
            "'Cualquiera en la misma red'."
        )
        return False

    print(f"\nEmparejando con '{config.name}' por primera vez...")
    pairing = await pyatv.pair(config, Protocol.RAOP, loop, storage=storage)
    try:
        await pairing.begin()
        if pairing.device_provides_pin:
            pin = input("Introduce el PIN que muestra el dispositivo: ").strip()
            pairing.pin(pin)
        else:
            pairing.pin(1234)
        await pairing.finish()

        if pairing.has_paired:
            print("Emparejamiento exitoso.")
            return True
        print("El emparejamiento no se completo. Intenta de nuevo.")
        return False
    finally:
        await pairing.close()


async def stream_to_device(config, loop, stop_event):
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


async def main():
    loop = asyncio.get_event_loop()
    storage = FileStorage.default_storage(loop)
    await storage.load()

    devices = await discover_devices(storage)
    if not devices:
        print(
            "\nNo se encontro ningun dispositivo AirPlay.\n"
            "Verifica que el HomePod y esta computadora esten en la misma red Wi-Fi,"
            " y que ningun firewall bloquee el descubrimiento (UDP 5353, mDNS)."
        )
        return

    print("\nDispositivos encontrados:")
    for i, d in enumerate(devices):
        print(f"  [{i}] {d.name}  ({d.address})")

    while True:
        try:
            idx = int(input("\nElige el numero del dispositivo: ").strip())
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
