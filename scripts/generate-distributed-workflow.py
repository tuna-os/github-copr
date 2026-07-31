#!/usr/bin/env python3
import yaml
import sys
import os

def generate_workflow(manifest_path, output_path, workflow_name='Distributed Build and Publish RPMs',
                      r2_path='repo/10-stream-x86_64', secondary_r2_path='repo/10-x86_64',
                      install_script='contrib/install.sh', install_r2_dest='install.sh',
                      submodules=True, mock_config=None):
    with open(manifest_path, 'r') as f:
        manifest = yaml.safe_load(f)

    # Allow manifest to specify r2_path; CLI arg takes precedence if explicitly set
    manifest_r2_path = manifest.get('r2_path', r2_path)
    if r2_path == 'repo/10-stream-x86_64' and manifest_r2_path != 'repo/10-stream-x86_64':
        r2_path = manifest_r2_path

    tiers = manifest.get('tiers', [])
    manifest_filename = os.path.basename(manifest_path)

    workflow = {
        'name': workflow_name,
        'on': {
            'workflow_dispatch': {
                'inputs': {
                    'force': {
                        'description': 'Force rebuild even if package exists in repo',
                        'type': 'boolean',
                        'default': False
                    }
                }
            }
        },
        'env': {
            'R2_BUCKET': 'bluefin',
            'LOCAL_REPO': '${{ github.workspace }}/local-repo',
            'MOCK_RUNNER_IMAGE': 'ghcr.io/tuna-os/mock-runner:centos-stream-10'
        },
        'jobs': {}
    }
    
    jobs = workflow['jobs']
    
    # 1. Seed Repo Job
    jobs['seed-repo'] = {
        'runs-on': 'ubuntu-latest',
        'steps': [
            {'name': 'Checkout', 'uses': 'actions/checkout@v4'},
            {'name': 'Install dependencies', 'run': 'sudo apt-get update -q && sudo apt-get install -y -q createrepo-c'},
            {'name': 'Configure rclone', 'run': 'curl -fsSL https://rclone.org/install.sh | sudo bash\nmkdir -p ~/.config/rclone\ncat > ~/.config/rclone/rclone.conf << EOF\n[r2]\ntype = s3\nprovider = Cloudflare\naccess_key_id = ${{ secrets.R2_ACCESS_KEY_ID }}\nsecret_access_key = ${{ secrets.R2_SECRET_ACCESS_KEY }}\nendpoint = https://${{ secrets.CLOUDFLARE_ACCOUNT_ID }}.r2.cloudflarestorage.com\nEOF\n'},
            {'name': 'Seed local repo from R2', 'run': f'mkdir -p local-repo\necho "Downloading existing repo from R2..."\nrclone sync "r2:${{R2_BUCKET}}/{r2_path}/" "local-repo/" --exclude "repodata/**" || true\ncreaterepo_c local-repo\n'},
            {'name': 'Upload initial repo', 'uses': 'actions/upload-artifact@v4', 'with': {'name': 'repo-0', 'path': 'local-repo', 'retention-days': 1}}
        ]
    }
    
    prev_tier_repo = 'repo-0'
    prev_consolidate_job = 'seed-repo'
    
    # Build --manifest flag for build-chain.sh (only needed for non-default manifest)
    manifest_flag = f' --manifest {manifest_filename}' if manifest_filename != 'build-order.yml' else ''
    # Chroot selection. GNOME 49 builds in build-chain.sh's default chroot,
    # but GNOME 50 has its own mock config (extra repos, tmpfs opts), and a
    # generated workflow that silently built in the wrong chroot would only
    # fail once a package needed one of those repos. The cache keys hash the
    # SELECTED config, not the default one, for the same reason.
    mock_flag = f' --mock-config {mock_config}' if mock_config else ''
    mock_cfg_file = f'mock/{mock_config}.cfg' if mock_config else 'mock/centos-stream-10-ci.cfg'

    for i, tier in enumerate(tiers):
        tier_name = tier['name']
        packages = [pkg['path'] for pkg in tier['packages'] if 'path' in pkg]
        
        build_job_name = f'build-{tier_name}'
        consolidate_job_name = f'consolidate-{tier_name}'
        repo_artifact_name = f'repo-{i+1}'
        
        # Build Job
        jobs[build_job_name] = {
            'needs': prev_consolidate_job,
            'runs-on': 'ubuntu-latest',
            'strategy': {
                'fail-fast': False,
                'matrix': {
                    'package': packages
                }
            },
            'steps': [
                {'name': 'Checkout', 'uses': 'actions/checkout@v4', **({'with': {'submodules': 'recursive'}} if submodules else {})},
                {'name': 'Install host dependencies', 'run': 'sudo apt-get update -q && sudo apt-get install -y -q podman createrepo-c rpm'},
                {'name': 'Cache CentOS Stream 10 image', 'uses': 'actions/cache@v4', 'with': {'path': '/tmp/cs10-image.tar', 'key': f"cs10-image-${{{{ hashFiles('{mock_cfg_file}') }}}}"}},
                {'name': 'Load or pull image', 'run': 'if [[ -f /tmp/cs10-image.tar ]]; then\n  podman load -i /tmp/cs10-image.tar\nelse\n  podman pull quay.io/centos/centos:stream10\n  podman save -o /tmp/cs10-image.tar quay.io/centos/centos:stream10\nfi\npodman pull ${{ env.MOCK_RUNNER_IMAGE }}\n'},
                {'name': 'Download previous repo', 'uses': 'actions/download-artifact@v4', 'with': {'name': prev_tier_repo, 'path': 'local-repo'}},
                {'name': 'Cache mock chroot (dnf downloads)', 'uses': 'actions/cache@v4', 'with': {'path': '.mock-cache', 'key': f"mock-cache-${{{{ matrix.package }}}}-${{{{ hashFiles('{mock_cfg_file}') }}}}-${{{{ github.run_id }}}}", 'restore-keys': f"mock-cache-${{{{ matrix.package }}}}-${{{{ hashFiles('{mock_cfg_file}') }}}}-\nmock-cache-${{{{ matrix.package }}}}-"}},
                {'name': 'Build package', 'env': {'MOCK_CACHE_DIR': '${{ github.workspace }}/.mock-cache'}, 'run': f'touch .build-marker\nARGS=(--backend podman --tier {tier_name} --package ${{{{ matrix.package }}}}{manifest_flag}{mock_flag})\nif [[ "${{{{ github.event.inputs.force }}}}" == "true" ]]; then\n  ARGS+=(--force)\nfi\n./scripts/build-chain.sh "${{ARGS[@]}}"\n'},
                {'name': 'Find new RPMs', 'id': 'find-rpms', 'run': 'mkdir -p new-rpms\nfind local-repo -name "*.rpm" -newer .build-marker -exec cp {} new-rpms/ \\;\ncount=$(ls -1 new-rpms/*.rpm 2>/dev/null | wc -l)\necho "count=$count" >> $GITHUB_OUTPUT\n'},
                {'name': 'Upload RPMs', 'if': "steps.find-rpms.outputs.count > '0'", 'uses': 'actions/upload-artifact@v4', 'with': {'name': f'rpms-{tier_name}-${{{{ strategy.job-index }}}}', 'path': 'new-rpms/*.rpm', 'retention-days': 1}}
            ]
        }
        
        # Consolidate Job
        jobs[consolidate_job_name] = {
            'needs': build_job_name,
            'runs-on': 'ubuntu-latest',
            'steps': [
                {'name': 'Install createrepo_c', 'run': 'sudo apt-get update -q && sudo apt-get install -y -q createrepo-c'},
                {'name': 'Download previous repo', 'uses': 'actions/download-artifact@v4', 'with': {'name': prev_tier_repo, 'path': 'local-repo'}},
                {'name': 'Download new RPMs', 'uses': 'actions/download-artifact@v4', 'continue-on-error': True, 'with': {'pattern': f'rpms-{tier_name}-*', 'path': 'local-repo', 'merge-multiple': True}},
                {'name': 'Update repo', 'run': 'createrepo_c --update local-repo'},
                {'name': 'Upload updated repo', 'uses': 'actions/upload-artifact@v4', 'with': {'name': repo_artifact_name, 'path': 'local-repo', 'retention-days': 1}}
            ]
        }
        
        prev_tier_repo = repo_artifact_name
        prev_consolidate_job = consolidate_job_name

    # Final Publish Job
    jobs['publish'] = {
        'needs': prev_consolidate_job,
        'runs-on': 'ubuntu-latest',
        'steps': [
            {'name': 'Checkout', 'uses': 'actions/checkout@v4'},
            {'name': 'Install dependencies', 'run': 'sudo apt-get update -q && sudo apt-get install -y -q rpm createrepo-c gpg gpgconf\ncurl -fsSL https://rclone.org/install.sh | sudo bash\n'},
            {'name': 'Download final repo', 'uses': 'actions/download-artifact@v4', 'with': {'name': prev_tier_repo, 'path': 'local-repo'}},
            {'name': 'Import GPG key', 'id': 'import-gpg', 'uses': 'crazy-max/ghaction-import-gpg@v6', 'with': {'gpg_private_key': '${{ secrets.GPG_PRIVATE_KEY }}', 'passphrase': '${{ secrets.GPG_PASSPHRASE }}', 'git_committer_name': 'RPM Builder', 'git_committer_email': 'rpm-signing@tunaos.org'}},
            {'name': 'Configure RPM macros', 'run': 'echo "%_signature gpg" > ~/.rpmmacros\necho "%_gpg_name ${{ steps.import-gpg.outputs.keyid }}" >> ~/.rpmmacros\necho "%__gpg_sign_cmd %{__gpg} gpg --batch --no-verbose --no-armor --use-agent --no-secmem-warning -u \\"%{_gpg_name}\\" -sbo %{__signature_filename} %{__plaintext_filename}" >> ~/.rpmmacros\n'},
            {'name': 'Sign RPMs', 'run': 'find local-repo -name "*.rpm" -exec rpmsign --addsign {} \\;\ncreaterepo_c --update local-repo\n'},
            {'name': 'Configure rclone', 'run': 'mkdir -p ~/.config/rclone\ncat > ~/.config/rclone/rclone.conf << EOF\n[r2]\ntype = s3\nprovider = Cloudflare\naccess_key_id = ${{ secrets.R2_ACCESS_KEY_ID }}\nsecret_access_key = ${{ secrets.R2_SECRET_ACCESS_KEY }}\nendpoint = https://${{ secrets.CLOUDFLARE_ACCOUNT_ID }}.r2.cloudflarestorage.com\nEOF\n'},
            {'name': 'Upload to R2', 'run': _build_upload_run(r2_path, secondary_r2_path, install_script, install_r2_dest)}
        ]
    }

    class IndentedDumper(yaml.Dumper):
        def increase_indent(self, flow=False, indentless=False):
            return super(IndentedDumper, self).increase_indent(flow, False)

    # Write yaml out without using standard aliases and formatting correctly
    with open(output_path, 'w') as f:
        yaml.dump(workflow, f, Dumper=IndentedDumper, default_flow_style=False, sort_keys=False, width=float("inf"))


def _build_upload_run(r2_path, secondary_r2_path, install_script, install_r2_dest):
    # Use just the last path component for the echo message
    label = r2_path.split('/')[-1]
    lines = [f'echo "Uploading to {label}..."',
             f'rclone sync local-repo/ "r2:${{R2_BUCKET}}/{r2_path}/"']
    if secondary_r2_path:
        label2 = secondary_r2_path.split('/')[-1]
        lines += [f'echo "Uploading to {label2}..."',
                  f'rclone sync local-repo/ "r2:${{R2_BUCKET}}/{secondary_r2_path}/"']
    lines += [f'rclone copyto public.gpg "r2:${{R2_BUCKET}}/public.gpg"',
              f'rclone copyto {install_script} "r2:${{R2_BUCKET}}/{install_r2_dest}"']
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Generate distributed build workflow from manifest')
    parser.add_argument('manifest', nargs='?',
                        default=os.path.join(os.path.dirname(__file__), '..', 'build-order.yml'),
                        help='Path to build-order YAML manifest')
    parser.add_argument('output', nargs='?',
                        default=os.path.join(os.path.dirname(__file__), '..', '.github', 'workflows', 'build-distributed.yml'),
                        help='Output workflow YAML path')
    parser.add_argument('--name', default='Distributed Build and Publish RPMs',
                        help='Workflow name')
    parser.add_argument('--r2-path', default='repo/10-stream-x86_64',
                        help='Primary R2 repo path (e.g. gnome49/10-stream-x86_64)')
    parser.add_argument('--secondary-r2-path', default='repo/10-x86_64',
                        help='Secondary R2 path (GNOME 50 only; set empty to disable)')
    parser.add_argument('--install-script', default='contrib/install.sh',
                        help='Install script to upload to R2')
    parser.add_argument('--install-r2-dest', default='install.sh',
                        help='R2 destination key for install script')
    parser.add_argument('--no-submodules', action='store_true',
                        help='Skip submodules: recursive in checkout steps')
    parser.add_argument('--mock-config', default=None,
                        help='Mock config name passed to build-chain.sh (e.g. centos-stream-10-ci-gnome50); also keys the image/chroot caches on that config file')
    args = parser.parse_args()
    secondary = args.secondary_r2_path if args.secondary_r2_path else None
    generate_workflow(args.manifest, args.output,
                      workflow_name=args.name,
                      r2_path=args.r2_path,
                      secondary_r2_path=secondary,
                      install_script=args.install_script,
                      install_r2_dest=args.install_r2_dest,
                      submodules=not args.no_submodules,
                      mock_config=args.mock_config)
    print(f"Generated {args.output}")
