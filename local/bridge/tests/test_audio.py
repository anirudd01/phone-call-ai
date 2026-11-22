import numpy as np

from carwash_bridge.audio import FRAME_BYTES, Framer, JitterBuffer, PcmResampler


def test_framer_returns_whole_20ms_frames() -> None:
    f = Framer()
    assert f.push(bytes(FRAME_BYTES - 10)) == []
    frames = f.push(bytes(FRAME_BYTES + 10))
    assert [len(x) for x in frames] == [FRAME_BYTES, FRAME_BYTES]
    assert f.push(bytes(FRAME_BYTES - 20)) == []
    assert f.push(bytes(20)) == [bytes(FRAME_BYTES)]


def test_resampler_changes_length_by_the_rate_ratio() -> None:
    tone = (np.sin(np.arange(4800) / 10) * 8000).astype(np.int16).tobytes()  # 100 ms at 48 kHz
    r = PcmResampler(48000, 16000)
    out = b"".join(r.process(tone) for _ in range(10))  # 1 s in
    assert abs(len(out) / 2 - 16000) < 400


def test_resampler_same_rate_is_passthrough() -> None:
    assert PcmResampler(16000, 16000).process(b"abcd") == b"abcd"


def test_jitter_buffer_waits_for_head_start_then_plays() -> None:
    j = JitterBuffer(prebuffer_bytes=8)
    j.write(b"\x01\x01\x01\x01")
    assert j.read(4) == bytes(4)  # not enough yet: silence
    j.write(b"\x02\x02\x02\x02")
    assert j.read(4) == b"\x01\x01\x01\x01"
    assert j.read(4) == b"\x02\x02\x02\x02"


def test_jitter_buffer_underrun_pads_with_silence_and_rebuffers() -> None:
    j = JitterBuffer(prebuffer_bytes=4)
    j.write(b"\x05\x05\x05\x05")
    assert j.read(6) == b"\x05\x05\x05\x05" + bytes(2)
    j.write(b"\x06\x06")
    assert j.read(2) == bytes(2)  # rebuilding the head start


def test_jitter_buffer_clear_drops_audio() -> None:
    j = JitterBuffer(prebuffer_bytes=2)
    j.write(b"\x07" * 10)
    j.clear()
    assert len(j) == 0 and j.read(4) == bytes(4)
