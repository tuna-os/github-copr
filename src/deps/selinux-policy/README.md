## Purpose

SELinux Fedora Policy is a fork of the [SELinux reference policy](https://github.com/SELinuxProject/refpolicy/). The [fedora-selinux/selinux-policy](https://github.com/selinux-policy/selinux-policy.git) repo makes Fedora packaging simpler and more transparent for packagers, upstream developers, and users. It is used for applying downstream Fedora fixes, for communication about proposed/committed changes, and for communication with upstream and the community. It reflects the upstream repository structure to make submitting patches to upstream easy.

## Structure

### GitHub
On GitHub, we have one repository containing the policy sources.

    $ cd selinux-policy
    $ git remote -v
    origin	git@github.com:fedora-selinux/selinux-policy.git (fetch)

    $ git branch -r
    origin/HEAD -> origin/master
    origin/f27
    origin/f28
    origin/master
    origin/rawhide

Note: As opposed to dist-git, the Rawhide content resides in the _rawhide_ branch rather than _master_.

### dist-git
Package sources in dist-git are composed from the _selinux-policy_ repository snapshot tarball, _container-selinux_ policy files snapshot, the _macro-expander_ script snapshot, and from other config files.

## Build process

1. Clone the [fedora-selinux/selinux-policy](https://github.com/fedora-selinux/selinux-policy) repository.

        $ cd ~/devel/github
        $ git clone git@github.com:fedora-selinux/selinux-policy.git
        $ cd selinux-policy

2. Create, backport, or cherry-pick needed changes to a particular branch and push them.

3. Clone the **selinux-policy** dist-git repository.

        $ cd ~/devel/dist-git
        $ fedpkg clone selinux-policy
        $ cd selinux-policy

4. Download the latest snapshot from the selinux-policy GitHub repository.

        $ ./make-rhat-patches.sh

5. Add changes to the dist-git repository, bump release, create a changelog entry, commit, and push.
6. Build the package.

        $ fedpkg build
