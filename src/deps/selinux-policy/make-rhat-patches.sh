#!/usr/bin/bash

DISTGIT_PATH=$(pwd)

FEDORA_VERSION=rawhide
DOCKER_FEDORA_VERSION=master
DISTGIT_BRANCH=rawhide
REPO_SELINUX_POLICY=${REPO_SELINUX_POLICY:-https://github.com/fedora-selinux/selinux-policy}
REPO_SELINUX_POLICY_BRANCH=${REPO_SELINUX_POLICY_BRANCH:-$FEDORA_VERSION}
REPO_CONTAINER_SELINUX=${REPO_CONTAINER_SELINUX:-https://github.com/containers/container-selinux}
REPO_MACRO_EXPANDER=${REPO_MACRO_EXPANDER:-https://github.com/fedora-selinux/macro-expander.git}

# When -l is specified, we use locally created tarballs and don't download them from github
DOWNLOAD_DEFAULT_GITHUB_TARBALLS=1
if [ "$1" == "-l" ]; then
    DOWNLOAD_DEFAULT_GITHUB_TARBALLS=0
fi

git checkout $DISTGIT_BRANCH -q

POLICYSOURCES=`mktemp -d --tmpdir policysources.XXXXXX`
pushd $POLICYSOURCES > /dev/null

git clone --depth=1 -q $REPO_SELINUX_POLICY selinux-policy \
    -b $REPO_SELINUX_POLICY_BRANCH
git clone --depth=1 -q $REPO_CONTAINER_SELINUX container-selinux
git clone --depth=1 -q $REPO_MACRO_EXPANDER macro-expander

pushd selinux-policy > /dev/null
# prepare policy patches against upstream commits matching the last upstream merge
BASE_HEAD_ID=$(git rev-parse HEAD)
BASE_SHORT_HEAD_ID=$(c=${BASE_HEAD_ID}; echo ${c:0:7})
git archive --prefix=selinux-policy-$BASE_HEAD_ID/ --format tgz HEAD > $DISTGIT_PATH/selinux-policy-$BASE_SHORT_HEAD_ID.tar.gz
popd > /dev/null

pushd container-selinux > /dev/null
# Actual container-selinux files are in master branch
#git checkout -b ${DOCKER_FEDORA_VERSION} -t origin/${DOCKER_FEDORA_VERSION} -q
tar -czf container-selinux.tgz container.if container.te container.fc
popd > /dev/null

pushd $DISTGIT_PATH > /dev/null
if [ $DOWNLOAD_DEFAULT_GITHUB_TARBALLS == 1 ]; then
    wget -O selinux-policy-${BASE_SHORT_HEAD_ID}.tar.gz https://github.com/fedora-selinux/selinux-policy/archive/${BASE_HEAD_ID}.tar.gz &> /dev/null
fi
cp $POLICYSOURCES/container-selinux/container-selinux.tgz .
cp $POLICYSOURCES/macro-expander/macro-expander.sh ./macro-expander
chmod +x ./macro-expander
popd > /dev/null

popd > /dev/null
rm -rf $POLICYSOURCES

# Update commit id in selinux-policy.spec file
sed -i "s/%global commit [^ ]*$/%global commit $BASE_HEAD_ID/" selinux-policy.spec

# Update sources
sha512sum --tag selinux-policy-${BASE_SHORT_HEAD_ID}.tar.gz container-selinux.tgz macro-expander > sources

echo -e "\nSELinux policy tarball and container-selinux.tgz with container policy files have been created."
echo "Commit id of selinux-policy in spec file was changed to ${BASE_HEAD_ID}"
