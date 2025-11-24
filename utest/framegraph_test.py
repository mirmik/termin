# utest/framegraph_test.py

import unittest

from termin.visualization.framegraph import (
    FramePass,
    FrameGraph,
    FrameGraphCycleError,
    FrameGraphMultiWriterError,
)


class DummyPass(FramePass):
    """Тестовый пасс без реального исполнения."""

    def __init__(self, name, reads=None, writes=None):
        super().__init__(
            name=name,
            reads=set(reads or []),
            writes=set(writes or []),
        )

    def execute(self, *args, **kwargs):
        # В тестах ничего не делаем
        return


class FrameGraphTests(unittest.TestCase):
    def test_simple_linear_chain(self):
        # A -> B -> C
        a = DummyPass("A", writes={"g1"})
        b = DummyPass("B", reads={"g1"}, writes={"g2"})
        c = DummyPass("C", reads={"g2"})

        g = FrameGraph([a, b, c])
        schedule = g.build_schedule()
        names = [p.name for p in schedule]

        self.assertEqual(set(names), {"A", "B", "C"})
        self.assertLess(names.index("A"), names.index("B"))
        self.assertLess(names.index("B"), names.index("C"))

    def test_branching(self):
        #   A
        #  / \
        # B   C
        #  \ /
        #   D
        a = DummyPass("A", writes={"r1"})
        b = DummyPass("B", reads={"r1"}, writes={"r2"})
        c = DummyPass("C", reads={"r1"}, writes={"r3"})
        d = DummyPass("D", reads={"r2", "r3"})

        g = FrameGraph([a, b, c, d])
        schedule = g.build_schedule()
        names = [p.name for p in schedule]

        # A должен быть до B и C
        self.assertLess(names.index("A"), names.index("B"))
        self.assertLess(names.index("A"), names.index("C"))
        # B и C должны быть до D
        self.assertLess(names.index("B"), names.index("D"))
        self.assertLess(names.index("C"), names.index("D"))

    def test_external_resource(self):
        # Ресурс, который никто не пишет, но кто-то читает — считаем внешним входом
        a = DummyPass("A", reads={"external_x"}, writes={"r1"})
        b = DummyPass("B", reads={"r1"})

        g = FrameGraph([a, b])
        schedule = g.build_schedule()
        names = [p.name for p in schedule]

        self.assertLess(names.index("A"), names.index("B"))
        # Никаких исключений не бросается

    def test_multi_writer_error(self):
        # Один и тот же ресурс пишет два пасса — это запрещаем.
        a = DummyPass("A", writes={"r1"})
        b = DummyPass("B", writes={"r1"})

        g = FrameGraph([a, b])
        with self.assertRaises(FrameGraphMultiWriterError):
            g.build_schedule()

    def test_cycle_detection(self):
        # A пишет r1, читает r2
        # B пишет r2, читает r1
        a = DummyPass("A", reads={"r2"}, writes={"r1"})
        b = DummyPass("B", reads={"r1"}, writes={"r2"})

        g = FrameGraph([a, b])
        with self.assertRaises(FrameGraphCycleError):
            g.build_schedule()

    def test_pass_without_resources(self):
        # Пассы без reads/writes ни от чего не зависят
        a = DummyPass("A")
        b = DummyPass("B")
        c = DummyPass("C")

        g = FrameGraph([a, b, c])
        schedule = g.build_schedule()
        # Любой порядок валиден, главное — все на месте
        names = [p.name for p in schedule]
        self.assertEqual(set(names), {"A", "B", "C"})


if __name__ == "__main__":
    unittest.main()
