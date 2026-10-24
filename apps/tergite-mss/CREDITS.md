# Credits

## Miroslav Dobsicek

The first version of the tergite-mss

## Chalmers University of Technology Bachelors Project

Title: "Constructing a Modular System for Storing and Serving Data from Quantum Computers"
Supervisors: 

- **Miroslav Dobsicek**
- **Sandro Stucki**

Students:

- **Simon Genne**
- **Arvid Holmqvist**
- **Bashar Oumari**
- **Jakob Ristner**
- **Björn Rosengren**
- **Jakob Wik**

Integration to tergite:

- **Abdullah-Al Amin**
- **Nicklas Botö**
- **Fabian Forslund**

## Martin Ahindura

Added the Authentication/Authorization/Accounting features

- Authentication via JWT tokens in cookies
- Authentication via JWT tokens in Authorization header
- Role-based authorization via JWT tokens
- Project-based authorization via app tokens saved in the database
- Project-based tracking of QPU usage in terms of durations of experiments
- Integration with [Puhuri HPC/cloud allocation service](https://puhuri.io/)
- Secure connections between backend and frontend via websockets

Added integration test suite plus CI/CD
Implemented version v2 of the API

## Adilet Tuleouv

Implemented parts of version v2 of the API

## fastapi-users

`libs/authlib` began as a copy of [fastapi-users](https://github.com/fastapi-users/fastapi-users)
14.0.2 by François Voron, used under the MIT licence kept in `libs/authlib/LICENSE`.
