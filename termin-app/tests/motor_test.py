import unittest
from termin.ga201.motor import Motor2
import math


def early(a, b):
    if abs(a.x - b.x) > 0.0001:
        return False
    if abs(a.y - b.y) > 0.0001:
        return False
    if abs(a.z - b.z) > 0.0001:
        return False
    return True


class TransformationProbe(unittest.TestCase):
    def test_translate(self):
        ident = Motor2(0,0,0,1)
        translate = Motor2(1,0,0,1)
        self.assertEqual(translate.factorize_translation(), translate)
        self.assertEqual(translate.factorize_rotation(), ident)

        rotation = Motor2.rotation(math.pi/2)
        self.assertEqual(rotation.factorize_rotation(), rotation)
        self.assertEqual(rotation.factorize_translation(), ident)

        q = rotation * translate
        self.assertTrue(
            (q.factorize_translation() - Motor2(0,1,0,1)).is_zero_equal()
        )

        invq = q.inverse()
        q_invq = q * invq
        invq_q = invq * q

        self.assertTrue((invq_q - ident).is_zero_equal())
        self.assertTrue((q_invq - ident).is_zero_equal())

        self.assertTrue((translate.inverse()-Motor2(-1,0,0,1)).is_zero_equal())