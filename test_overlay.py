"""Pure interaction and geometry regressions; no desktop required."""
import unittest
from desktop import Spring, clamp_pet, tray_placement, circle_contains
from sessions import Session


class OverlayTests(unittest.TestCase):
    def test_spring_settles_with_bounded_overshoot_and_reverses(self):
        spring = Spring()
        spring.target = 1
        values = []
        for _ in range(120):
            spring.step(1/60)
            values.append(spring.value)
        self.assertEqual(spring.value, 1)
        self.assertGreater(max(values), 1)
        self.assertLess(max(values), 1.08)
        spring.target = 0
        for _ in range(120):
            spring.step(1/60)
        self.assertEqual(spring.value, 0)
        self.assertEqual(spring.velocity, 0)

    def test_reduced_motion_has_no_transitional_frames(self):
        spring = Spring()
        spring.target = 1
        self.assertFalse(spring.step(.001, reduced=True))
        self.assertEqual(spring.value, 1)
        spring.target = 0
        self.assertFalse(spring.step(.001, reduced=True))
        self.assertEqual(spring.value, 0)

    def test_large_frame_pause_does_not_explode(self):
        spring = Spring()
        spring.target = 1
        spring.step(999)
        self.assertTrue(0 < spring.value < 1.08)

    def test_left_preferred_and_right_only_when_left_has_no_space(self):
        area = (0, 0, 1920, 1040)
        left = tray_placement(1800, 500, area)
        self.assertEqual(left["side"], "left")
        self.assertEqual(left["x"] + left["width"], 1800)
        right = tray_placement(12, 12, area)
        self.assertEqual(right["side"], "right")
        self.assertEqual(right["x"], 76)
        self.assertGreaterEqual(right["y"], 12)
        self.assertGreaterEqual(right["connector"], 16)

    def test_negative_monitor_and_bottom_edge(self):
        area = (-1920, -200, 0, 840)
        x,y = clamp_pet(-70, 900, area)
        p = tray_placement(x,y,area, details=True)
        self.assertEqual((x,y),(-76,764))
        self.assertGreaterEqual(p["x"], area[0])
        self.assertLessEqual(p["y"]+p["height"],area[3]-12)
        self.assertLess(p["connector"],p["height"]-16)

    def test_small_monitor_relocates_pet_and_keeps_both_visible(self):
        area = (0,0,640,480)
        p = tray_placement(260,210,area,details=True)
        self.assertEqual(p["side"],"left")
        self.assertGreaterEqual(p["x"],12)
        self.assertLessEqual(p["pet_x"]+64,area[2]-12)
        self.assertLessEqual(p["y"]+p["height"],area[3]-12)

    def test_hit_test_excludes_circle_corners(self):
        self.assertFalse(circle_contains(100,100,101,101))
        self.assertTrue(circle_contains(100,100,132,132))

    def test_thinking_and_completion_are_real_transcript_events(self):
        session = Session("c","Codex")
        session.apply({"type":"response_item","payload":{"type":"reasoning"}},10)
        self.assertEqual(session.state,"thinking")
        session.apply({"type":"event_msg","payload":{"type":"turn_aborted"}},11)
        self.assertEqual(session.completed,0)
        session.apply({"type":"event_msg","payload":{"type":"task_started"}},11.5)
        session.apply({"type":"event_msg","payload":{"type":"task_complete"}},12)
        self.assertEqual(session.completed,12)
        session.apply({"type":"event_msg","payload":{"type":"task_complete"}},12)
        self.assertEqual(session.completed,12)
        session.apply({"type":"response_item","payload":{"type":"message","role":"assistant","phase":"final_answer"}},13)
        self.assertEqual(session.completed,12)
        claude = Session("a","Claude")
        claude.apply({"type":"assistant","message":{"content":[{"type":"thinking"}]}},20)
        self.assertEqual(claude.state,"thinking")
        claude.apply({"type":"assistant","message":{"stop_reason":"end_turn"}},21)
        self.assertEqual(claude.completed,21)


if __name__=="__main__":
    unittest.main()
