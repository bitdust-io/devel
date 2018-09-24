from distutils.core import setup
from distutils.extension import Extension

from Cython.Build import cythonize
from Cython.Distutils import build_ext
ext_modules = cythonize('example_cython.pyx')
setup(
    # name = 'my_cython_lib',
    cmdclass = {'build_ext': build_ext},
    ext_modules = ext_modules
)
