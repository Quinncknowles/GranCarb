# \# GranCarb

# 

# \*\*Description:\*\* Attempt at a modern recreation of Carbdose, the application used by the EPA to aid with Radon mitigation in the 1990s. Will use wxPython to match, as closely as possible, the original layout of the Carbdose program.

# 

# \*\*Antivirus Flags:\*\* Doing this in Python using PyInstaller to generate an executable means that the resulting executable file is lacking a "paid commercial code-signing certificate." Windows Defender and corporate antivirus scanners may flag it as a false positive. The codebase is entirely open source for review.

# 

# \## Goals

# 

# \- Recreate each Carbdose screen (User input, Waste disposal, X-Protocol, Cancer risks, Gamma radiation, Bq<->Ci calculator) as closely as possible to the original 1990s layout.

# \- Reproduce the original calculations wherever the underlying formulas can be confirmed, and clearly flag anything that's approximated or unverified until it can be checked against the original tool.

# \- Keep the codebase readable and open so radon mitigation professionals, regulators, or hobbyist reviewers can inspect exactly how a result was produced.

# \- Package as a standalone Windows executable via PyInstaller so the tool doesn't require a Python install to run.

# 

# \## Acknowledgements

# 

# \- The original \*\*Carbdose\*\* application and its underlying methodology, developed for the EPA in the 1990s to support radon mitigation via granular activated carbon (GAC) filtration.

# \- Built with \[wxPython](https://www.wxpython.org/).

# \- Packaged with \[PyInstaller](https://pyinstaller.org/).

# 

# \## License

# 

# Licensed under the \[Apache License 2.0](LICENSE).

