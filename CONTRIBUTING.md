# Contributing to tergite-frontend

**This project is currently not accepting pull requests from the general public yet.**

**It is currently being developed by the core developers only.**

We love your input! We want to make contributing to this project as easy and transparent as possible, whether it's:

- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features
- Becoming a maintainer

## Government Model

[Chalmers Next Labs AB (CNL)](https://chalmersnextlabs.se) manages and maintains this project on behalf of all contributors.

## Version Control

Tergite is developed on a separate version control system and mirrored on Github.
If you are reading this on GitHub, then you are looking at a mirror.

## Versioning

When versioning we follow the format `{year}.{month}.{patch_number}` e.g. `2023.12.0`.

## Contacting the Tergite Developers

Since the Github repositories are only mirrors, no Github pull requests or Github issue/bug reports
are looked. Please get in touch via email <quantum.nextlabs@chalmers.se> instead.

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

All signed CLAs are emails to us at <contact.quantum@chalmersnextlabs.se>.

## How to Test

- Make sure you have [conda](https://docs.anaconda.com/free/miniconda/index.html) installed, and
  [nodejs +20.12](https://nodejs.org/) for the dashboard in `ui/`.
- Clone the repo and enter its root folder

```shell
git clone git@github.com:tergite/tergite-frontend.git
cd tergite-frontend
```

- Create the conda environment, and install MSS's dependencies

```shell
conda create -n mss python=3.13
conda activate mss
pip install ."[dev]"
```

- Run MSS's tests, which need the MongoDB and Redis that `tests/fixtures/config.test.toml` names,
  and the PostgreSQL that `TEST_POSTGRES_URL` does

```shell
pytest
```

- Install the dashboard's dependencies, and run its tests

```shell
cd ui
npm i
npm run test
```

## How to Run End-to-end Tests

- Ensure you have [nodejs](https://nodejs.org/en), [uv](https://docs.astral.sh/uv/), MongoDB's
  `mongod` and `mongosh`, `redis-server` and `sqlite3` installed
- Ensure nothing is running on ports 3001, 8002, 8101, 27018 and 6380
- Clone the repo, and tergite-backend beside it unless `BACKEND_REPO` is given

```shell
git clone git@github.com:tergite/tergite-frontend.git
cd tergite-frontend
```

- Run the tests command

```shell
BACKEND_PATH="../tergite-backend" \
# BACKEND_REPO="https://github.com/tergite/tergite-backend.git" \ # cloned when BACKEND_PATH is not set
# BACKEND_BRANCH="main" \ # the branch of BACKEND_REPO to clone; default is 'main'
# DEBUG="True" \ # Set 'True' to keep the services running and temp-native/ after the tests, default: ''
# VISUAL="True" \ # Set 'True' to run the e2e in Playwright's UI mode, default: ''
./dev/e2e_native_test.sh
```

- It seeds MSS's database from [ui/fixtures/](./ui/fixtures), serves the dashboard's test build
  from MSS at `/ui`, and passes its arguments to `playwright test`, e.g. a spec to run alone:

```shell
BACKEND_PATH="../tergite-backend" ./dev/e2e_native_test.sh playwright/home.spec.ts
```

## How to Build

- Follow the first three steps of [How to Test](#how-to-test)
- Build the dashboard in `ui/` into `ui/dist`, which the build includes for MSS to serve at `/ui`

```shell
(cd ui && npm ci && npm run build)
```

- Build the main.py file with [Nuitka](https://nuitka.net/)

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

## How to Generate Snapshots for CI

Playwright names each screenshot baseline after the platform (`-chromium-darwin.png`,
`-chromium-linux.png`), so CI on linux needs the linux ones beside those made on a mac. Generate
them with the e2e stack in Playwright's own linux image, which has the browsers:

- Make sure you have [docker](https://docs.docker.com/engine/install/) installed.

- Clone the repo, and tergite-backend beside it, and enter the repo's root folder

```shell
git clone git@github.com:tergite/tergite-frontend.git
cd tergite-frontend
```

- Generate the image `tergite-dashboard-playwright`, with the repo's root as the context

```shell
docker build -t tergite-dashboard-playwright:latest -f ui/Dockerfile.playwright .
```

- Run the suite in it, with the backend and the specs' folder mounted, so that the new baselines
  land in it

```shell
docker run --rm -v "$PWD/../tergite-backend:/backend" -e BACKEND_PATH=/backend \
  -v "$PWD/ui/playwright:/repo/ui/playwright" \
  tergite-dashboard-playwright:latest
```

- The new baselines are the `-chromium-linux.png` files in the `ui/playwright/*-snapshots/`
  folders; commit them if anything has changed

```shell
git add ui/playwright
git commit -m "Updated the baseline snapshots for end-to-end tests"
```

## References

This document was adapted from [a gist by Brian A. Danielak](https://gist.github.com/briandk/3d2e8b3ec8daf5a27a62) which
was originally adapted from
the open-source contribution guidelines
for [Facebook's Draft](https://github.com/facebook/draft-js/blob/a9316a723f9e918afde44dea68b5f9f39b7d9b00/CONTRIBUTING.md)
