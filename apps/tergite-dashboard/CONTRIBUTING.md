# Contributing to tergite-dashboard

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
are looked at. Please get in touch via email <quantum.nextlabs@chalmers.se> instead.

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
same [Apache 2.0 License](./LICENSE) that covers the project. Feel free to contact the maintainers if that's a concern.

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

- Make sure you have [nodejs +20.12](https://nodejs.org/) installed.
- Clone the repo and enter its root folder

```shell
git clone git@github.com:tergite/tergite-frontend.git
cd tergite-frontend/apps/tergite-dashboard
```

- Install the dependencies

```shell
npm i
```

- Run the tests command

```shell
npm run test
```

## How to Run End-to-end Tests

- Ensure you have [docker](https://docs.docker.com/engine/install/) and [jq](https://jqlang.org/download/) installed
- If you will not supply the `PLAYWRIGHT_IMAGE` argument, you need [nodejs](https://nodejs.org/en) installed also.
- Ensure nothing is running on ports:

  - 27018
  - 8000
  - 8002
  - 8001
  - 6378

- Clone the repo

```shell
git clone git@github.com:tergite/tergite-frontend.git
cd tergite-frontend
```

- Run the tests command

```shell
BACKEND_REPO="https://github.com/tergite/tergite-backend.git" \
# BACKEND_BRANCH="main" \ # you can set a different backend branch; default is 'main'
# DEBUG="True" \ # Set 'True' to avoid cleaning up the containers, env, and repos after test, default: ''
# CLEAN="True" \ # Set 'True' to also remove the stack's images and the build cache, before and after, default: ''
# VISUAL="True" \ # Set 'True' to run the e2e in Playwright's UI mode, default: ''
# PLAYWRIGHT_IMAGE="mcr.microsoft.com/playwright:v1.64.0-noble" \ # Set the docker image to run the tests. If not provided, it runs on the host machine
#   OPENID_CONFIG_URL="https://samples.auth0.com/.well-known/openid-configuration" \ # Set the url to get the openID config for mock OpenID connect, default: 'https://samples.auth0.com/.well-known/openid-configuration'
#   OPENID_CLIENT_ID="kbyuFDidLLm280LIwVFiazOqjO3ty8KH" \ # Set the client id for mock OpenID connect, default: 'kbyuFDidLLm280LIwVFiazOqjO3ty8KH'
#   OPENID_CLIENT_SECRET="60Op4HFM0I8ajz0WdiStAbziZ-VFQttXuxixHHs2R7r7-CW8GR79l-mmLqMhc-Sa" \ # Set the client secret for mock OpenID connect, default: '60Op4HFM0I8ajz0WdiStAbziZ-VFQttXuxixHHs2R7r7-CW8GR79l-mmLqMhc-Sa'
#   OPENID_AUTH_URL="https://samples.auth0.com/authorize" \ # Set the url to redirect to for auth for mock OpenID connect, default: 'https://samples.auth0.com/authorize'
./dev/e2e_test.sh
```

## How to Build

- Make sure you have [nodejs +20.12](https://nodejs.org/) installed.
- Clone the repo and enter its root folder

```shell
git clone git@github.com:tergite/tergite-frontend.git
cd tergite-frontend/apps/tergite-dashboard
```

- Install the dependencies

```shell
npm i
```

- To Build for production, run:

```shell
npm run build
```

- Obtain the built files in the [`/dist`](./dist) folder

## How to Generate Snapshots for CI

Playwright names each screenshot baseline after the platform (`-chromium-darwin.png`,
`-chromium-linux.png`), so CI on linux needs the linux ones beside those made on a mac. Generate
them in Playwright's own linux image, which has the browsers:

- Make sure you have [docker](https://docs.docker.com/engine/install/) installed.

- Clone the repo and enter its root folder

```shell
git clone git@github.com:tergite/tergite-frontend.git
cd apps/tergite-dashboard
```

- Generate the image `tergite-dashboard-playwright`

```shell
docker build -t tergite-dashboard-playwright:latest -f Dockerfile.playwright .
```

- Run the suite in it, with the specs' folder mounted so that the new baselines land in it

```shell
docker run --rm -v ./playwright:/app/playwright tergite-dashboard-playwright:latest
```

- The new baselines are the `-chromium-linux.png` files in the `playwright/*-snapshots/` folders;
  commit them if anything has changed

```shell
git add playwright
git commit -m "Updated the baseline snapshots for end-to-end tests"
```

## References

This document was adapted from [a gist by Brian A. Danielak](https://gist.github.com/briandk/3d2e8b3ec8daf5a27a62) which
was originally adapted from the open-source contribution guidelines
for [Facebook's Draft](https://github.com/facebook/draft-js/blob/a9316a723f9e918afde44dea68b5f9f39b7d9b00/CONTRIBUTING.md)
