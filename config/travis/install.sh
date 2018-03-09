#!/bin/bash
#
# Script to set up Travis-CI test VM.

COVERALLS_DEPENDENCIES="python-coverage python-coveralls python-docopt";

L2TBINARIES_DEPENDENCIES="construct dfdatetime libbde libewf libfsntfs libfvde libfwnt libqcow libsigscan libsmdev libsmraw libvhdi libvmdk libvshadow libvslvm lzma pycrypto pysqlite pytsk3 six";

L2TBINARIES_TEST_DEPENDENCIES="funcsigs mock pbr";

PYTHON2_DEPENDENCIES="libbde-python libewf-python libfsntfs-python libfvde-python libfwnt-python libqcow-python libsigscan-python libsmdev-python libsmraw-python libvhdi-python libvmdk-python libvshadow-python libvslvm-python python-backports.lzma python-construct python-crypto python-dfdatetime python-pysqlite2 python-pytsk3 python-six";

PYTHON2_TEST_DEPENDENCIES="python-mock python-tox";

PYTHON3_DEPENDENCIES="libbde-python3 libewf-python3 libfsntfs-python3 libfvde-python3 libfwnt-python3 libqcow-python3 libsigscan-python3 libsmdev-python3 libsmraw-python3 libvhdi-python3 libvmdk-python3 libvshadow-python3 libvslvm-python3 python3-construct python3-crypto python3-dfdatetime python3-pysqlite2 python3-pytsk3 python3-six";

PYTHON3_TEST_DEPENDENCIES="python3-mock python3-setuptools python3-tox";

# Exit on error.
set -e;

if test ${TRAVIS_OS_NAME} = "osx";
then
	git clone https://github.com/log2timeline/l2tbinaries.git -b dev;

	mv l2tbinaries ../;

	for PACKAGE in ${L2TBINARIES_DEPENDENCIES};
	do
		sudo /usr/bin/hdiutil attach ../l2tbinaries/macos/${PACKAGE}-*.dmg;
		sudo /usr/sbin/installer -target / -pkg /Volumes/${PACKAGE}-*.pkg/${PACKAGE}-*.pkg;
		sudo /usr/bin/hdiutil detach /Volumes/${PACKAGE}-*.pkg
	done

	for PACKAGE in ${L2TBINARIES_TEST_DEPENDENCIES};
	do
		sudo /usr/bin/hdiutil attach ../l2tbinaries/macos/${PACKAGE}-*.dmg;
		sudo /usr/sbin/installer -target / -pkg /Volumes/${PACKAGE}-*.pkg/${PACKAGE}-*.pkg;
		sudo /usr/bin/hdiutil detach /Volumes/${PACKAGE}-*.pkg
	done

elif test ${TRAVIS_OS_NAME} = "linux";
then
	sudo rm -f /etc/apt/sources.list.d/travis_ci_zeromq3-source.list;

	sudo add-apt-repository ppa:gift/dev -y;
	sudo apt-get update -q;

	if test ${TRAVIS_PYTHON_VERSION} = "2.7";
	then
		sudo apt-get install -y ${COVERALLS_DEPENDENCIES} ${PYTHON2_DEPENDENCIES} ${PYTHON2_TEST_DEPENDENCIES};
	else
		sudo apt-get install -y ${PYTHON3_DEPENDENCIES} ${PYTHON3_TEST_DEPENDENCIES};
	fi
fi
