"""Exercise the registered Python drawable callback through its native C ABI."""

import os
import subprocess
import sys
import textwrap


def test_native_python_material_callback_contract():
    result = subprocess.run(
        [
            sys.executable,
            "--termin-overlay",
            os.environ["TERMIN_PYTHON_OVERLAY"],
            "-c",
            textwrap.dedent(
                """
                import ctypes as ct
                import os
                import sys
                from pathlib import Path

                from termin.bootstrap import bootstrap_player, shutdown_player
                bootstrap_player()
                from termin.materials import TcMaterial
                from termin.render import DrawableComponent

                # Mirrors the public tc_drawable_protocol.h/tc_render_item.h ABI.
                class Handle(ct.Structure):
                    _fields_ = [("index", ct.c_uint32), ("generation", ct.c_uint32)]

                class Context(ct.Structure):
                    _fields_ = [
                        ("phase", ct.c_uint64), ("flags", ct.c_uint32),
                        ("layer_mask", ct.c_uint64), ("render_category_mask", ct.c_uint64),
                        ("debug_pass_name", ct.c_char_p), ("pass_contract", ct.c_void_p),
                        ("scene", ct.c_void_p), ("camera", ct.c_void_p),
                        ("user_context", ct.c_void_p),
                    ]

                # RenderCamera holds two packed Mat44 doubles, Vec3, and clip planes.
                class Camera(ct.Structure):
                    _fields_ = [
                        ("view", ct.c_double * 16), ("projection", ct.c_double * 16),
                        ("position", ct.c_double * 3),
                        ("near_clip", ct.c_double), ("far_clip", ct.c_double),
                    ]

                Emit = ct.CFUNCTYPE(ct.c_bool, Handle, ct.c_void_p)
                class Sink(ct.Structure):
                    _fields_ = [("emit", Emit), ("user_data", ct.c_void_p)]

                Collect = ct.CFUNCTYPE(
                    ct.c_bool, ct.c_void_p, ct.POINTER(Context), ct.POINTER(Sink)
                )
                class Vtable(ct.Structure):
                    _fields_ = [
                        ("phase_mask", ct.c_void_p), ("collect_render_items", ct.c_void_p),
                        ("collect_materials", Collect),
                    ]

                class Capability(ct.Structure):
                    _fields_ = [("vtable", ct.POINTER(Vtable)), ("userdata", ct.c_void_p)]

                sdk = Path(os.environ["TERMIN_SDK"])
                library = sdk / ("bin/termin_render.dll" if sys.platform == "win32"
                                 else "lib/libtermin_render.dylib" if sys.platform == "darwin"
                                 else "lib/libtermin_render.so")
                native = ct.CDLL(str(library))
                native.tc_drawable_capability_get.argtypes = [ct.c_void_p]
                native.tc_drawable_capability_get.restype = ct.POINTER(Capability)

                material = TcMaterial.create("python-bridge-material", "bridge-material-2895")
                emitted = []
                accept = True
                @Emit
                def emit(handle, user_data):
                    assert user_data == 2895
                    emitted.append((handle.index, handle.generation))
                    return accept
                sink = Sink(emit, 2895)
                camera = Camera(near_clip=0.25, far_clip=150.0)
                camera.position[:] = (1.0, 2.0, 3.0)
                scene = Handle(0xffffffff, 0)
                context = Context(
                    phase=4, flags=1, layer_mask=0x1234, render_category_mask=0x5678,
                    debug_pass_name=b"bridge-contract",
                    camera=ct.addressof(camera), scene=ct.addressof(scene),
                )

                class Probe(DrawableComponent):
                    def __init__(self):
                        super().__init__()
                        self.materials = [material]
                        self.contexts = []
                        self.heavy_calls = 0
                    def collect_materials(self, ctx):
                        self.contexts.append(ctx)
                        return self.materials
                    def collect_render_items(self, ctx):
                        self.heavy_calls += 1
                        raise AssertionError("heavy collection used for material enumeration")

                def collect(component):
                    pointer = component._tc.c_ptr_int()
                    capability = native.tc_drawable_capability_get(pointer)
                    assert capability
                    return capability.contents.vtable.contents.collect_materials(
                        pointer, ct.byref(context), ct.byref(sink)
                    )

                probe = Probe()
                assert collect(probe)
                assert len(emitted) == 1
                assert emitted[0][0] != 0xffffffff
                received = probe.contexts[-1]
                assert (received.phase, received.flags) == (4, 1)
                assert (received.layer_mask, received.render_category_mask) == (0x1234, 0x5678)
                assert received.debug_pass_name == "bridge-contract"
                assert received.camera.position.x == 1.0
                assert received.camera.near_clip == 0.25
                assert received.camera.far_clip == 150.0
                assert received.scene is not None and not received.scene.is_alive()
                camera.near_clip = 0.75
                assert received.camera.near_clip == 0.25  # Owns a copy of native context.

                emitted.clear()
                probe.materials = []
                context.camera = None
                context.scene = None
                assert collect(probe) and emitted == []
                assert probe.contexts[-1].camera is None and probe.contexts[-1].scene is None

                probe.materials = [material, material]
                accept = False
                assert not collect(probe)
                assert len(emitted) == 1  # Sink cancellation stops iteration.
                accept = True
                probe.materials = None
                assert not collect(probe)
                probe.materials = [TcMaterial()]
                assert not collect(probe)
                probe.materials = [object()]
                assert not collect(probe)
                assert probe.heavy_calls == 0

                class Missing(DrawableComponent):
                    def collect_render_items(self, ctx):
                        raise AssertionError("fallback called")
                missing = Missing()
                assert not collect(missing)
                del missing, probe, material
                shutdown_player()
                print("bridge contract passed")
                """
            ),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.rstrip().endswith("bridge contract passed")
    assert "must return an iterable" in result.stderr
    assert "returned an invalid material" in result.stderr
    assert "collect_materials() must return TcMaterial objects" in result.stderr
    assert "fallback called" not in result.stderr
