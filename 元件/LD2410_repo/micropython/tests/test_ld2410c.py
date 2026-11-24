"""Self-test for the ld2410c driver.

Runs without radar hardware on CPython:

    python micropython/tests/test_ld2410c.py

and also on MicroPython (copy the hardware/ folder plus this file):

    import test_ld2410c
    test_ld2410c.run_all()

The fake UART replays real frames captured with the official PC tool and
answers commands exactly like the module does (including the case where the
first 0x00FF is ignored while the radar is streaming).

MicroPython has no os.path, so paths are split by hand.
"""

import os
import sys


def _dirname(path):
    """Directory part of a path ("/" or "\\" separated, no os.path)."""
    path = (path or "").replace("\\", "/")
    if "/" in path:
        return path.rsplit("/", 1)[0]
    return ""


try:
    from hardware import ld2410c
except ImportError:
    _base = _dirname(globals().get("__file__", ""))
    _root = _dirname(_base)
    if _root:
        sys.path.insert(0, _root)
    from hardware import ld2410c


DATA_HEAD = b"\xf4\xf3\xf2\xf1"
DATA_TAIL = b"\xf8\xf7\xf6\xf5"

# --- real frames captured 2026-11-21 with HLK-LD2410 Tool at 115200 ----------
# Engineering mode, payload length 0x23 (35 bytes), tail 55 00.
REAL_FRAME_A = bytes.fromhex(
    "f4f3f2f1 2300 01aa 03 1e00 64 1e00 64 0000 0808"
    "6464 2b04 0908 0609 08 0000 6464 6464 6046 40 24 01 5500 f8f7f6f5")
REAL_FRAME_B = bytes.fromhex(
    "f4f3f2f1 2300 01aa 02 4100 00 4100 64 3500 0808"
    "0b07 0b07 0606 0204 01 0000 6441 303c 2713 0b 17 01 5500 f8f7f6f5")
# Basic (non engineering) frame from the protocol document, section 2.3.2.
DOC_BASIC_FRAME = bytes.fromhex(
    "f4f3f2f1 0d00 02aa 02 5100 00 0000 00 3b00 5500 f8f7f6f5")


class FakePin:
    def __init__(self, value=0):
        self._value = value

    def value(self):
        return self._value


class FakeUART:
    """Minimal machine.UART stand-in."""

    def __init__(self, responder=None):
        self.rx = b""
        self.tx = []
        self.responder = responder
        self.write_count = 0
        self.init_calls = []
        self.baudrate = 115200

    def any(self):
        return len(self.rx)

    def read(self, count=None):
        if not self.rx:
            return b""
        if count is None:
            data, self.rx = self.rx, b""
        else:
            data, self.rx = self.rx[:count], self.rx[count:]
        return data

    def write(self, data):
        self.write_count += 1
        self.tx.append(bytes(data))
        if self.responder is not None:
            self.rx += self.responder(bytes(data))
        return len(data)

    def init(self, baudrate=None, bits=8, parity=None, stop=1):
        self.init_calls.append(baudrate)
        if baudrate:
            self.baudrate = baudrate

    def deinit(self):
        pass


def _frame(kind, command, status, value=b""):
    """Build an ACK frame (kind='ack') or a data frame (kind='data')."""
    if kind == "ack":
        body = bytes((command & 0xFF, ((command >> 8) + 1) & 0xFF)) + \
            bytes((status & 0xFF, (status >> 8) & 0xFF)) + value
        return b"\xfd\xfc\xfb\xfa" + bytes((len(body) & 0xFF,
                                           len(body) >> 8)) + body + \
            b"\x04\x03\x02\x01"
    body = value
    return DATA_HEAD + bytes((len(body) & 0xFF, len(body) >> 8)) + body + \
        DATA_TAIL


class RadarSim:
    """Answers commands like an LD2410C and optionally streams data frames."""

    def __init__(self):
        self.max_moving_gate = 8
        self.max_stationary_gate = 8
        self.no_one_seconds = 5
        self.motion_sens = [50, 50, 40, 30, 20, 15, 15, 15, 15]
        self.static_sens = [10, 10, 40, 40, 30, 30, 20, 20, 20]
        self.resolution = 0
        self.stream = False
        self.ignore_enter_config = 0
        self.ignore_sensitivity = 0
        self.fail_status = 0
        self.commands = []

    def __call__(self, data):
        if data[:4] != b"\xfd\xfc\xfb\xfa":
            return b""
        length = data[4] | (data[5] << 8)
        payload = data[6:6 + length]
        command = payload[0] | (payload[1] << 8)
        value = payload[2:]
        self.commands.append(command)

        prefix = REAL_FRAME_A if self.stream else b""

        if command == 0x00FF and self.ignore_enter_config > 0:
            self.ignore_enter_config -= 1
            return prefix  # command swallowed, only the data stream arrives
        if command == 0x00FE and self.fail_status:
            return prefix + _frame("ack", command, self.fail_status)
        if command == 0x00FF:
            return prefix + _frame("ack", command, 0,
                                   b"\x01\x00\x40\x00")
        if command == 0x00FE or command in (0x0062, 0x0063, 0x00A3,
                                            0x00A2, 0x00A1, 0x00AA):
            if command == 0x00AA and len(value) >= 2:
                self.resolution = value[0] | (value[1] << 8)
            return prefix + _frame("ack", command, 0)
        if command == 0x00A2:
            return prefix + _frame("ack", command, 0)
        if command == 0x0061:
            body = bytes((0xAA, 8, self.max_moving_gate,
                          self.max_stationary_gate)) + \
                bytes(self.motion_sens) + bytes(self.static_sens) + \
                bytes((self.no_one_seconds & 0xFF,
                       self.no_one_seconds >> 8))
            return prefix + _frame("ack", command, 0, body)
        if command == 0x0060:
            words = {}
            for offset in (0, 6, 12):
                word = value[offset] | (value[offset + 1] << 8)
                number = (value[offset + 2] | (value[offset + 3] << 8) |
                          (value[offset + 4] << 16) | (value[offset + 5] << 24))
                words[word] = number
            self.max_moving_gate = words.get(0, self.max_moving_gate)
            self.max_stationary_gate = words.get(1, self.max_stationary_gate)
            self.no_one_seconds = words.get(2, self.no_one_seconds)
            return prefix + _frame("ack", command, 0)
        if command == 0x0064:
            if self.ignore_sensitivity > 0:
                self.ignore_sensitivity -= 1
                return prefix + _frame("ack", command, self.fail_status)
            gate = (value[2] | (value[3] << 8) | (value[4] << 16) |
                    (value[5] << 24))
            motion = (value[8] | (value[9] << 8) | (value[10] << 16) |
                      (value[11] << 24))
            static = (value[14] | (value[15] << 8) | (value[16] << 16) |
                      (value[17] << 24))
            if gate == 0xFFFF:
                self.motion_sens = [motion] * 9
                self.static_sens = [static] * 9
            else:
                self.motion_sens[gate] = motion
                self.static_sens[gate] = static
            return prefix + _frame("ack", command, 0)
        if command == 0x00A0:
            body = b"\x01\x00" + bytes((44, 2)) + \
                b"\x10\x31\x07\x24"  # V2.44.24073110
            return prefix + _frame("ack", command, 0, body)
        if command == 0x00AB:
            return prefix + _frame("ack", command, 0,
                                   bytes((self.resolution, 0)))
        return prefix + _frame("ack", command, self.fail_status)


def make_radar(sim=None, out=None):
    sim = sim or RadarSim()
    uart = FakeUART(sim)
    radar = ld2410c.LD2410C(uart=uart, out=out)
    return radar, uart, sim


def feed(radar, uart, data):
    uart.rx += data


# ------------------------------------------------------------------ tests

def test_frame_encoding():
    radar, uart, sim = make_radar()
    expected = {
        0x00FF: "fdfcfbfa 0400 ff00 0100 04030201",
        0x00FE: "fdfcfbfa 0200 fe00 04030201",
        0x0061: "fdfcfbfa 0200 6100 04030201",
        0x0062: "fdfcfbfa 0200 6200 04030201",
        0x0063: "fdfcfbfa 0200 6300 04030201",
        0x00A2: "fdfcfbfa 0200 a200 04030201",
        0x00A3: "fdfcfbfa 0200 a300 04030201",
    }
    for command, hexed in expected.items():
        uart.tx = []
        radar.send(command, b"\x01\x00" if command == 0x00FF else b"")
        got = uart.tx[0].hex()
        eq(got, hexed.replace(" ", ""), "frame for 0x%04X" % command)

    # Protocol examples with parameters (section 2.2.3 and 2.2.7).
    uart.tx = []
    radar.send(0x0060,
               ld2410c._le16(0) + ld2410c._le32(8) +
               ld2410c._le16(1) + ld2410c._le32(8) +
               ld2410c._le16(2) + ld2410c._le32(5))
    eq(uart.tx[0].hex(), "fdfcfbfa14006000" "000008000000" "010008000000"
       "020005000000" "04030201", "set max gates frame")

    uart.tx = []
    radar.send(0x0064,
               ld2410c._le16(0) + ld2410c._le32(3) +
               ld2410c._le16(1) + ld2410c._le32(40) +
               ld2410c._le16(2) + ld2410c._le32(40))
    eq(uart.tx[0].hex(), "fdfcfbfa14006400" "000003000000" "010028000000"
       "020028000000" "04030201", "set sensitivity frame")

    uart.tx = []
    radar.send(0x00A1, ld2410c._le16(7))
    eq(uart.tx[0].hex(), "fdfcfbfa0400a100" "0700" "04030201", "set baud frame")


def test_ack_status_error():
    sim = RadarSim()
    sim.fail_status = 1
    radar, uart, _ = make_radar(sim)
    try:
        radar.send(0x00FE)
    except ld2410c.LD2410CCommandError:
        return
    raise AssertionError("failure status must raise LD2410CCommandError")


def test_enter_config_retry():
    sim = RadarSim()
    sim.ignore_enter_config = 2  # module swallows the first two 0x00FF
    sim.stream = True            # while streaming data frames
    radar, uart, _ = make_radar(sim)
    eq(radar.enter_config(retries=5), True, "enter config after retries")
    eq(sim.commands.count(0x00FF), 3, "0x00FF attempts")


def test_timeout_raises():
    sim = RadarSim()
    sim.ignore_enter_config = 99
    radar, uart, _ = make_radar(sim)
    radar.timeout_ms = 40
    try:
        radar.enter_config(retries=2, delay_ms=1)
    except ld2410c.LD2410CTimeout:
        return
    raise AssertionError("missing ACK must raise LD2410CTimeout")


def test_read_params():
    radar, uart, sim = make_radar()
    params = radar.read_params()
    eq(params["max_gate"], 8, "max_gate")
    eq(params["max_moving_gate"], 8, "max_moving_gate")
    eq(params["max_stationary_gate"], 8, "max_stationary_gate")
    eq(params["no_one_seconds"], 5, "nobody delay")
    eq(params["motion_sens"], [50, 50, 40, 30, 20, 15, 15, 15, 15],
       "motion sensitivity")
    eq(len(params["static_sens"]), 9, "static sensitivity length")
    eq(sim.commands[0], 0x00FF, "session starts with 0x00FF")
    eq(sim.commands[-1], 0x00FE, "session ends with 0x00FE")


def test_write_params_and_verify():
    radar, uart, sim = make_radar()
    params = radar.read_params()
    params["max_moving_gate"] = 4
    params["max_stationary_gate"] = 4
    params["no_one_seconds"] = 30
    params["motion_sens"] = [60, 55, 50, 45, 40, 35, 30, 25, 20]
    params["static_sens"] = [55, 50, 45, 40, 35, 30, 25, 20, 15]
    result = radar.write_params(params)
    eq(result["verified"], True, "read-back verification")
    eq(result["diff"], [], "no difference after write")
    eq(sim.max_moving_gate, 4, "module max moving gate")
    eq(sim.no_one_seconds, 30, "module nobody delay")
    eq(sim.motion_sens[4], 40, "gate 4 motion sensitivity")
    eq(sim.static_sens[8], 15, "gate 8 static sensitivity")


def test_write_params_detects_mismatch():
    radar, uart, sim = make_radar()
    params = radar.read_params()
    params["motion_sens"][0] = 77
    sim.ignore_sensitivity = 1  # the module keeps the old value on gate 0
    sim.motion_sens[0] = 50
    result = radar.write_params(params)
    eq(result["verified"], False, "mismatch must be reported")
    eq(len(result["diff"]) >= 1, True, "difference list")


def test_firmware_version():
    radar, uart, sim = make_radar()
    fw = radar.firmware_version()
    eq(fw["major"], 2, "major")
    eq(fw["minor"], 44, "minor")
    eq(fw["string"], "V2.44.24073110", "firmware string")


def test_resolution():
    radar, uart, sim = make_radar()
    eq(radar.read_resolution()["meters"], 0.75, "factory resolution")
    radar.set_resolution(0.2, restart=False)
    eq(radar.read_resolution()["meters"], 0.2, "resolution after set")
    try:
        radar.set_resolution(0.5)
    except ValueError:
        pass
    else:
        raise AssertionError("0.5 m resolution must be rejected")


def test_baudrate_switch():
    radar, uart, sim = make_radar()
    radar.set_baudrate(256000)
    eq(radar.baudrate, 256000, "driver baud rate")
    eq(uart.init_calls[-1], 256000, "UART reopened at the new rate")
    try:
        radar.set_baudrate(12345)
    except ValueError:
        pass
    else:
        raise AssertionError("unsupported baud rate must be rejected")


def test_engineering_frame():
    radar, uart, sim = make_radar()
    feed(radar, uart, REAL_FRAME_A)
    frame = radar.poll()
    eq(frame["state"], 3, "state")
    eq(frame["state_name"], "moving+stationary", "state name")
    eq(frame["moving_cm"], 30, "moving distance")
    eq(frame["stationary_cm"], 30, "stationary distance")
    eq(frame["moving_energy"], 100, "moving energy")
    eq(frame["stationary_energy"], 100, "stationary energy")
    eq(frame["detection_cm"], 0, "detection distance")
    eq(frame["distance_cm"], 30, "usable distance falls back to target")
    eq(len(frame["moving_gates"]), 9, "nine moving gates")
    eq(len(frame["stationary_gates"]), 9, "nine stationary gates")
    eq(frame["max_moving_gate"], 8, "max moving gate in frame")
    eq(frame["light"], 36, "light level from the V2.44 tail")
    eq(frame["engineering"], True, "engineering flag")
    eq(radar.frames, 1, "frame counter")


def test_basic_frame():
    radar, uart, sim = make_radar()
    feed(radar, uart, DOC_BASIC_FRAME)
    frame = radar.poll()
    eq(frame["type"], 2, "basic frame type")
    eq(frame["moving_cm"], 0x51, "moving distance 81 cm")
    eq(frame["detection_cm"], 0x3B, "detection distance 59 cm")
    eq(frame["distance_cm"], 0x3B, "detection distance is used when set")
    eq(frame["engineering"], False, "not engineering")
    eq(len(frame["moving_gates"]), 0, "no gate energies in basic mode")


def test_partial_frame():
    radar, uart, sim = make_radar()
    for offset in range(0, len(REAL_FRAME_A), 3):
        feed(radar, uart, REAL_FRAME_A[offset:offset + 3])
        got = radar.poll()
        if got is not None:
            break
    eq(got is not None, True, "frame assembled from 3-byte chunks")
    eq(radar.frames, 1, "exactly one frame")


def test_noise_resync():
    radar, uart, sim = make_radar()
    feed(radar, uart, b"\x00\x11\x22\xf4\xf3" + REAL_FRAME_B)
    frame = radar.poll()
    eq(frame is not None, True, "frame found after noise")
    eq(frame["state"], 2, "state parsed after resync")
    eq(frame["moving_cm"], 65, "distance after resync")


def test_bad_length_resync():
    radar, uart, sim = make_radar()
    # A header with an impossible length must be skipped, not trusted.
    feed(radar, uart, DATA_HEAD + b"\xff\x00" + REAL_FRAME_A)
    frame = radar.poll()
    eq(frame is not None, True, "good frame after bad length")
    eq(radar.errors, 0, "bad header dropped silently")


def test_out_pin():
    radar, uart, sim = make_radar(out=FakePin(1))
    eq(radar.presence(), True, "OUT high means presence")
    radar.out_active_high = False
    eq(radar.presence(), False, "active low OUT inverted")


def test_age_and_connection():
    radar, uart, sim = make_radar()
    eq(radar.is_connected(), False, "not connected before first frame")
    feed(radar, uart, REAL_FRAME_A)
    radar.poll()
    eq(radar.is_connected(), True, "connected after a frame")
    eq(radar.age_ms() >= 0, True, "age is measurable")
    ld2410c.sleep_ms(60)
    eq(radar.is_connected(within_ms=50), False, "stale after 60 ms")


def test_check_and_compare_helpers():
    params = {"max_gate": 8, "max_moving_gate": 4,
              "max_stationary_gate": 8, "no_one_seconds": 5,
              "motion_sens": [50] * 9, "static_sens": [50] * 9}
    eq(ld2410c.check_params(params), [], "valid parameters")
    bad = dict(params)
    bad["max_moving_gate"] = 12
    bad["motion_sens"] = [101] + [50] * 8
    eq(len(ld2410c.check_params(bad)), 2, "two warnings")
    diff = ld2410c.compare_params(params, dict(params))
    eq(diff, [], "identical dictionaries")
    other = dict(params)
    other["no_one_seconds"] = 9
    eq(len(ld2410c.compare_params(params, other)), 1, "one difference")


def test_constructor_opens_uart():
    class Factory:
        def __init__(self):
            self.calls = []

        def __call__(self, *args, **kwargs):
            self.calls.append((args, kwargs))
            return FakeUART()

    factory = Factory()
    saved = ld2410c.UART
    ld2410c.UART = factory
    try:
        radar = ld2410c.LD2410C(uart_id=2, tx=15, rx=16, baudrate=115200,
                                out_pin=None)
    finally:
        ld2410c.UART = saved
    args, kwargs = factory.calls[0]
    eq(args[0], 2, 'uart id passed to machine.UART')
    eq(kwargs['tx'], 15, 'tx pin')
    eq(kwargs['rx'], 16, 'rx pin')
    eq(kwargs['baudrate'], 115200, 'baud rate')
    eq(kwargs['bits'], 8, 'data bits')
    eq(radar.uart is not None, True, 'uart attached')


def test_partial_header_ignored():
    radar, uart, sim = make_radar()
    uart.rx += b'\xf4\xf3'
    eq(radar.poll(), None, 'partial header is not a frame')
    eq(radar.frames, 0, 'no frame counted')


def test_bad_tail_resync():
    radar, uart, sim = make_radar()
    broken = REAL_FRAME_A[:-4] + b'\x00\x00\x00\x00'
    uart.rx += broken + REAL_FRAME_B
    frame = radar.poll()
    eq(frame is not None, True, 'good frame after a corrupted tail')
    eq(radar.frames, 1, 'only the good frame counted')
    eq(frame['state'], 2, 'state from the good frame')


def test_wrong_ack_is_ignored():
    sim = RadarSim()

    def responder(data):
        # Put an ACK for another command in front of the real answer.
        return _frame('ack', 0x00FE, 0) + sim(data)

    uart = FakeUART(responder)
    radar = ld2410c.LD2410C(uart=uart)
    payload = radar.send(0x00FF, b'\x01\x00')
    eq(payload, b'\x01\x00\x40\x00', 'correct ACK payload')


def test_uart_without_any():
    class NoAnyUART(FakeUART):
        any = None

    uart = NoAnyUART()
    radar = ld2410c.LD2410C(uart=uart)
    uart.rx += REAL_FRAME_A
    frame = radar.poll()
    eq(frame is not None, True, 'poll works without UART.any()')
    eq(frame['state'], 3, 'frame decoded')

def test_diagnose():
    sim = RadarSim()
    sim.stream = True
    uart = FakeUART(sim)
    radar = ld2410c.LD2410C(uart=uart, baudrate=115200)
    uart.rx += REAL_FRAME_A
    result = radar.diagnose(verbose=False)
    eq(result["ok"], True, "diagnose on a healthy link")
    eq(result["data_ok"], True, "data stream detected")
    eq(result["cmd_ok"], True, "command channel detected")
    eq(result["found_baud"], 115200, "reported baud rate")
    eq(radar.timeout_ms, 800, "probe restores the command timeout")


def test_diagnose_command_only():
    sim = RadarSim()          # radar does not stream data frames
    uart = FakeUART(sim)
    radar = ld2410c.LD2410C(uart=uart, baudrate=115200)
    result = radar.diagnose(verbose=False)
    eq(result["data_ok"], False, "no data frame seen")
    eq(result["cmd_ok"], True, "command channel answers")
    eq(result["ok"], True, "still usable for configuration")
    eq(result["scan"], [], "no need to scan other baud rates")


def test_diagnose_data_only():
    sim = RadarSim()
    sim.ignore_enter_config = 999   # module never answers 0x00FF
    uart = FakeUART(sim)
    radar = ld2410c.LD2410C(uart=uart, baudrate=115200)
    uart.rx += REAL_FRAME_A * 2
    result = radar.diagnose(verbose=False)
    eq(result["data_ok"], True, "data frames arrive")
    eq(result["cmd_ok"], False, "no ACK")
    eq(result["ok"], False, "link is not usable for configuration")
    eq(result["found_baud"], 115200, "baud rate still reported")
    eq(result["scan"], [], "does not scan away from a working data rate")


def test_hexdump():
    eq(ld2410c.hexdump(b""), "", "empty hexdump")
    eq(ld2410c.hexdump(b"\xf4\xf3\x00"), "F4 F3 00", "hexdump text")
    text = ld2410c.hexdump(bytes(range(40)), limit=4)
    eq(text.endswith("..."), True, "hexdump truncation marker")


def test_real_capture_corpus():
    """Replay every frame of the captured .dat files when they are installed.

    On the board only test_ld2410c.py may be copied, so a missing fixtures/
    folder simply skips this check (parsing itself is covered by the single
    frame tests above).
    """
    base = _dirname(globals().get("__file__", ""))
    folders = []
    if base:
        folders.append(base + "/fixtures")
    folders.append("fixtures")
    folder = None
    names = []
    for candidate in folders:
        try:
            names = sorted(os.listdir(candidate))
            folder = candidate
            break
        except OSError:
            continue
    if folder is None:
        print("      (fixtures/ not installed - corpus replay skipped)")
        return
    for name in names:
        if not name.endswith(".dat"):
            continue
        with open(folder + "/" + name, "rb") as handle:
            blob = handle.read()
        radar, uart, sim = make_radar()
        uart.rx += blob
        radar.poll()
        expected = blob.count(DATA_HEAD)
        eq(radar.frames, expected, name + ": frame count")
        eq(radar.errors, 0, name + ": no parse errors")
        frame = radar.frame
        eq(len(frame["moving_gates"]), 9, name + ": gate count")
        for gate, energy in enumerate(frame["moving_gates"]):
            eq(0 <= energy <= 100, True, name + ": gate energy range")
        eq(frame["state"] in (0, 1, 2, 3), True, name + ": state value")
        eq(frame["light"] is not None, True, name + ": light level present")

# ------------------------------------------------------------------ runner

def eq(actual, expected, label):
    if actual != expected:
        raise AssertionError("%s: expected %r, got %r"
                             % (label, expected, actual))


TESTS = [
    test_frame_encoding,
    test_ack_status_error,
    test_enter_config_retry,
    test_timeout_raises,
    test_read_params,
    test_write_params_and_verify,
    test_write_params_detects_mismatch,
    test_firmware_version,
    test_resolution,
    test_baudrate_switch,
    test_engineering_frame,
    test_basic_frame,
    test_partial_frame,
    test_noise_resync,
    test_bad_length_resync,
    test_out_pin,
    test_age_and_connection,
    test_check_and_compare_helpers,
    test_constructor_opens_uart,
    test_partial_header_ignored,
    test_bad_tail_resync,
    test_wrong_ack_is_ignored,
    test_uart_without_any,
    test_diagnose,
    test_diagnose_command_only,
    test_diagnose_data_only,
    test_hexdump,
    test_real_capture_corpus,
]


def run_all(verbose=True):
    passed = 0
    failed = []
    for test in TESTS:
        try:
            test()
            passed += 1
            if verbose:
                print("PASS  %s" % test.__name__)
        except Exception as error:  # noqa: BLE001 - test report
            failed.append((test.__name__, error))
            if verbose:
                print("FAIL  %s: %s" % (test.__name__, error))
    print("")
    print("%d passed, %d failed" % (passed, len(failed)))
    return failed


if __name__ == "__main__":
    failed = run_all()
    if failed:
        raise SystemExit(1)
