# Tergite MSS

![CI](https://github.com/tergite/tergite-frontend/actions/workflows/mss-ci.yml/badge.svg)

The Main Service Server (MSS) or the Public API in the [Tergite software stack](https://tergite.github.io/) of the WACQT quantum computer.

**This project is developed by a core group of collaborators.**  
**Chalmers Next Labs AB (CNL) takes on the role of managing and maintaining this project.**

## Version Control

The tergite stack is developed on a separate version control system and mirrored on Github.
If you are reading this on GitHub, then you are looking at a mirror.

## Dependencies

- [Python 3.8](https://www.python.org/)
- [MongoDb](https://www.mongodb.com/)
- [Tergite Backend](https://github.com/tergite/tergite-backend)

## Quick Start

- Ensure you have [conda](https://docs.anaconda.com/free/miniconda/index.html) installed.
  (_You could simply have python +3.8 installed instead._)
- Ensure you have [tergite backend](https://github.com/tergite/tergite-backend) running.
- Clone the repo

```shell
git clone git@github.com:tergite/tergite-frontend.git
```

- Create conda environment

```shell
conda create -n mss -y python=3.12
conda activate mss
```

- Install dependencies

```shell
cd tergite-frontend/apps/tergite-mss
pip install -e .
```

- Copy the `mss-config.example.toml` file to `mss-config.toml` and
  update the variables there appropriately.

```shell
cp mss-config.example.toml mss-config.toml
```

- If you don't have a key certificate pair for MSS, generate them
  and copy the public key certificate to the backend machine in the tergite-backend folder.

```shell
openssl genpkey -algorithm RSA -out mss_private_key.pem -pkeyopt rsa_keygen_bits:4096
openssl rsa -pubout -in mss_private_key.pem -out mss_public_key.pem
# scp mss_public_key.pem backend-host:~/tergite-backend/mss_public_key.pem
```

_Note: You can change the path where this private key file is found by
setting the `PRIVATE_KEY_FILE` environment variable._

- Run start script

```shell
./start_mss.sh
```

- Open your browser at [http://localhost:8002/docs](http://localhost:8002/docs) to see the interactive API docs

## Documentation

Find more documentation in the [docs folder](./docs)

## Contribution Guidelines

If you would like to contribute, please have a look at our
[contribution guidelines](./CONTRIBUTING.md)

## Authors

This project is a work of
[many contributors](https://github.com/tergite/tergite-frontend/graphs/contributors).

Special credit goes to the authors of this project as seen in the [CREDITS](./CREDITS.md) file.

## ChangeLog

To view the changelog for each version, have a look at
the [CHANGELOG.md](./CHANGELOG.md) file.

## License

[Apache 2.0 License](./LICENSE.txt)

## Acknowledgements

This project was sponsored by:

- [Knut and Alice Wallenberg Foundation](https://kaw.wallenberg.org/en) under the [Wallenberg Center for Quantum Technology (WACQT)](https://www.chalmers.se/en/centres/wacqt/) project at [Chalmers University of Technology](https://www.chalmers.se)
- [Nordic e-Infrastructure Collaboration (NeIC)](https://neic.no) and [NordForsk](https://www.nordforsk.org/sv) under the [NordIQuEst](https://neic.no/nordiquest/) project
- [European Union's Horizon Europe](https://research-and-innovation.ec.europa.eu/funding/funding-opportunities/funding-programmes-and-open-calls/horizon-europe_en) under the [OpenSuperQ](https://cordis.europa.eu/project/id/820363) project
- [European Union's Horizon Europe](https://research-and-innovation.ec.europa.eu/funding/funding-opportunities/funding-programmes-and-open-calls/horizon-europe_en) under the [OpenSuperQPlus](https://opensuperqplus.eu/) project
