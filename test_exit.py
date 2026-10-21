"""Exit trajectory stays outside the bubble before landing and shrinking."""
import unittest
from pet import exit_pose


class ExitPoseTests(unittest.TestCase):
    def test_jump_lands_before_shrink(self):
        self.assertEqual(exit_pose(0,72,0),(0,0,1))
        self.assertEqual(exit_pose(.325,72,0),(0,-72,1))
        x,y,scale=exit_pose(.65,72,0)
        self.assertAlmostEqual(y,0)
        self.assertEqual(scale,1)
        self.assertEqual(exit_pose(1,72,0),(0,0,0))
        scales=[exit_pose(i/100,72,0)[2] for i in range(70,101)]
        self.assertEqual(scales,sorted(scales,reverse=True))

    def test_top_edge_uses_inward_jump_with_bounded_height(self):
        self.assertEqual(exit_pose(.325,24,64),(64,-24,1))
        self.assertEqual(exit_pose(.325,24,-64),(-64,-24,1))
        for progress in (-1,0,.2,.8,1,2):
            _,y,scale=exit_pose(progress,24,64)
            self.assertTrue(-24<=y<=0)
            self.assertTrue(0<=scale<=1)


if __name__=="__main__":
    unittest.main()
