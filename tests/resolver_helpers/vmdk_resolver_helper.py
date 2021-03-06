#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Tests for the VMDK image resolver helper implementation."""

from __future__ import unicode_literals

import unittest

from dfvfs.resolver_helpers import vmdk_resolver_helper

from tests.resolver_helpers import test_lib


class VMDKResolverHelperTest(test_lib.ResolverHelperTestCase):
  """Tests for the VMDK image resolver helper implementation."""

  def testNewFileObject(self):
    """Tests the NewFileObject function."""
    resolver_helper_object = vmdk_resolver_helper.VMDKResolverHelper()
    self._TestNewFileObject(resolver_helper_object)

  def testNewFileSystem(self):
    """Tests the NewFileSystem function."""
    resolver_helper_object = vmdk_resolver_helper.VMDKResolverHelper()
    self._TestNewFileSystemRaisesNotSupported(resolver_helper_object)


if __name__ == '__main__':
  unittest.main()
