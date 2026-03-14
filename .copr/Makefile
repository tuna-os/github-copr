# COPR make_srpm hook. Called as:
#   make -f .copr/Makefile srpm outdir=<path> spec=<path/to/pkg.spec>
#
# Downloads all SourceN URLs from the spec, then builds the SRPM.
# Uses curl (spectool is not available in all COPR SRPM builder environments).
srpm:
	@set -e; \
	SPECDIR="$(dir $(spec))"; \
	echo "Downloading sources for $(spec) into $$SPECDIR"; \
	rpmspec -q --qf "%{SOURCE0}\n%{SOURCE1}\n%{SOURCE2}\n%{SOURCE3}\n%{SOURCE4}\n" "$(spec)" 2>/dev/null \
	  | grep -E '^https?://' \
	  | while read url; do \
	      fname=$$(basename "$$url"); \
	      if [ ! -f "$$SPECDIR/$$fname" ]; then \
	        echo "  Downloading $$url"; \
	        curl -fLo "$$SPECDIR/$$fname" "$$url"; \
	      else \
	        echo "  Already present: $$fname"; \
	      fi; \
	    done
	rpmbuild -bs "$(spec)" \
		--define "_srcrpmdir $(outdir)" \
		--define "_sourcedir $(dir $(spec))"
