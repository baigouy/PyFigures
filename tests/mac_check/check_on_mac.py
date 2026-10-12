"""Play the sample videos with Apple's AVFoundation — the decoder behind
QuickTime, Safari, Keynote and PowerPoint on a Mac — and compare what it shows
with tests/mac_check/samples/expected.json. Runs on a macOS GitHub runner
(.github/workflows/mac_video_check.yml); needs numpy and
pyobjc-framework-AVFoundation (which brings CoreMedia and Quartz).

Exit code 0 = every sample is playable and decodes to the expected frames.
"""
import json
import os
import sys

import numpy as np

import AVFoundation
import CoreMedia
import Quartz
from Foundation import NSURL

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(HERE, "samples")
TOLERANCE = 6.0     # grey levels; a 16-235 range mix-up shifts 30 -> 42


def _decode_all(asset, track):
    """Number of frames AVAssetReader decodes (to 32BGRA), and its final status."""
    reader, err = AVFoundation.AVAssetReader.alloc().initWithAsset_error_(asset, None)
    if reader is None:
        return 0, f"no reader: {err}"
    settings = {"PixelFormatType": 1111970369}            # kCVPixelFormatType_32BGRA
    out = AVFoundation.AVAssetReaderTrackOutput.alloc().initWithTrack_outputSettings_(
        track, settings)
    reader.addOutput_(out)
    if not reader.startReading():
        return 0, f"cannot start reading: {reader.error()}"
    n = 0
    while True:
        buf = out.copyNextSampleBuffer()
        if buf is None:
            break
        if CoreMedia.CMSampleBufferGetNumSamples(buf) > 0:
            n += 1
    status = reader.status()                                # 2 = completed
    return n, None if status == 2 else f"reader status {status}: {reader.error()}"


def _frame_mean(asset, fps, i):
    """Mean of the R, G, B values of frame i as AVFoundation renders it."""
    gen = AVFoundation.AVAssetImageGenerator.assetImageGeneratorWithAsset_(asset)
    gen.setRequestedTimeToleranceBefore_(CoreMedia.kCMTimeZero)
    gen.setRequestedTimeToleranceAfter_(CoreMedia.kCMTimeZero)
    t = CoreMedia.CMTimeMakeWithSeconds((i + 0.5) / fps, 600)
    img, _actual, err = gen.copyCGImageAtTime_actualTime_error_(t, None, None)
    if img is None:
        raise RuntimeError(f"no image for frame {i}: {err}")
    w = Quartz.CGImageGetWidth(img)
    h = Quartz.CGImageGetHeight(img)
    bpr = Quartz.CGImageGetBytesPerRow(img)
    if Quartz.CGImageGetBitsPerPixel(img) != 32:
        raise RuntimeError(f"unexpected {Quartz.CGImageGetBitsPerPixel(img)} bits per pixel")
    data = Quartz.CGDataProviderCopyData(Quartz.CGImageGetDataProvider(img))
    px = np.frombuffer(bytes(data), np.uint8).reshape(h, bpr)[:, : w * 4]
    px = px.reshape(h, w, 4).astype(np.float64)
    # opaque video: alpha (or the skipped byte) is 255 wherever it sits in the
    # pixel, so the colour mean follows without knowing the byte order
    skipped = px.min(axis=(0, 1)).argmax() if px.min(axis=(0, 1)).max() == 255 else None
    if skipped is None:
        raise RuntimeError("cannot find the alpha byte")
    return float(np.delete(px, skipped, axis=2).mean()), (w, h)


def check(name, exp):
    path = os.path.join(SAMPLES, name)
    asset = AVFoundation.AVURLAsset.URLAssetWithURL_options_(NSURL.fileURLWithPath_(path), None)
    problems = []
    if not asset.isPlayable():
        problems.append("AVFoundation says it is NOT playable")
    tracks = asset.tracksWithMediaType_(AVFoundation.AVMediaTypeVideo)
    if not tracks:
        return problems + ["no video track"]
    track = tracks[0]
    size = track.naturalSize()
    if "width" in exp and (round(size.width), round(size.height)) != (exp["width"], exp["height"]):
        problems.append(f"size {size.width}x{size.height}, expected {exp['width']}x{exp['height']}")
    fps = track.nominalFrameRate()
    if abs(fps - exp["fps"]) > 0.05:
        problems.append(f"fps {fps}, expected {exp['fps']}")
    n, err = _decode_all(asset, track)
    if err:
        problems.append(err)
    if n != exp["frames"]:
        problems.append(f"decoded {n} frames, expected {exp['frames']}")
    for i, want in enumerate(exp.get("means", [])):
        got, _ = _frame_mean(asset, exp["fps"], i)
        if abs(got - want) > TOLERANCE:
            problems.append(f"frame {i}: mean {got:.1f}, expected {want:.1f}")
    return problems


def main():
    with open(os.path.join(SAMPLES, "expected.json"), encoding="utf-8") as f:
        expected = json.load(f)
    failed = 0
    for name, exp in sorted(expected.items()):
        problems = check(name, exp)
        print(("FAIL " if problems else "OK   ") + name)
        for p in problems:
            print("     - " + p)
        failed += bool(problems)
    print(f"{len(expected) - failed}/{len(expected)} samples play correctly on macOS")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
