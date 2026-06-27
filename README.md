# TeamPulse

A team task management API built with FastAPI and PostgreSQL.

## Overview

TeamPulse powers a project dashboard used by ~200 engineering teams internally. The API serves:
- Task CRUD and assignment
- Sprint board views with filters
- Team analytics dashboard (velocity, burndown, cycle time)
- Notification service for overdue tasks

## Tech Stack
- **Backend:** Python 3.12 / FastAPI
- **Database:** PostgreSQL 15 with SQLAlchemy ORM
- **Cache:** None currently (this is the problem)
- **Auth:** JWT via middleware
- **Deployment:** Docker + Kubernetes on AWS EKS

## Known Issues
- **Dashboard load time is 4–8 seconds** on teams with >500 tasks — the #1 user complaint
- The analytics queries join 4 tables and run expensive aggregations on every page load
- No caching layer exists; every request hits the DB directly
- The `GET /api/dashboard/{team_id}` endpoint is the bottleneck
