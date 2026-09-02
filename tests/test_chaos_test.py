import unittest
from demo.chaos_test import run_chaos_demo

class TestChaosDemo(unittest.TestCase):
    def test_run_chaos_demo(self):
        res = run_chaos_demo(site="spicejet", target_field="total_fare", dry_run=True)
        self.assertTrue(res)

if __name__ == "__main__":
    unittest.main()
