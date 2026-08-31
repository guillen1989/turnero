# Release del TWA de Android a Play Store

Este directorio solo versiona `twa-manifest.json` (y este archivo). El resto del
proyecto Android (`app/`, `build.gradle`, `gradlew`, etc.) se regenera bajo demanda
con `bubblewrap update` a partir de ese manifiesto.

## Por qué Docker

El Node.js del host (v12) es demasiado antiguo para `@bubblewrap/cli` (requiere >=14.15).
Se usa un contenedor `node:18-bullseye` con JDK 17, montando el SDK de Android, la caché
de Gradle y este directorio del host.

## Primera vez / si el contenedor `bubblewrap-work` no existe

```bash
docker run -d --name bubblewrap-work \
  -v /home/portatil/Android/Sdk:/opt/android-sdk \
  -v ~/.gradle:/root/.gradle \
  -v /home/portatil/desarrollo/turnero/android-twa:/work \
  node:18-bullseye sleep infinity

docker exec bubblewrap-work bash -c '
  apt-get update -qq && apt-get install -y -qq openjdk-17-jdk-headless unzip
  npm install -g @bubblewrap/cli
  mkdir -p /root/.bubblewrap
  echo "{\"jdkPath\":\"/usr/lib/jvm/java-17-openjdk-amd64\",\"androidSdkPath\":\"/opt/android-sdk\"}" > /root/.bubblewrap/config.json
'
```

Si el SDK montado no tiene `cmdline-tools` (comprobar con
`ls /opt/android-sdk/cmdline-tools`), instalarlas:

```bash
docker exec bubblewrap-work bash -c '
  cd /tmp
  curl -sSL -o cmdline-tools.zip https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip
  mkdir -p /opt/android-sdk/cmdline-tools/latest
  unzip -q cmdline-tools.zip -d /tmp/cmdline-tools-extract
  mv /tmp/cmdline-tools-extract/cmdline-tools/* /opt/android-sdk/cmdline-tools/latest/
  export ANDROID_SDK_ROOT=/opt/android-sdk JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
  yes | /opt/android-sdk/cmdline-tools/latest/bin/sdkmanager --licenses --sdk_root=/opt/android-sdk
  /opt/android-sdk/cmdline-tools/latest/bin/sdkmanager --sdk_root=/opt/android-sdk "build-tools;36.0.0"
'
```

`bubblewrap build` busca `sdkmanager` en `<androidSdkPath>/bin/sdkmanager`, una ruta
que `cmdline-tools` no crea por sí sola. Hay que enlazarla a mano (una sola vez, se
pierde solo si se recrea el contenedor):

```bash
docker exec bubblewrap-work bash -c '
  mkdir -p /opt/android-sdk/bin
  ln -sf /opt/android-sdk/cmdline-tools/latest/bin/sdkmanager /opt/android-sdk/bin/sdkmanager
'
```

Copiar el keystore de subida (una sola vez, no se versiona):

```bash
cp ~/upload-keystore.jks /home/portatil/desarrollo/turnero/android-twa/android-keystore.jks
```

## Rebuild (cada nueva versión)

1. Edita `twa-manifest.json` si hace falta cambiar algo más allá de la versión
   (bubblewrap gestiona `appVersionName`/`appVersionCode` en el siguiente paso).
2. Regenera el proyecto Android y sube de versión (te pedirá el nuevo `versionName`;
   el `versionCode` se incrementa solo):

   ```bash
   docker exec -it bubblewrap-work bash -c '
     export ANDROID_SDK_ROOT=/opt/android-sdk ANDROID_HOME=/opt/android-sdk JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
     cd /work && bubblewrap update
   '
   ```

3. Compila y firma (te pedirá las contraseñas del keystore y de la clave — escríbelas
   tú, no se deben automatizar ni guardar en ningún sitio):

   ```bash
   docker exec -it bubblewrap-work bash -c '
     export ANDROID_SDK_ROOT=/opt/android-sdk ANDROID_HOME=/opt/android-sdk JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
     cd /work && bubblewrap build
   '
   ```

4. El resultado queda en `android-twa/app-release-bundle.aab` (subir esto a Play
   Console) y `android-twa/app-release-signed.apk` (para probar en un dispositivo).

## Seguridad

- `android-keystore.jks` y las contraseñas del keystore NUNCA deben commitearse ni
  pegarse en el chat. El `.gitignore` de la raíz ya excluye todo `android-twa/`
  salvo `twa-manifest.json` y este archivo.
- Nunca ejecutar `git add -A` / `git add .` dentro de `android-twa/`.
