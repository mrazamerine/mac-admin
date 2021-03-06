#!/usr/bin/python

#  buildMunkiPkg.py
#
#
#  Created by Jacob F. Grant
#
#  Written: 05/13/17
#  Updated: 08/28/17
#

"""
buildMunkiPkg

A script to sync permissions and build all MacOS
packages in a directory using the munkipkg tool.

https://github.com/munki/munki-pkg

Must be run with sudo.
"""

import sys
import os
import subprocess
import argparse
import shutil
import pwd
import grp


def inPath(exe):
    """Check PATH environment for executable."""
    for path in os.environ["PATH"].split(os.pathsep):
        path = path.strip('"')
        exe_path = os.path.join(path, exe)
        if os.path.isfile(exe_path):
            return exe_path
    return None


def isPackage(pkgDir):
    """Check the contents of a directory for the files/directories required for munkipkg."""
    # Check for 'payload' or 'scripts' directories
    if not (os.path.isdir(os.path.join(pkgDir, 'payload')) or
            os.path.isdir(os.path.join(pkgDir, 'scripts'))
           ):
        print >> sys.stderr, "buildMunkiPkg:", pkgDir, "missing payload and scripts directories"
        return False

    # Check for 'Bom.txt'
    if not os.path.isfile(os.path.join(pkgDir, 'Bom.txt')):
        print >> sys.stderr, "buildMunkiPkg:", pkgDir, "missing Bom.txt"
        return False

    # Check for 'build-info[.plist][.json][.yml]'
    for ext in ['.plist', '.json', '.yml']:
        if os.path.isfile(os.path.join(pkgDir, ('build-info' + ext))):
            return True

    print >> sys.stderr, "buildMunkiPkg:", pkgDir, "missing build-info file"
    return False


def syncPermissions(pkgDir, quiet=False):
    """Sync the permissions to files/directories from Bom.txt file."""
    if quiet:
        return subprocess.call(['munkipkg', '--sync', pkgDir, '--quiet'])
    else:
        return subprocess.call(['munkipkg', '--sync', pkgDir])


def resetOwner(pkgDir, quiet=False):
    """Resets the ownership of package files/directories"""
    pkgUid = os.stat(pkgDir).st_uid
    pkgGid = os.stat(pkgDir).st_gid
    pkgName = pwd.getpwuid(pkgUid)[0]
    pkgGroup = grp.getgrgid(pkgGid)[0]
    if not quiet:
        print >> sys.stdout, "buildMunkiPkg: setting ownership of" + pkgDir + "to" + pkgName + ":" + pkgGroup
    for root, dirs, files in os.walk(pkgDir):
        for d in dirs:
            os.chown(os.path.join(root, d), pkgUid, pkgGid)
        for f in files:
            os.chown(os.path.join(root, f), pkgUid, pkgGid)
    return


def makePackage(pkgDir, quiet=False):
    """Build munkipkg package."""
    if quiet:
        return subprocess.call(['munkipkg', pkgDir, '--quiet'])
    else:
        return subprocess.call(['munkipkg', pkgDir])


def movePackage(buildLocation, pkgDir, quiet=False):
    """Move package file from munkipkg directory to central location."""
    # Check for build directory in pkgDir
    # Retun with error if does not exist
    pkgDirBuild = os.path.join(pkgDir, 'build')
    if not os.path.exists(pkgDirBuild):
        print >> sys.stderr, "buildMunkiPkg: no build directory in", pkgDir
        return

    pkgUid = os.stat(pkgDir).st_uid
    pkgGid = os.stat(pkgDir).st_gid
    pkgName = pwd.getpwuid(pkgUid)[0]
    pkgGroup = grp.getgrgid(pkgGid)[0]

    # Check for build directory in buildLocation
    # Create directory if does not exist
    buildLocationDir = os.path.join(buildLocation, 'build')
    if not os.path.exists(buildLocationDir):
        print >> sys.stdout, "buildMunkiPkg: creating ", buildLocationDir
        os.makedirs(buildLocationDir)
        os.chown(buildLocationDir, pkgUid, pkgGid)

    # Moves all files ending with '.pkg'
    # Deletes directory if empty
    isEmpty = False
    for pkg in os.listdir(pkgDirBuild):
        if pkg.endswith('.pkg'):
            oldPkg = os.path.join(pkgDirBuild, pkg)
            newPkg = os.path.join(buildLocationDir, pkg)
            os.rename(oldPkg, newPkg)
            os.chown(newPkg, pkgUid, pkgGid)
            if not quiet:
                print >> sys.stdout, "buildMunkiPkg:", pkg, "moved to", buildLocationDir
        else:
            isEmpty = True
    if not isEmpty:
        if not quiet:
            print >> sys.stdout, "buildMunkiPkg: removing empty directory", pkgDirBuild
        shutil.rmtree(pkgDirBuild)
    return


def main():
    # Parse script arguments
    mainParser = argparse.ArgumentParser(
        description='Syncs permissions and builds multiple packages using the munkipkg tool.')
    mainParser.add_argument(
        '-q',
        '--quiet',
        action="store_true",
        help="Suppress normal output messages. Errors will still be printed to stderr."
    )
    mainParser.add_argument(
        '-o',
        '--owner',
        action="store_true",
        help=("Sets ownership of directories/files in packages to those specified in Bom.txt. "
              "If you do not include this option, files/directories will be reset to current owner.")
    )
    mainParser.add_argument(
        '-d',
        '--directory',
        help="Runs buildMunkiPkg.py on the given directory. Defaults to current directory.",
        default='.'
    )
    mainParser.add_argument(
        '-b',
        '--buildLocation',
        help="Location of directory with built packages. Defaults to current directory.",
        default='.'
    )
    args = mainParser.parse_args()
    quiet = args.quiet
    owner = args.owner

    # Check if script is running as root
    if os.geteuid() != 0:
        print >> sys.stderr, "This script must be run as root"
        return 1

    # Check if munkipkg executable is in PATH env
    exe_path = inPath('munkipkg')
    if not exe_path:
        print >> sys.stderr, "munkipkg not found in PATH"
        return 1

    # Check if given directories are really directories
    currentDir = args.directory
    buildLocation = args.buildLocation
    if not os.path.isdir(currentDir):
        print >> sys.stderr, currentDir, "is not a directory"
        return 1
    if not os.path.isdir(buildLocation):
        print >> sys.stderr, buildLocation, "is not a directory"
        return 1

    # Build packages
    if isPackage(currentDir):
        pkgDir = currentDir
        syncPermissions(pkgDir, quiet)
        makePackage(pkgDir, quiet)
        movePackage(buildLocation, pkgDir, quiet)
        if not owner:
            resetOwner(pkgDir, quiet)
    else:
        print >> sys.stdout, "buildMunkiPkg: examining directories in", currentDir
        for subDir in os.listdir(currentDir):
            pkgDir = os.path.join(currentDir, subDir)
            if os.path.isdir(pkgDir):
                if isPackage(pkgDir):
                    syncPermissions(pkgDir, quiet)
                    makePackage(pkgDir, quiet)
                    movePackage(buildLocation, pkgDir, quiet)
                    if not owner:
                        resetOwner(pkgDir, quiet)
    return


if __name__ == "__main__":
    main()
