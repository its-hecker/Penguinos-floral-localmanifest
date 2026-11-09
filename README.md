# PenguinOS for Pixel 4 XL (coral)

This is the Android 17 `celerity` build configuration for `coral`.
It uses the PixelOS device tree and vendor, the Floral 4.14 KernelSU Next
kernel, Lunaris Dolby, hardware 3D Face ID, Motion Sense, Active Edge, and
the signed Google Camera split set.

The first compile and phone validation are pending. The pinned device-tree
commit must be present on the `main` branch of
[penguinos-floral-dt](https://github.com/its-hecker/penguinos-floral-dt)
before the initial sync.

From a fresh ServerHive checkout:

```bash
mkdir -p ~/penguinos-coral
cd ~/penguinos-coral
repo init -u https://github.com/Project-PenguinOS/manifest.git -b celerity --git-lfs
git clone -b main https://github.com/its-hecker/Penguinos-floral-localmanifest.git .repo/local_manifests
repo sync -c --fail-fast --no-clone-bundle --no-tags -j4
bash .repo/local_manifests/build.sh coral -g
```

The build helper runs the hardware preparation before invoking PenguinOS's
build script. Use `-l` to select the upstream vanilla build option.
