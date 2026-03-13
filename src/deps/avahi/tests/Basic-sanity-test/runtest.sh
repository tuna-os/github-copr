#!/bin/bash
# vim: dict=/usr/share/beakerlib/dictionary.vim cpt=.,w,b,u,t,i,k
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   runtest.sh of /CoreOS/avahi/Sanity/Basic-sanity-test
#   Description: Tests basic functionality of avahi.
#   Author: Martin Cermak <mcermak@redhat.com>
#   Author: Tomas Dolezal <todoleza@redhat.com> - rhel7 updates
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   Copyright (c) 2013 Red Hat, Inc. 
#
#   This copyrighted material is made available to anyone wishing
#   to use, modify, copy, or redistribute it subject to the terms
#   and conditions of the GNU General Public License version 2.
#
#   This program is distributed in the hope that it will be
#   useful, but WITHOUT ANY WARRANTY; without even the implied
#   warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#   PURPOSE. See the GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public
#   License along with this program; if not, write to the Free
#   Software Foundation, Inc., 51 Franklin Street, Fifth Floor,
#   Boston, MA 02110-1301, USA.
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Include rhts environment
. /usr/bin/rhts-environment.sh
. /usr/lib/beakerlib/beakerlib.sh

TEMPSTR=$(date +%c%N | md5sum | awk '{print $1}' | cut -c -8)
ORIGPWD=$(pwd)

IP1='127.0.0.1'
IP2='::1'

rlJournalStart
    rlPhaseStartSetup
        rlAssertRpm 'avahi'
        rlAssertRpm 'avahi-tools'

        rlRun "TmpDir=\`mktemp -d\`" 0 "Creating tmp directory"
        rlRun "pushd $TmpDir"

        ROOTDIR="" #using non-chroot
        rlFileBackup /etc/named.conf /etc/resolv.conf
        rlFileBackup --clean /var/named/
        cat $ORIGPWD/named.conf > /etc/named.conf

        rlRun "TDOMAIN=$TEMPSTR.cz"
        rlRun "TZONEFILE=$ROOTDIR/var/named/$TDOMAIN.zone"

        # set up /etc/named.conf
        rlRun "sed -i \"s/<DOMAIN>/$TDOMAIN/g\" /etc/named.conf"

        # set up zonefile
        rlRun "cp $ORIGPWD/zonefile $TZONEFILE"
        rlRun "chmod a+r $TZONEFILE"
        rlRun "sed -i \"s/<DOMAIN>/$TDOMAIN/g\" $TZONEFILE"
        rlRun "sed -i \"s/<IP1>/$IP1/g\" $TZONEFILE"
        rlRun "sed -i \"s/<IP2>/$IP2/g\" $TZONEFILE"
        rlRun "sed -i \"s/<SERIAL>/$(date +%N)/g\" $TZONEFILE"

        rlServiceStart named #using non-chroot

        # set default resolver
        rlRun "echo nameserver 127.0.0.1 > /etc/resolv.conf"
    rlPhaseEnd

    rlPhaseStartTest
        # check bind
        rlRun "dig @localhost server1.$TDOMAIN +short | grep $IP1"
        rlRun "dig AAAA @localhost server2.$TDOMAIN +short | grep $IP2"

        # turn on avahi or restart it with new resolv.conf
        rlServiceStart "avahi-daemon"

        # the test itself...
        rlRun "avahi-resolve -4n server1.$TDOMAIN | grep '127.0.0.1'" 0 "Test the IPv4 avahi DN resolver."
        rlRun "avahi-resolve -6n server2.$TDOMAIN | grep '::1'" 0 "Test the IPv6 avahi DN resolver."

    rlPhaseEnd

    rlPhaseStartCleanup
        rlFileRestore
        rlServiceStart avahi-daemon
        rlServiceRestore named avahi-daemon

        rlRun "popd"
        rlRun "rm -r $TmpDir" 0 "Removing tmp directory"
    rlPhaseEnd
 rlJournalPrintText
rlJournalEnd
