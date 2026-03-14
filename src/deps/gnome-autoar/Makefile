# Used by COPR's make_srpm build method.
# Downloads sources from the URLs in the spec file, then builds an SRPM.
srpm:
	spectool -g *.spec
	rpmbuild -bs *.spec \
		--define "_srcrpmdir $(CURDIR)" \
		--define "_sourcedir $(CURDIR)"
