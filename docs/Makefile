# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line.
SPHINXOPTS    =
SPHINXBUILD   = sphinx-build
SPHINXPROJ    = UniFlex
SOURCEDIR     = .
BUILDDIR      = _build

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

gh-pages: COMMIT = $(shell git rev-parse HEAD)
gh-pages: clean html
	git checkout gh-pages
	cd ..; git rm -r .
	cd ..; git checkout $(COMMIT) -- .gitignore README.md LICENSE
	cd ..; cp -r docs/_build/html/. .
	cd ..; git stage .
	cd ..; git commit -m 'autodoc commit for $(COMMIT)'
	git checkout master

.PHONY: help Makefile

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
