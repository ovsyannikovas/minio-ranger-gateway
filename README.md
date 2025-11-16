# MinIO-Ranger Gateway

A proxy service that acts as a gateway for accessing MinIO object storage. Gateway implements Apache Ranger-based security policy verification, providing access control, auditing, and compliance with corporate security standards.

## Overview

MinIO does not have native integration with Apache Ranger. This gateway service sits between clients and MinIO, checking every operation through Apache Ranger for authorization.

## Architecture

```
Client → Gateway (FastAPI) → MinIO
           ↓
      Apache Ranger (policy check)
```

## Features

- ✅ **Ranger Integration**: Custom service definition for MinIO in Apache Ranger
- ✅ **Local Policy Checking**: Loads policies from Ranger and checks them locally (like native plugins)
- ✅ **Policy Caching**: Policies cached in memory, refreshed periodically (5 min default)
- ✅ **Result Caching**: TTL-based cache for authorization results (5 min default)
- ✅ **S3 API Compatibility**: Proxies S3 requests to MinIO transparently
- ✅ **Authorization**: Checks policies locally before allowing operations
- ✅ **Audit Logging**: Logs all authorized operations for compliance
- ✅ **Background Policy Loader**: Automatically refreshes policies from Ranger

## Documentation

- [Architecture](docs/ARCHITECTURE.md) - System architecture and design
- [Ranger Setup](docs/RANGER_SETUP.md) - How to create custom service in Ranger
- [MinIO Authorization](docs/MINIO_AUTHORIZATION.md) - MinIO authorization mechanisms
- [Policy Parsing](docs/POLICY_PARSING.md) - How policies are parsed and checked locally
- [Caching](docs/CACHING.md) - Policy caching strategy
- [Implementation](docs/IMPLEMENTATION.md) - Current implementation status

## Quick Start

### 1. Start All Services

```bash
docker-compose up -d
```

This starts:
- **Apache Ranger**: zookeeper, solr, db, admin (port 6080)
- **MinIO**: object storage (ports 9000, 9001)
- **Gateway**: FastAPI proxy (port 8000)

Wait for services to be ready (Ranger takes 2-3 minutes on first start):

```bash
docker-compose ps
```

### 2. Create Ranger Service

```bash
make setup-minio-ranger
```

This creates:
- Service definition (`minio-service-def`)
- Service instance (`minio-service`)
- Sample policies

### 3. Test Gateway

```bash
# Health check
curl http://localhost:8000/api/v1/utils/health-check/

# Test request (requires policy in Ranger)
curl -H "X-User: user1" http://localhost:8000/analytics/
```

Gateway is now running and ready to proxy requests to MinIO with Ranger authorization!

## Usage

### Test with curl

```bash
# List bucket (user groups loaded automatically from Ranger)
curl -H "X-User: user1" http://localhost:8000/analytics/

# Get object
curl -H "X-User: user1" http://localhost:8000/analytics/data/file.csv

# Put object
curl -X PUT -H "X-User: user1" \
     --data-binary @file.txt \
     http://localhost:8000/analytics/data/file.txt
```

**Note**: Gateway automatically gets user groups from Ranger UserSync. You can use `X-User-Groups` header as fallback if Ranger is unavailable.

### Configuration

Environment variables (in `.env` or `docker-compose.yml`):

```env
# Ranger
RANGER_HOST=http://ranger:6080
RANGER_USER=admin
RANGER_PASSWORD=rangerR0cks!
RANGER_SERVICE_NAME=minio-service
RANGER_CACHE_TTL=300

# MinIO
MINIO_ENDPOINT=http://minio:9000
MINIO_ROOT_USER=admin
MINIO_ROOT_PASSWORD=password
```

## Project Structure

```
.
├── docs/                    # Documentation
├── ranger-requests/         # Ranger service definitions and policies
│   ├── servicedef.json
│   ├── service.json
│   └── policies/
├── full-stack-fastapi-template/
│   └── backend/
│       └── app/
│           ├── gateway/    # Gateway modules
│           │   ├── ranger_client.py    # Fetches policies from Ranger
│           │   ├── policy_parser.py    # Local policy checking
│           │   ├── policy_loader.py   # Background policy loader
│           │   ├── cache.py           # Policy and result caching
│           │   └── authorizer.py      # Authorization logic
│           └── api/routes/
│               └── gateway.py
└── docker-compose.yml      # Ranger + MinIO services
```

## TODO

- [ ] Implement AWS Signature v4 authentication
- [ ] Add comprehensive tests
- [ ] Improve error handling with S3-compatible error codes
- [ ] Add metrics and monitoring
- [ ] Optimize performance (connection pooling, batch checks)

## License

MIT
