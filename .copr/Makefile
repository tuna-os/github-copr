# COPR make_srpm hook. Called as:
#   make -f .copr/Makefile srpm outdir=<path> spec=<path/to/pkg.spec>
srpm:
	spectool -g -C $(dir $(spec)) $(spec)
	rpmbuild -bs $(spec) \
		--define "_srcrpmdir $(outdir)" \
		--define "_sourcedir $(dir $(spec))"
