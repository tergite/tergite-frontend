# Backends

This is documentation about how we manage the different backends that connect to MSS

## How to Add New BCC

- Start your [tergite-backend](https://github.com/tergite/tergite-backend) instance
- Copy the `mss-config.example.toml` to `mss-config.toml`.  
  Note: You could also create a new toml file based on `mss-config.example.toml`  
  and set the `MSS_CONFIG_FILE` environment variable to point to that file.
- Add the new client:

```toml
[[backends]]
# this name of the backend computer that will be accessible from tergite.qiskit and from webGUI
name = "simulator-arusha"
# the URL where this backend is running
url = "http://127.0.0.1:8002"
```

```shell
cp mss-config.example.toml mss-config.toml
```

- Update the values in the `mss-config.toml` file. It should have comments describing what each value signifies.

- Start your MSS

```shell
./start_mss
```

### FAQs

#### - How does the frontend know when the backend is offline?

Currently, there is no realtime monitoring of the status of the backend.
This is something we hope to implement in future.
