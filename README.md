# for-web-bearnet

Build recipe for Bear-Net's Stoat web client image. It checks out upstream
[stoatchat/for-web](https://github.com/stoatchat/for-web) at a pinned commit,
generates real notification sounds (`make_sounds.py`) over the silent fallback
placeholders the public images ship with, and pushes the result to
`ghcr.io/jchebert1/for-web-bearnet`.

Run it from the Actions tab (Build Bear-Net for-web image -> Run workflow).
The server opts in via the `image:` line for the `web` service in `compose.yml`.
Rollback: point that line back at the previous `ghcr.io/stoatchat/for-web` tag.

No upstream code is modified; this repo owns only the sounds and the build.
