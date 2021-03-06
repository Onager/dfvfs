# -*- coding: utf-8 -*-
"""Scanner for volume systems."""

from __future__ import unicode_literals

import abc
import os

from dfvfs.credentials import manager as credentials_manager
from dfvfs.lib import definitions
from dfvfs.lib import errors
from dfvfs.helpers import source_scanner
from dfvfs.helpers import windows_path_resolver
from dfvfs.path import factory as path_spec_factory
from dfvfs.resolver import resolver
from dfvfs.volume import apfs_volume_system
from dfvfs.volume import tsk_volume_system
from dfvfs.volume import vshadow_volume_system


class VolumeScannerMediator(object):
  """Volume scanner mediator."""

  # pylint: disable=redundant-returns-doc

  # TODO: merge GetAPFSVolumeIdentifiers, GetVSSStoreIdentifiers,
  # GetVSSStoreIdentifiers into GetVolumeIdentifiers?

  @abc.abstractmethod
  def GetAPFSVolumeIdentifiers(self, volume_system, volume_identifiers):
    """Retrieves APFS volume identifiers.

    This method can be used to prompt the user to provide APFS volume
    identifiers.

    Args:
      volume_system (APFSVolumeSystem): volume system.
      volume_identifiers (list[str]): volume identifiers including prefix.

    Returns:
      list[str]: selected volume identifiers including prefix or None.
    """

  @abc.abstractmethod
  def GetPartitionIdentifiers(self, volume_system, volume_identifiers):
    """Retrieves partition identifiers.

    This method can be used to prompt the user to provide partition identifiers.

    Args:
      volume_system (TSKVolumeSystem): volume system.
      volume_identifiers (list[str]): volume identifiers including prefix.

    Returns:
      list[str]: selected volume identifiers including prefix or None.
    """

  @abc.abstractmethod
  def GetVSSStoreIdentifiers(self, volume_system, volume_identifiers):
    """Retrieves VSS store identifiers.

    This method can be used to prompt the user to provide VSS store identifiers.

    Args:
      volume_system (VShadowVolumeSystem): volume system.
      volume_identifiers (list[str]): volume identifiers including prefix.

    Returns:
      list[str]: selected volume identifiers including prefix or None.
    """

  @abc.abstractmethod
  def UnlockEncryptedVolume(
      self, source_scanner_object, scan_context, locked_scan_node, credentials):
    """Unlocks an encrypted volume.

    This method can be used to prompt the user to provide encrypted volume
    credentials.

    Args:
      source_scanner_object (SourceScanner): source scanner.
      scan_context (SourceScannerContext): source scanner context.
      locked_scan_node (SourceScanNode): locked scan node.
      credentials (Credentials): credentials supported by the locked scan node.

    Returns:
      bool: True if the volume was unlocked.
    """


class VolumeScanner(object):
  """Volume scanner."""

  def __init__(self, mediator=None):
    """Initializes a volume scanner.

    Args:
      mediator (VolumeScannerMediator): a volume scanner mediator.
    """
    super(VolumeScanner, self).__init__()
    self._mediator = mediator
    self._source_path = None
    self._source_scanner = source_scanner.SourceScanner()
    self._source_type = None

  def _GetAPFSVolumeIdentifiers(self, scan_node):
    """Determines the APFS volume identifiers.

    Args:
      scan_node (SourceScanNode): scan node.

    Returns:
      list[str]: APFS volume identifiers.

    Raises:
      ScannerError: if the format of or within the source is not supported
          or the the scan node is invalid.
      UserAbort: if the user requested to abort.
    """
    if not scan_node or not scan_node.path_spec:
      raise errors.ScannerError('Invalid scan node.')

    volume_system = apfs_volume_system.APFSVolumeSystem()
    volume_system.Open(scan_node.path_spec)

    volume_identifiers = self._source_scanner.GetVolumeIdentifiers(
        volume_system)
    if not volume_identifiers:
      return []

    if len(volume_identifiers) > 1:
      if not self._mediator:
        raise errors.ScannerError(
            'Unable to proceed. APFS volumes found but no mediator to '
            'determine how they should be used.')

      try:
        volume_identifiers = self._mediator.GetAPFSVolumeIdentifiers(
            volume_system, volume_identifiers)
      except KeyboardInterrupt:
        raise errors.UserAbort('File system scan aborted.')

    return self._NormalizedVolumeIdentifiers(
        volume_system, volume_identifiers, prefix='apfs')

  def _GetTSKPartitionIdentifiers(self, scan_node):
    """Determines the TSK partition identifiers.

    Args:
      scan_node (SourceScanNode): scan node.

    Returns:
      list[str]: TSK partition identifiers.

    Raises:
      ScannerError: if the format of or within the source is not supported or
          the scan node is invalid or if the volume for a specific identifier
          cannot be retrieved.
      UserAbort: if the user requested to abort.
    """
    if not scan_node or not scan_node.path_spec:
      raise errors.ScannerError('Invalid scan node.')

    volume_system = tsk_volume_system.TSKVolumeSystem()
    volume_system.Open(scan_node.path_spec)

    volume_identifiers = self._source_scanner.GetVolumeIdentifiers(
        volume_system)
    if not volume_identifiers:
      return []

    if len(volume_identifiers) == 1:
      return volume_identifiers

    if not self._mediator:
      raise errors.ScannerError(
          'Unable to proceed. Partitions found but no mediator to determine '
          'how they should be used.')

    try:
      volume_identifiers = self._mediator.GetPartitionIdentifiers(
          volume_system, volume_identifiers)

    except KeyboardInterrupt:
      raise errors.UserAbort('File system scan aborted.')

    return self._NormalizedVolumeIdentifiers(
        volume_system, volume_identifiers, prefix='p')

  def _GetVSSStoreIdentifiers(self, scan_node):
    """Determines the VSS store identifiers.

    Args:
      scan_node (SourceScanNode): scan node.

    Returns:
      list[str]: VSS store identifiers.

    Raises:
      ScannerError: if the format the scan node is invalid or no mediator
          is provided and VSS store identifiers are found.
      UserAbort: if the user requested to abort.
    """
    if not scan_node or not scan_node.path_spec:
      raise errors.ScannerError('Invalid scan node.')

    volume_system = vshadow_volume_system.VShadowVolumeSystem()
    volume_system.Open(scan_node.path_spec)

    volume_identifiers = self._source_scanner.GetVolumeIdentifiers(
        volume_system)
    if not volume_identifiers:
      return []

    if not self._mediator:
      raise errors.ScannerError(
          'Unable to proceed. VSS stores found but no mediator to determine '
          'how they should be used.')

    try:
      volume_identifiers = self._mediator.GetVSSStoreIdentifiers(
          volume_system, volume_identifiers)

    except KeyboardInterrupt:
      raise errors.UserAbort('File system scan aborted.')

    return self._NormalizedVolumeIdentifiers(
        volume_system, volume_identifiers, prefix='vss')

  def _NormalizedVolumeIdentifiers(
      self, volume_system, volume_identifiers, prefix='v'):
    """Normalizes volume identifiers.

    Args:
      volume_system (VolumeSystem): volume system.
      volume_identifiers (list[int|str]): allowed volume identifiers, formatted
          as an integer or string with prefix.
      prefix (Optional[str]): volume identifier prefix.

    Returns:
      list[str]: volume identifiers with prefix.

    Raises:
      ScannerError: if the volume identifier is not supported or no volume
          could be found that corresponds with the identifier.
    """
    normalized_volume_identifiers = []
    for volume_identifier in volume_identifiers:
      if isinstance(volume_identifier, int):
        volume_identifier = '{0:s}{1:d}'.format(prefix, volume_identifier)

      elif not volume_identifier.startswith(prefix):
        try:
          volume_identifier = int(volume_identifier, 10)
          volume_identifier = '{0:s}{1:d}'.format(prefix, volume_identifier)
        except (TypeError, ValueError):
          pass

      try:
        volume = volume_system.GetVolumeByIdentifier(volume_identifier)
      except KeyError:
        volume = None

      if not volume:
        raise errors.ScannerError(
            'Volume missing for identifier: {0:s}.'.format(volume_identifier))

      normalized_volume_identifiers.append(volume_identifier)

    return normalized_volume_identifiers

  def _ScanEncryptedVolume(self, scan_context, scan_node):
    """Scans an encrypted volume scan node for volume and file systems.

    Args:
      scan_context (SourceScannerContext): source scanner context.
      scan_node (SourceScanNode): volume scan node.

    Raises:
      ScannerError: if the format of or within the source is not supported,
          the scan node is invalid, there are no credentials defined for
          the format or no mediator is provided and a locked scan node was
          found, e.g. an encrypted volume,
    """
    if not scan_node or not scan_node.path_spec:
      raise errors.ScannerError('Invalid or missing scan node.')

    credentials = credentials_manager.CredentialsManager.GetCredentials(
        scan_node.path_spec)
    if not credentials:
      raise errors.ScannerError('Missing credentials for scan node.')

    if not self._mediator:
      raise errors.ScannerError(
          'Unable to proceed. Encrypted volume found but no mediator to '
          'determine how it should be unlocked.')

    if self._mediator.UnlockEncryptedVolume(
        self._source_scanner, scan_context, scan_node, credentials):
      self._source_scanner.Scan(
          scan_context, scan_path_spec=scan_node.path_spec)

  def _ScanFileSystem(self, scan_node, base_path_specs):
    """Scans a file system scan node for file systems.

    Args:
      scan_node (SourceScanNode): file system scan node.
      base_path_specs (list[PathSpec]): file system base path specifications.

    Raises:
      ScannerError: if the scan node is invalid.
    """
    if not scan_node or not scan_node.path_spec:
      raise errors.ScannerError('Invalid or missing file system scan node.')

    base_path_specs.append(scan_node.path_spec)

  def _ScanVolume(self, scan_context, scan_node, base_path_specs):
    """Scans a volume scan node for volume and file systems.

    Args:
      scan_context (SourceScannerContext): source scanner context.
      scan_node (SourceScanNode): volume scan node.
      base_path_specs (list[PathSpec]): file system base path specifications.

    Raises:
      ScannerError: if the format of or within the source
          is not supported or the scan node is invalid.
    """
    if not scan_node or not scan_node.path_spec:
      raise errors.ScannerError('Invalid or missing scan node.')

    if scan_context.IsLockedScanNode(scan_node.path_spec):
      # The source scanner found a locked volume and we need a credential to
      # unlock it.
      self._ScanEncryptedVolume(scan_context, scan_node)

      if scan_context.IsLockedScanNode(scan_node.path_spec):
        return

    if scan_node.IsVolumeSystemRoot():
      self._ScanVolumeSystemRoot(scan_context, scan_node, base_path_specs)

    elif scan_node.IsFileSystem():
      self._ScanFileSystem(scan_node, base_path_specs)

    elif scan_node.type_indicator == definitions.TYPE_INDICATOR_VSHADOW:
      # TODO: look into building VSS store on demand.

      # We "optimize" here for user experience, alternatively we could scan for
      # a file system instead of hard coding a TSK child path specification.
      path_spec = path_spec_factory.Factory.NewPathSpec(
          definitions.TYPE_INDICATOR_TSK, location='/',
          parent=scan_node.path_spec)

      base_path_specs.append(path_spec)

    else:
      for sub_scan_node in scan_node.sub_nodes:
        self._ScanVolume(scan_context, sub_scan_node, base_path_specs)

  def _ScanVolumeSystemRoot(self, scan_context, scan_node, base_path_specs):
    """Scans a volume system root scan node for volume and file systems.

    Args:
      scan_context (SourceScannerContext): source scanner context.
      scan_node (SourceScanNode): volume system root scan node.
      base_path_specs (list[PathSpec]): file system base path specifications.

    Raises:
      ScannerError: if the scan node is invalid, the scan node type is not
          supported or if a sub scan node cannot be retrieved.
    """
    if not scan_node or not scan_node.path_spec:
      raise errors.ScannerError('Invalid scan node.')

    if scan_node.type_indicator == definitions.TYPE_INDICATOR_APFS_CONTAINER:
      volume_identifiers = self._GetAPFSVolumeIdentifiers(scan_node)

    elif scan_node.type_indicator == definitions.TYPE_INDICATOR_VSHADOW:
      volume_identifiers = self._GetVSSStoreIdentifiers(scan_node)
      # Process VSS stores (snapshots) starting with the most recent one.
      volume_identifiers.reverse()

    else:
      raise errors.ScannerError(
          'Unsupported volume system type: {0:s}.'.format(
              scan_node.type_indicator))

    for volume_identifier in volume_identifiers:
      location = '/{0:s}'.format(volume_identifier)
      sub_scan_node = scan_node.GetSubNodeByLocation(location)
      if not sub_scan_node:
        raise errors.ScannerError(
            'Scan node missing for volume identifier: {0:s}.'.format(
                volume_identifier))

      self._ScanVolume(scan_context, sub_scan_node, base_path_specs)

  def GetBasePathSpecs(self, source_path):
    """Determines the base path specifications.

    Args:
      source_path (str): source path.

    Returns:
      list[PathSpec]: path specifications.

    Raises:
      ScannerError: if the source path does not exists, or if the source path
          is not a file or directory, or if the format of or within the source
          file is not supported.
    """
    if not source_path:
      raise errors.ScannerError('Invalid source path.')

    # Note that os.path.exists() does not support Windows device paths.
    if (not source_path.startswith('\\\\.\\') and
        not os.path.exists(source_path)):
      raise errors.ScannerError(
          'No such device, file or directory: {0:s}.'.format(source_path))

    scan_context = source_scanner.SourceScannerContext()
    scan_context.OpenSourcePath(source_path)

    try:
      self._source_scanner.Scan(scan_context)
    except (ValueError, errors.BackEndError) as exception:
      raise errors.ScannerError(
          'Unable to scan source with error: {0!s}'.format(exception))

    self._source_path = source_path
    self._source_type = scan_context.source_type

    if self._source_type not in [
        definitions.SOURCE_TYPE_STORAGE_MEDIA_DEVICE,
        definitions.SOURCE_TYPE_STORAGE_MEDIA_IMAGE]:
      scan_node = scan_context.GetRootScanNode()
      return [scan_node.path_spec]

    # Get the first node where where we need to decide what to process.
    scan_node = scan_context.GetRootScanNode()
    while len(scan_node.sub_nodes) == 1:
      scan_node = scan_node.sub_nodes[0]

    base_path_specs = []
    if scan_node.type_indicator != definitions.TYPE_INDICATOR_TSK_PARTITION:
      self._ScanVolume(scan_context, scan_node, base_path_specs)

    else:
      # Determine which partition needs to be processed.
      partition_identifiers = self._GetTSKPartitionIdentifiers(scan_node)
      for partition_identifier in partition_identifiers:
        location = '/{0:s}'.format(partition_identifier)
        sub_scan_node = scan_node.GetSubNodeByLocation(location)
        self._ScanVolume(scan_context, sub_scan_node, base_path_specs)

    return base_path_specs


class WindowsVolumeScanner(VolumeScanner):
  """Windows volume scanner."""

  _WINDOWS_DIRECTORIES = frozenset([
      'C:\\Windows',
      'C:\\WINNT',
      'C:\\WTSRV',
      'C:\\WINNT35',
  ])

  def __init__(self, mediator=None):
    """Initializes a Windows volume scanner.

    Args:
      mediator (VolumeScannerMediator): a volume scanner mediator.
    """
    super(WindowsVolumeScanner, self).__init__(mediator=mediator)
    self._file_system = None
    self._path_resolver = None
    self._windows_directory = None

  def _ScanFileSystem(self, scan_node, base_path_specs):
    """Scans a file system scan node for file systems.

    This method checks if the file system contains a known Windows directory.

    Args:
      scan_node (SourceScanNode): file system scan node.
      base_path_specs (list[PathSpec]): file system base path specifications.

    Raises:
      ScannerError: if the scan node is invalid.
    """
    if not scan_node or not scan_node.path_spec:
      raise errors.ScannerError('Invalid or missing file system scan node.')

    file_system = resolver.Resolver.OpenFileSystem(scan_node.path_spec)
    if not file_system:
      return

    try:
      path_resolver = windows_path_resolver.WindowsPathResolver(
          file_system, scan_node.path_spec.parent)

      if self._ScanFileSystemForWindowsDirectory(path_resolver):
        base_path_specs.append(scan_node.path_spec)

    finally:
      file_system.Close()

  def _ScanFileSystemForWindowsDirectory(self, path_resolver):
    """Scans a file system for a known Windows directory.

    Args:
      path_resolver (WindowsPathResolver): Windows path resolver.

    Returns:
      bool: True if a known Windows directory was found.
    """
    result = False
    for windows_path in self._WINDOWS_DIRECTORIES:
      windows_path_spec = path_resolver.ResolvePath(windows_path)

      result = windows_path_spec is not None
      if result:
        self._windows_directory = windows_path
        break

    return result

  def OpenFile(self, windows_path):
    """Opens the file specificed by the Windows path.

    Args:
      windows_path (str): Windows path to the file.

    Returns:
      FileIO: file-like object or None if the file does not exist.
    """
    path_spec = self._path_resolver.ResolvePath(windows_path)
    if path_spec is None:
      return None

    return self._file_system.GetFileObjectByPathSpec(path_spec)

  def ScanForWindowsVolume(self, source_path):
    """Scans for a Windows volume.

    Args:
      source_path (str): source path.

    Returns:
      bool: True if a Windows volume was found.

    Raises:
      ScannerError: if the source path does not exists, or if the source path
          is not a file or directory, or if the format of or within the source
          file is not supported.
    """
    windows_path_specs = self.GetBasePathSpecs(source_path)
    if (not windows_path_specs or
        self._source_type == definitions.SOURCE_TYPE_FILE):
      return False

    file_system_path_spec = windows_path_specs[0]
    self._file_system = resolver.Resolver.OpenFileSystem(file_system_path_spec)

    if file_system_path_spec.type_indicator == definitions.TYPE_INDICATOR_OS:
      mount_point = file_system_path_spec
    else:
      mount_point = file_system_path_spec.parent

    self._path_resolver = windows_path_resolver.WindowsPathResolver(
        self._file_system, mount_point)

    # The source is a directory or single volume storage media image.
    if not self._windows_directory:
      self._ScanFileSystemForWindowsDirectory(self._path_resolver)

    if not self._windows_directory:
      return False

    self._path_resolver.SetEnvironmentVariable(
        'SystemRoot', self._windows_directory)
    self._path_resolver.SetEnvironmentVariable(
        'WinDir', self._windows_directory)

    return True
