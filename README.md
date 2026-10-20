# Tonic Tumble

An original falling-capsule puzzle game built on the [AngheloAlf/drmario64](https://github.com/AngheloAlf/drmario64)
decomp (MIT). The program is compiled from the decompilation's C sources; every picture, tune, sound effect, sample,
3D shape and line of text was generated for this project. Hero **Dr. Fenna**, rival **Grudge**.

Play: **https://andrewnakas.github.io/drmario64-cleanroom/** (EmulatorJS + a patched mupen64plus-next core; no ROM needed).

Keys: **Arrows** move / drop · **X** A (rotate) · **Z** B (rotate back) · **Enter** Start · **Space** Z · **Q / W** L / R ·
**I J K L** C buttons. Gamepads work too.

## What is kept, what is new

| Part | Kept (structure only) | New |
|---|---|---|
| Code | the decomp's C/asm sources | compiled with mips64-elf GCC (non-matching build), our CC0 IPL3 boot stub, ROM name TONIC TUMBLE |
| RSP microcode | family, version and segment sizes | CRUCODE1 placeholder tags (`cleanroom/ucode.py`); runs only on HLE cores patched for the tags |
| Textures (1205) | name, format, size, palette grouping | every image drawn by our generators (`games/drmario64/art/`) |
| Geometry (323 vertex arrays) | vertex counts, display-list topology, UV orientation | positions, UVs, colours; 3D meshes reshaped |
| Music (24 songs, 104 effects) | tempo, intro/loop length, channel roles and registers | notes composed by `cleanroom.audio.compose`; effects regenerated |
| Samples (190) | length, loop points, codebook size | resynthesised |
| Text (1131 strings) | control codes, line counts and widths | all wording ours (`games/drmario64/text/rewrites.json`) |

Publish gates, both 0 failing: [ORIGINALITY.md](ORIGINALITY.md) (`cleanroom.originality`: music, text, geometry,
images, code) and [TAINT.md](TAINT.md) (every original asset byte window searched over the whole ROM image, plus the
microcode scan).

## Building

The generators need facts measured from your own copy of the original game (the "dirty room"); those files are not
in this repository: `games/drmario64/spec/samples.json`, `spec/label_boxes.json`, `spec/geometry.json`, the voice-line
list and the gate's name list are written locally by `extract_spec.py` / `extract_more.py` / `find_labels.py`.

- Assets: `python -m games.drmario64.assets <spec_local> <cassets>`
- ROM: `python -m games.drmario64.build_decomp <decomp checkout> <cassets> <cbuild> -j 2`
- Site: `python ports/ejs/make_site.py <rom> <EmulatorJS dir> <site> --core <patched mupen64plus_next-wasm.data> --core-src <ucode-tags dir>`
  then `python ports/ejs/patch_core.py <site>/tonictumble.z64 <site>/data/cores <site>/data/cores`

Licence: MIT (`LICENSE`). Fonts: OFL / Apache-2.0, licence files in `games/drmario64/fonts/`.
