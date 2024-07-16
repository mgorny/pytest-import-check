# (c) 2024 Michał Górny
# SPDX-License-Identifier: GPL-2.0-or-later

import subprocess
import sys

import pytest


@pytest.fixture(params=[False, True])
def py_limited_api(request):
    yield request.param


@pytest.fixture
def build_c_ext(pytester, py_limited_api):
    def inner(code=""):
        pytester.makefile(".c", test=f"""
            #define PY_SSIZE_T_CLEAN
            #include <Python.h>

            static struct PyModuleDef testmodule = {{
                PyModuleDef_HEAD_INIT,
                .m_name = "test",
                .m_doc = NULL,
                .m_size = -1,
                .m_methods = NULL,
            }};

            extern void this_function_does_not_exist();

            PyMODINIT_FUNC
            PyInit_test(void)
            {{
                {code}
                return PyModule_Create(&testmodule);
            }}
        """)
        pytester.makepyfile(setup=f"""
            import os

            from setuptools import setup, Extension

            extra_link_args = []
            # TODO: this should really be per-linker
            if os.name == "nt":
                extra_link_args.append("/force:unresolved")

            setup(name="test",
                  version="0",
                  ext_modules=[
                      Extension(name="test",
                                sources=["test.c"],
                                py_limited_api={py_limited_api},
                                extra_link_args=extra_link_args),
                  ])
        """)
        subprocess.run([sys.executable, "setup.py", "build_ext", "-i"],
                       check=True)
    yield inner


def test_c_ext(run, build_c_ext):
    build_c_ext()
    result = run("--ignore=setup.py")
    result.assert_outcomes(passed=1)


def test_c_ext_undefined_symbol(run, build_c_ext):
    build_c_ext(code="this_function_does_not_exist();")
    result = run("--ignore=setup.py")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines([
        "test.*::import-check*FAILED*",
        "E*ImportError*test.*this_function_does_not_exist*",
    ])
    # check whether we got nicely stripped traceback
    #result.stdout.no_fnmatch_line("*/_pytest/*")
    #result.stdout.no_fnmatch_line("*importlib*")
