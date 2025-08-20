# Contributing to dtrust

Thanks for your interest in contributing! Contributions are welcome and appreciated.  
This document outlines how to set up the project, report issues, and submit changes.

---

## How to Contribute
There are many ways to help:
- Report bugs
- Suggest new features
- Improve documentation
- Submit code changes (fixes or enhancements)

---

## Reporting Issues
- Check the [issue tracker](https://github.com/keepittechie/dtrust/issues) to avoid duplicates.
- Provide as much detail as possible:
  - Steps to reproduce the bug
  - Expected vs. actual behavior
  - Your environment (OS, Python version, etc.)
- Use the appropriate label if possible.

---

## 🔧 Development Setup

### Requirements
- Python 3.9+
- `make` (for running helper commands)
- Git
- Recommended: a virtual environment (`venv` or `conda`)

### Setup Steps
```bash
# 1. Clone the repo
git clone git@github.com:keepittechie/dtrust.git
cd dtrust

# 2. (Optional) Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # On Linux/Mac
.venv\Scripts\activate      # On Windows

# 3. Install dependencies (if any are added later)
pip install -r requirements.txt
````

---

## Running the Project

```bash
# Run a Tier 2 scan
python3 dtrust_cli.py --tier 2 --rootfs / --out build/tier2.json --max-seconds 20

# Validate report
python3 scripts/validate.py build/tier2.json

# Score report
python3 score-dtrust-report.py build/tier2.json > build/tier2.score.json

# Render HTML
python3 render_pretty.py --in build/tier2.json --out build/tier2_pretty.html --score build/tier2.score.json
```

Or use:

```bash
make
```

to build reports using the default Makefile targets.

---

## Coding Guidelines

* Follow [PEP8](https://peps.python.org/pep-0008/) style.
* Use clear, descriptive commit messages.
* Write docstrings for new functions.
* Keep changes small and focused.

---

## Pull Requests

1. **Fork** the repository.
2. **Create a branch**:

   ```bash
   git checkout -b feature/my-new-feature
   ```
3. **Make changes** and commit them:

   ```bash
   git commit -m "Add support for XYZ"
   ```
4. **Push to your fork** and open a PR:

   ```bash
   git push origin feature/my-new-feature
   ```
5. Describe your changes clearly in the PR.

---

## Code of Conduct

By participating, you agree to follow our [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Acknowledgments

Thank you for helping make **dtrust** better!

```
