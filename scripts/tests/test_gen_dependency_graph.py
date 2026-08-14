import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "gen-dependency-graph.py"
SPEC = importlib.util.spec_from_file_location("gen_dependency_graph", SCRIPT_PATH)
GRAPH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GRAPH)


class CMakeDependencyParserTests(unittest.TestCase):
    def parse(self, content):
        with tempfile.TemporaryDirectory() as temporary_directory:
            cmake_file = Path(temporary_directory) / "CMakeLists.txt"
            cmake_file.write_text(content, encoding="utf-8")
            return GRAPH.parse_cmake_deps(cmake_file)

    def test_reads_repository_package_helper_inside_condition(self):
        deps = self.parse(
            """
            if(COMMAND termin_require_package)
                termin_require_package(termin_physics termin_physics::termin_physics)
            endif()
            """
        )

        self.assertEqual(deps, {"termin-physics"})

    def test_reads_balanced_link_command_and_ignores_comment(self):
        deps = self.parse(
            """
            # termin_require_package(termin_bootstrap termin_bootstrap::termin_bootstrap)
            target_link_libraries(example PRIVATE
                $<$<BOOL:${WITH_PHYSICS}>:termin_physics::termin_physics>
                termin_modules::termin_modules
            )
            """
        )

        self.assertEqual(deps, {"termin-modules", "termin-physics"})

    def test_ignores_build_only_target_dependencies(self):
        deps = self.parse(
            """
            target_link_libraries(module_pixel_smoke PRIVATE
                termin_bootstrap::termin_bootstrap
            )
            target_link_libraries(module PUBLIC termin_scene::termin_scene)
            """
        )

        self.assertEqual(deps, {"termin-scene"})

    def test_current_modules_keep_their_native_dependencies(self):
        expected = {
            "termin-modules": ("engine", {"termin-base"}),
            "termin-physics": ("physics", {"termin-base", "termin-collision"}),
        }

        for module, (district, dependencies) in expected.items():
            with self.subTest(module=module):
                actual = GRAPH.parse_cmake_deps(
                    str(Path(GRAPH.ROOT) / district / module / "CMakeLists.txt")
                )
                self.assertTrue(dependencies <= actual)


class InteractiveDocumentTests(unittest.TestCase):
    def test_embeds_direct_graph_without_external_data_file(self):
        html = GRAPH.render_interactive_html(
            {"consumer", "dependency"},
            {("consumer", "dependency")},
            {"consumer": "Test"},
        )

        self.assertNotIn("__DEPENDENCY_GRAPH_DATA__", html)
        self.assertIn('"source":"consumer","target":"dependency"', html)
        self.assertIn('<script id="graph-data" type="application/json">', html)


if __name__ == "__main__":
    unittest.main()
