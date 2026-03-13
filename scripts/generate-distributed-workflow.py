#!/usr/bin/env python3
import yaml
import sys
import os

def generate_workflow(manifest_path, output_path):
    with open(manifest_path, 'r') as f:
        manifest = yaml.safe_load(f)

    tiers = manifest.get('tiers', [])
    
    workflow = {
        'name': 'Distributed Build and Publish RPMs',
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
            {'name': 'Seed local repo from R2', 'run': 'mkdir -p local-repo\necho "Downloading existing repo from R2..."\nrclone sync "r2:${R2_BUCKET}/repo/10-stream-x86_64/" "local-repo/" --exclude "repodata/**" || true\ncreaterepo_c local-repo\n'},
            {'name': 'Upload initial repo', 'uses': 'actions/upload-artifact@v4', 'with': {'name': 'repo-0', 'path': 'local-repo', 'retention-days': 1}}
        ]
    }
    
    prev_tier_repo = 'repo-0'
    prev_consolidate_job = 'seed-repo'
    
    for i, tier in enumerate(tiers):
        tier_name = tier['name']
        packages = [pkg['path'] for pkg in tier['packages']]
        
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
                {'name': 'Checkout', 'uses': 'actions/checkout@v4', 'with': {'submodules': 'recursive'}},
                {'name': 'Install host dependencies', 'run': 'sudo apt-get update -q && sudo apt-get install -y -q podman createrepo-c rpm'},
                {'name': 'Cache CentOS Stream 10 image', 'uses': 'actions/cache@v4', 'with': {'path': '/tmp/cs10-image.tar', 'key': "cs10-image-${{ hashFiles('mock/centos-stream-10-ci.cfg') }}"}},
                {'name': 'Load or pull image', 'run': 'if [[ -f /tmp/cs10-image.tar ]]; then\n  podman load -i /tmp/cs10-image.tar\nelse\n  podman pull quay.io/centos/centos:stream10\n  podman save -o /tmp/cs10-image.tar quay.io/centos/centos:stream10\nfi\npodman pull ${{ env.MOCK_RUNNER_IMAGE }}\n'},
                {'name': 'Download previous repo', 'uses': 'actions/download-artifact@v4', 'with': {'name': prev_tier_repo, 'path': 'local-repo'}},
                {'name': 'Build package', 'run': 'touch .build-marker\nARGS=(--backend podman --package ${{ matrix.package }})\nif [[ "${{ github.event.inputs.force }}" == "true" ]]; then\n  ARGS+=(--force)\nfi\n./scripts/build-chain.sh "${ARGS[@]}"\n'},
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
            {'name': 'Import GPG key', 'uses': 'crazy-max/ghaction-import-gpg@v6', 'with': {'gpg_private_key': '${{ secrets.GPG_PRIVATE_KEY }}', 'passphrase': '${{ secrets.GPG_PASSPHRASE }}', 'git_committer_name': 'RPM Builder', 'git_committer_email': 'rpm-signing@tunaos.org'}},
            {'name': 'Sign RPMs', 'run': 'find local-repo -name "*.rpm" -exec rpmsign --addsign {} \\;\ncreaterepo_c --update local-repo\n'},
            {'name': 'Configure rclone', 'run': 'mkdir -p ~/.config/rclone\ncat > ~/.config/rclone/rclone.conf << EOF\n[r2]\ntype = s3\nprovider = Cloudflare\naccess_key_id = ${{ secrets.R2_ACCESS_KEY_ID }}\nsecret_access_key = ${{ secrets.R2_SECRET_ACCESS_KEY }}\nendpoint = https://${{ secrets.CLOUDFLARE_ACCOUNT_ID }}.r2.cloudflarestorage.com\nEOF\n'},
            {'name': 'Upload to R2', 'run': 'echo "Uploading to 10-stream-x86_64..."\nrclone sync local-repo/ "r2:${R2_BUCKET}/repo/10-stream-x86_64/"\necho "Uploading to 10-x86_64..."\nrclone sync local-repo/ "r2:${R2_BUCKET}/repo/10-x86_64/"\nrclone copyto public.gpg "r2:${R2_BUCKET}/public.gpg"\n'}
        ]
    }

    # Write yaml out without using standard aliases and formatting correctly
    with open(output_path, 'w') as f:
        yaml.dump(workflow, f, default_flow_style=False, sort_keys=False, width=float("inf"))

if __name__ == '__main__':
    manifest = os.path.join(os.path.dirname(__file__), '..', 'build-order.yml')
    output = os.path.join(os.path.dirname(__file__), '..', '.github', 'workflows', 'build-distributed.yml')
    generate_workflow(manifest, output)
    print(f"Generated {output}")
