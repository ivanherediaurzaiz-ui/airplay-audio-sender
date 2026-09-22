# AirPlay Audio Sender

Envía el audio de tu computadora con Windows a un HomePod (u otro receptor
AirPlay/RAOP), sin instalar nada en la computadora: ni programa, ni driver de
audio virtual, ni permisos de administrador.

- La captura de audio usa **WASAPI en modo loopback**, una función nativa de
  Windows (no un driver de terceros).
- El envío por AirPlay usa **pyatv**, una librería de código abierto (MIT).
- El resultado final es un único archivo `AirPlayAudioSender.exe` que corres
  directamente, sin instalador.

## ⚠️ Importante antes de empezar

Esto es software recién construido para tu caso, no un producto probado por
miles de personas. Es muy probable que la primera vez necesitemos ajustar
algo según lo que veas en pantalla (mensajes de error, etc.) — no te
desanimes si no funciona a la primera.

## Paso 1: Obtener el .exe (se compila en la nube, no en tu computadora)

Como el .exe de Windows no se puede generar en este entorno, la compilación
se hace gratis en los servidores de GitHub (GitHub Actions), y tú solo te
descargas el resultado. No necesitas instalar Python, Git, ni nada más en tu
computadora de trabajo para este paso — solo un navegador.

1. Entra a [github.com](https://github.com) y crea una cuenta gratuita si no
   tienes una (puedes hacerlo desde cualquier computadora, no tiene que ser
   la del trabajo).
2. Crea un repositorio nuevo, **público** (los repos públicos tienen minutos
   de GitHub Actions gratis ilimitados), por ejemplo llamado
   `airplay-audio-sender`.
3. Usando el botón **"Add file" → "Upload files"** en la página del
   repositorio (funciona arrastrando archivos, sin necesidad de instalar
   Git), sube estos archivos manteniendo la misma estructura de carpetas:
   - `app.py`
   - `live_wav_stream.py`
   - `requirements.txt`
   - `.gitignore`
   - `.github/workflows/build-windows.yml`
4. Ve a la pestaña **"Actions"** del repositorio. Debería aparecer un
   workflow llamado "Compilar AirPlayAudioSender.exe" ejecutándose
   automáticamente (tarda 2-3 minutos).
5. Cuando termine (ícono verde ✅), haz clic en esa ejecución y baja hasta
   **"Artifacts"**. Ahí vas a encontrar `AirPlayAudioSender-windows`,
   descárgalo (es un .zip que contiene el .exe).

## Paso 2: Usarlo en la computadora de trabajo

1. Copia `AirPlayAudioSender.exe` a tu computadora de trabajo (USB, correo,
   OneDrive, lo que uses normalmente para pasar archivos).
2. Asegúrate de que la computadora y el HomePod estén en la **misma red
   Wi-Fi**.
3. Haz doble clic en `AirPlayAudioSender.exe`. Se abrirá una ventana de
   consola (es normal, es la interfaz del programa).
4. Windows probablemente muestre una advertencia de SmartScreen porque el
   .exe no está firmado digitalmente (firmar código cuesta dinero y este
   proyecto es gratuito). Si tu política de empresa lo permite, haz clic en
   "Más información" → "Ejecutar de todas formas". **Si tu computadora de
   trabajo bloquea esto a nivel de política de IT, este método no va a
   funcionar y tendrías que hablar con tu departamento de sistemas.**
5. El programa buscará dispositivos AirPlay en la red y los listará
   numerados. Escribe el número del HomePod y presiona Enter.
6. La primera vez, el HomePod pedirá un código PIN (lo vas a escuchar que el
   HomePod lo "dice" en voz alta, o puede aparecer en la app Casa de un
   iPhone cercano). Escríbelo en la consola cuando se te pida.
7. Después de emparejar, el audio de Windows debería empezar a sonar en el
   HomePod. Para detener, cierra la ventana o presiona Ctrl+C.

La próxima vez que abras el programa no debería volver a pedir el PIN (las
credenciales quedan guardadas en un archivo `.pyatv.conf` en tu carpeta de
usuario).

## Si algo no funciona

Copia el mensaje de error exacto que aparece en la consola y compártelo — con
eso puedo ajustar el código. Algunos problemas comunes esperables:

- **"No se encontró ningún dispositivo AirPlay"**: revisa que ambos estén en
  la misma red Wi-Fi, y que el firewall de la empresa no esté bloqueando el
  descubrimiento mDNS/Bonjour (puerto UDP 5353).
- **El PIN no es aceptado**: intenta de nuevo; a veces el HomePod tarda unos
  segundos en anunciar el PIN correcto.
- **Audio entrecortado**: es un proyecto nuevo sin optimizar a fondo; se
  puede ajustar el tamaño de los bloques de audio (`BLOCKSIZE` en `app.py`).
- **SmartScreen / antivirus bloquea el .exe**: normal para software sin
  firmar; si tu empresa no lo permite, este enfoque no es viable ahí.

## Qué hace cada archivo

| Archivo | Para qué sirve |
|---|---|
| `app.py` | Programa principal: descubre, empareja y transmite |
| `live_wav_stream.py` | Convierte el audio capturado en un flujo que pyatv puede transmitir en vivo |
| `requirements.txt` | Librerías de Python necesarias |
| `.github/workflows/build-windows.yml` | Le dice a GitHub cómo compilar el .exe automáticamente |
