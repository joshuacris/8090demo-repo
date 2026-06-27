# Vault API

A personal notes & secrets storage service built with FastAPI + PostgreSQL.

## Overview

Vault lets users store private notes (passwords, API keys, personal info). Notes are
encrypted at rest and scoped to the user who created them.

## Tech Stack
- **Backend:** Python 3.12 / FastAPI
- **Database:** PostgreSQL 15 with SQLAlchemy ORM
- **Auth:** _none yet — see open PRs_

## Status
- ✅ Note CRUD (create / read / update / delete)
- ⬜ **Authentication** — currently every request is anonymous and notes aren't scoped to a
  real user. This is the next big piece (see PR X) and the two competing follow-ups for how
  to handle sessions (PR Y vs PR Z).

## Endpoints
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/notes` | Create a note |
| `GET` | `/api/notes/{id}` | Get a note |
| `GET` | `/api/notes` | List notes |
| `PUT` | `/api/notes/{id}` | Update a note |
| `DELETE` | `/api/notes/{id}` | Delete a note |
