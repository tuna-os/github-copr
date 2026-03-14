#!/bin/bash
. /usr/share/beakerlib/beakerlib.sh || exit 1

NAME=harfbuzz

rlJournalStart
    rlPhaseStartSetup
        rlAssertRpm ${NAME}
        rlAssertRpm ${NAME}-devel
        rlShowPackageVersion ${NAME}
        rlRun -t -l "VERSION=$(rpm -q ${NAME} --queryformat='%{version}')" 0 "Get VERSION"
        FEDORA_VERSION=$(rlGetDistroRelease)
        rlLog "FEDORA_VERSION=${DISTRO_RELEASE}"
        rlRun "tmp=\$(mktemp -d)" 0 "Create tmp directory"
        rlRun "pushd $tmp"
        rlFetchSrcForInstalled "${NAME}"
        rlRun "rpm --define '_topdir $tmp' -i *src.rpm"
        rlRun -t -l "mkdir BUILD" 0 "Creating BUILD directory"
        rlRun -t -l "rpmbuild --noclean --nodeps --define '_topdir $tmp' -bp $tmp/SPECS/*spec"
        if [ -d BUILD/${NAME}-${VERSION}-build ]; then
            rlRun -t -l "pushd BUILD/${NAME}-${VERSION}-build/${NAME}-${VERSION}"
        else
            rlRun -t -l "pushd BUILD/${NAME}-${VERSION}"
        fi
        rlRun "set -o pipefail"
        rlRun "meson build -Dgraphite2=enabled -Dchafa=disabled"
        rlRun "pushd build"
        rlRun "meson test"
        rlRun "retval=$?"
        rlRun "echo $retval"
        rlRun "popd"
    rlPhaseEnd

    rlPhaseStartTest
        rlRun -t -l "INSTALLED_VERSION=$(hb-info --version|awk 'NR==1 {print $3}')" \
              0 "Get installed version"
        rlAssertEquals "versions should be equal" "${VERSION}" "${INSTALLED_VERSION}"
        rlGetTestState
        rlLog "Number of failed asserts so far: ${ECODE}"
        rlRun "popd" 0
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "popd"
        rlRun "rm -r $tmp" 0 "Remove tmp directory"
    rlPhaseEnd
rlJournalEnd

