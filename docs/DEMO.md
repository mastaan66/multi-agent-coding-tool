# Demo and media

The README media is generated from repository-owned sources.

## Watch

- [MP4 walkthrough](assets/demo.mp4)
- [Animated GIF](assets/demo.gif)
- [Quick-start terminal image](assets/quickstart.svg)
- [Architecture diagram](assets/architecture.svg)

## Regenerate

Requirements:

- ImageMagick with the convert command
- FFmpeg
- DejaVu Sans Mono or a font supplied through AI_FACTORY_DEMO_FONT

Run:

~~~bash
make media
~~~

The render script uses deterministic terminal frames and does not require API
credentials or network access.
