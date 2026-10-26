# Contributing to tergite-mss

**This project is currently not accepting pull requests from the general public yet.**

**It is currently being developed by the core developers only.**

## Government Model

[Chalmers Next Labs AB (CNL)](https://chalmersnextlabs.se) manages and maintains this project on behalf of all contributors.

## Version Control

Tergite is developed on a separate version control system and mirrored on Github.
If you are reading this on GitHub, then you are looking at a mirror.

## Versioning

When versioning we follow the format `{year}.{month}.{patch_number}` e.g. `2023.12.0`.

## Contacting the Tergite Developers

Since the Github repositories are only mirrors, no Github pull requests or Github issue/bug reports
are looked at. Please get in touch via email <contact.quantum@chalmersnextlabs.se> instead.

Take note that the maintainers may not answer every email.

## But We Use [Github Flow](https://docs.github.com/en/get-started/quickstart/github-flow), So All Code Changes Happen Through Pull Requests

Pull requests are the best way to propose changes to the codebase (we
use [Github Flow](https://docs.github.com/en/get-started/quickstart/github-flow)). We actively welcome your pull
requests:

1. Clone the repo and create your branch from `main`.
2. If you've added code that should be tested, add tests.
3. If you've changed APIs, update the documentation.
4. Ensure the test suite passes.
5. Make sure your code lints.
6. Issue that pull request!

## Any contributions you make will be under the Apache 2.0 Software Licenses

In short, when you submit code changes, your submissions are understood to be under the
same [Apache 2.0 License](./LICENSE.txt) that covers the project. Feel free to contact the maintainers if that's a concern.

## Write bug reports with detail, background, and sample code

[This is an example](http://stackoverflow.com/q/12488905/180626).
Here's [another example from Craig Hockenberry](http://www.openradar.me/11905408).

**Great Bug Reports** tend to have:

- A quick summary and/or background
- Steps to reproduce
  - Be specific!
  - Give sample code if you can.
- What you expected would happen
- What actually happens
- Notes (possibly including why you think this might be happening, or stuff you tried that didn't work)

People _love_ thorough bug reports. I'm not even kidding.

## License

By contributing, you agree that your contributions will be licensed under its Apache 2.0 License.

## Contributor Licensing Agreement

Before you can submit any code, all contributors must sign a
contributor license agreement (CLA). By signing a CLA, you're attesting
that you are the author of the contribution, and that you're freely
contributing it under the terms of the Apache-2.0 license.

The [individual CLA](https://tergite.github.io/contributing/icla.pdf) document is available for review as a PDF.

Please note that if your contribution is part of your employment or
your contribution is the property of your employer,
you will also most likely need to sign a [corporate CLA](https://tergite.github.io/contributing/ccla.pdf).

All signed CLAs are emails to us at <contact@quantum.chalmersnextlabs.se>.

## How to Test

- Make sure you have [conda](https://docs.anaconda.com/free/miniconda/index.html) installed.
- Clone the repo and enter its root folder

```shell
git clone git@github.com:tergite/tergite-frontend.git
cd tergite-frontend/apps/tergite-mss
```

- Create the conda environment

```shell
conda create -n mss python=3.12
```

- Install dependencies

```shell
conda activate mss
pip install ."[dev]"
```

- Run the tests commands

```shell
pytest
```

## Build Executable with [Nuitka](https://nuitka.net/)

- Make sure you have [conda](https://docs.anaconda.com/free/miniconda/index.html) installed.
- Clone the repo and enter its root folder

```shell
git clone git@github.com:tergite/tergite-frontend.git
cd tergite-frontend/apps/tergite-mss
```

- Create the conda environment

```shell
conda create -n mss python=3.12
```

- Install dependencies

```shell
conda activate mss
pip install ."[dev]"
```

- Build the dashboard in `ui/` into `ui/dist`, which the build includes for MSS to serve at `/ui`

```shell
(cd ui && npm ci && npm run build)
```

- Build the main.py file

```shell
python -m nuitka main.py
```

- After the build, the app will be at `main.dist/mss`, a folder that must stay whole. You can run it.

```shell
# create the mss-config.toml
cp mss-config.example.toml mss-config.toml
# create the mss private key
openssl genpkey -algorithm RSA -out private-mss-key.pem -pkeyopt rsa_keygen_bits:4096 -aes-256-cbc
# migrate the database, MongoDB or SQL, and run the app, with any of `--port`, `--host`,
# `--forwarded-allow-ips`, `--workers` and `--reload`; `main.dist/mss migrate` or `main.dist/mss serve` does one alone
MSS_CONFIG_FILE="$PWD/mss-config.toml" PRIVATE_KEY_FILE="$PWD/private-mss-key.pem" main.dist/mss start --port 8002
```

## References

This document was adapted from [a gist by Brian A. Danielak](https://gist.github.com/briandk/3d2e8b3ec8daf5a27a62) which
was originally adapted from the open-source contribution guidelines
for [Facebook's Draft](https://github.com/facebook/draft-js/blob/a9316a723f9e918afde44dea68b5f9f39b7d9b00/CONTRIBUTING.md)
