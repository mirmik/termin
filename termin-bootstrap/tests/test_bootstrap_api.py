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


def test_importing_legacy_native_modules_has_no_kind_registration_side_effects():
    _run_python(
        """
        from termin.inspect import KindRegistry

        before = set(KindRegistry.instance().kinds())

        import termin._native  # noqa: F401
        import termin.animation._animation_native  # noqa: F401
        import termin.navmesh._navmesh_native  # noqa: F401
        import termin.skeleton._skeleton_native  # noqa: F401
        import termin.voxels._voxels_native  # noqa: F401

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
            navmesh=False,
            entity=False,
        )

        kinds = set(KindRegistry.instance().kinds())
        assert "tc_mesh" in kinds
        assert "tc_material" in kinds
        """
    )


def test_explicit_domain_native_kind_registration_functions_remain_available():
    _run_python(
        """
        from termin.inspect import KindRegistry
        import termin.animation._animation_native as animation_native
        import termin.navmesh._navmesh_native as navmesh_native
        import termin.skeleton._skeleton_native as skeleton_native
        import termin.voxels._voxels_native as voxels_native

        animation_native.register_animation_kind_handlers()
        navmesh_native.register_navmesh_kind_handlers()
        skeleton_native.register_tc_skeleton_kind()
        voxels_native.register_voxel_grid_kind_handlers()

        registry = KindRegistry.instance()
        kinds = set(registry.kinds())
        assert "tc_animation_clip" in kinds
        assert "navmesh_handle" in kinds
        assert "tc_skeleton" in kinds
        assert "voxel_grid_handle" in kinds
        assert registry.kind_for_object(animation_native.TcAnimationClip()) == "tc_animation_clip"
        assert registry.kind_for_object(navmesh_native.TcNavMesh()) == "navmesh_handle"
        assert registry.kind_for_object(skeleton_native.TcSkeleton()) == "tc_skeleton"
        assert registry.kind_for_object(voxels_native.TcVoxelGrid()) == "voxel_grid_handle"
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
            navmesh=False,
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
            navmesh=False,
            entity=False,
        )

        termin.bootstrap.bootstrap_player()

        from termin.skeleton import TcSkeleton

        registry = KindRegistry.instance()
        assert registry.kind_for_object(TcSkeleton()) == "tc_skeleton"
        """
    )
