# -*- coding: utf-8 -*-

import sys, os, imp
from distutils.core import setup
import py2exe

if not 'py2exe' in sys.argv:
  sys.argv.insert(1, 'py2exe')

py2exe_options = {
  'compressed': 1,
  'optimize': 0,
  'includes': [],
  'excludes': [],
  'dll_excludes': [],
  'packages': [],
  'bundle_files': 2}

def manifest(app_name):
  os.system('img2py -i main_icon.ico main_icon.py')
  return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
  <assembly xmlns="urn:schemas-microsoft-com:asm.v1"
  manifestVersion="1.0">
  <assemblyIdentity
      version="0.64.1.0"
      processorArchitecture="x86"
      name="Controls"
      type="win32"
  />
  <description>%s</description>
  <dependency>
      <dependentAssembly>
          <assemblyIdentity
              type="win32"
              name="Microsoft.Windows.Common-Controls"
              version="6.0.0.0"
              processorArchitecture="X86"
              publicKeyToken="6595b64144ccf1df"
              language="*"
          />
      </dependentAssembly>
  </dependency>
  </assembly>
  """ % (app_name)

setup(
  options = {'py2exe': py2exe_options},
  windows = [{
    'script': 'wxTurtle.py',
    'icon_resources': [(1, 'main_icon.ico')],
    'other_resources': [(24, 1, manifest('wxTurtle'))]}],
  data_files = [
    'akeome.turtle',
    'kotoyoro.turtle',
    'ohayou.turtle',
    'testdata.turtle',
    'msvcp71.dll'],
  zipfile = None)
