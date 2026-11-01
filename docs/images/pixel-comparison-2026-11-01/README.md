# Pixel comparison — November 1, 2026

[PNG chart](pixel-jetlink-comparison.png) · [SVG chart](pixel-jetlink-comparison.svg) · [Copyable text](pixel-jetlink-comparison.txt) · [Chart data](pixel-jetlink-comparison.json)

One 12,000-frame run per phone, using the same JetLink APK and Cinque Terre V2 source model with each chipset's compilation. Twenty warmup frames per phone are reported separately. Pixel 10 timing overruns were recorded without stopping; all measured slow frames remain in the statistics.

The chart shows phone processing time from synthetic desk tests. It excludes transport and does not qualify direct comma USB or driving. The [Pixel 10 report](../../PIXEL10_TESTS_2026-11-01.md) retains its two earlier strict stops and full diagnostic measurement. The [Pixel 11 report](../../PIXEL_LONG_TESTS_2026-11-01.md) retains both completed long runs; only its first run appears here.

To render the saved chart data locally with Python, NumPy and Matplotlib installed:

```sh
python render_comparison.py pixel-jetlink-comparison.json
```

The renderer uses the sanitized JSON. Raw device captures, private compiler/model files and device identifiers are not included.
