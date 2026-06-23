import subprocess
import sys
import textwrap


def _run_python(code: str) -> None:
    subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        check=True,
    )


def test_importing_bootstrap_has_no_kind_registration_side_effects():
    _run_python(
        """
        from termin.inspect import KindRegistry

        before = set(KindRegistry.instance().kinds())
        import termin.bootstrap  # noqa: F401
        after = set(KindRegistry.instance().kinds())

        assert after == before
        """
    )


def test_explicit_runtime_bootstrap_registers_core_resource_kinds():
    _run_python(
        """
        import termin.bootstrap
        from termin.inspect import KindRegistry

        termin.bootstrap.register_runtime_kinds(
            mesh=True,
            material=True,
            skeleton=False,
            animation=False,
            voxel_grid=False,
            entity=False,
        )

        kinds = set(KindRegistry.instance().kinds())
        assert "tc_mesh" in kinds
        assert "tc_material" in kinds
        """
    )


def test_explicit_player_bootstrap_registers_python_type_mappings():
    _run_python(
        """
        import termin.bootstrap
        import tmesh
        from termin.inspect import KindRegistry
        from termin.materials import TcMaterial

        termin.bootstrap.init_python_kind_handlers(
            mesh=True,
            material=True,
            skeleton=False,
            animation=False,
            voxel_grid=False,
            entity=False,
        )

        registry = KindRegistry.instance()
        assert registry.kind_for_object(tmesh.TcMesh()) == "tc_mesh"
        assert registry.kind_for_object(TcMaterial()) == "tc_material"
        """
    )


def test_partial_python_kind_init_does_not_block_later_full_player_bootstrap():
    _run_python(
        """
        import termin.bootstrap
        from termin.inspect import KindRegistry

        termin.bootstrap.init_python_kind_handlers(
            mesh=True,
            material=True,
            skeleton=False,
            animation=False,
            voxel_grid=False,
            entity=False,
        )

        termin.bootstrap.bootstrap_player()

        from termin.skeleton import TcSkeleton

        registry = KindRegistry.instance()
        assert registry.kind_for_object(TcSkeleton()) == "tc_skeleton"
        """
    )
