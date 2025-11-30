#!/usr/bin/env python3
# coding:utf-8

import sys
import traceback
import motor_test

def execute_test(test):
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.TestLoader().loadTestsFromModule(test)
    )

    if len(result.errors) != 0 or len(result.failures) != 0:
        sys.exit(-1)


if __name__ == "__main__":
    execute_test(motor_test)
    