# Candidate Test Cases

- Input digest: `3eb49b8e753c2ede40c791542993b29df12495ef984efd8eb2b69c63af07ffbd`
- Candidates: `18`

> These are candidates only. They are not approved for production or direct execution.

## case-092997d04a58b9b5 - GET /auth/session - 请求可达性
- status: `AUTOMATABLE`; risk: `readonly`; type: `api`
- environments: `production-like, isolated`
- evidence: `ev-6066b704592cb178`
- human confirmation: confirm status codes and business assertions

### Steps

1. `apiClient` GET `env.api('/auth/session' )`

### Expected


## case-5249ab65fb148018 - GET /auth/session - 未认证访问
- status: `DRAFT`; risk: `readonly`; type: `api`
- environments: `production-like, isolated`
- evidence: `ev-6066b704592cb178`
- human confirmation: confirm status codes and business assertions

### Steps

1. `anonClient` GET `env.api('/auth/session' )`

### Expected

- documented unauthenticated status

## case-5dafc9e8ce95a39b - GET /quality-gates - 请求可达性
- status: `AUTOMATABLE`; risk: `readonly`; type: `api`
- environments: `production-like, isolated`
- evidence: `ev-aeaf63539eabc42d`
- human confirmation: confirm status codes and business assertions

### Steps

1. `apiClient` GET `env.api('/quality-gates' )`

### Expected


## case-69fd9ecc32cb9079 - GET /quality-gates - 响应结构
- status: `DRAFT`; risk: `readonly`; type: `api`
- environments: `production-like, isolated`
- evidence: `ev-aeaf63539eabc42d`
- human confirmation: confirm status codes and business assertions

### Steps

1. `apiClient` GET `env.api('/quality-gates' )`

### Expected

- response has documented JSON shape

## case-782734cd5b8ee7a1 - GET /requirements - 请求可达性
- status: `AUTOMATABLE`; risk: `readonly`; type: `api`
- environments: `production-like, isolated`
- evidence: `ev-8c7d90d6afb1431a`
- human confirmation: confirm status codes and business assertions

### Steps

1. `apiClient` GET `env.api('/requirements' )`

### Expected


## case-a78614f358a0ef50 - GET /jobs - 请求可达性
- status: `AUTOMATABLE`; risk: `readonly`; type: `api`
- environments: `production-like, isolated`
- evidence: `ev-9addfda6eee469b3`
- human confirmation: confirm status codes and business assertions

### Steps

1. `apiClient` GET `env.api('/jobs' )`

### Expected


## case-a78674fb8a051ebc - GET /sdd/projects - 请求可达性
- status: `AUTOMATABLE`; risk: `readonly`; type: `api`
- environments: `production-like, isolated`
- evidence: `ev-2d5a3f43a22be600`
- human confirmation: confirm status codes and business assertions

### Steps

1. `apiClient` GET `env.api('/sdd/projects' )`

### Expected


## case-b270af6c9f9045b1 - GET /jobs - 未认证访问
- status: `DRAFT`; risk: `readonly`; type: `api`
- environments: `production-like, isolated`
- evidence: `ev-9addfda6eee469b3`
- human confirmation: confirm status codes and business assertions

### Steps

1. `anonClient` GET `env.api('/jobs' )`

### Expected

- documented unauthenticated status

## case-b634315b5eb413e9 - GET /requirements - 响应结构
- status: `DRAFT`; risk: `readonly`; type: `api`
- environments: `production-like, isolated`
- evidence: `ev-8c7d90d6afb1431a`
- human confirmation: confirm status codes and business assertions

### Steps

1. `apiClient` GET `env.api('/requirements' )`

### Expected

- response has documented JSON shape

## case-b8aba3871053aba9 - GET /auth/login - 未认证访问
- status: `DRAFT`; risk: `readonly`; type: `api`
- environments: `production-like, isolated`
- evidence: `ev-a9fd77c8d51d65ea`
- human confirmation: 已有测试覆盖，默认不重复生成; confirm status codes and business assertions

### Steps

1. `anonClient` GET `env.api('/auth/login' )`

### Expected

- documented unauthenticated status

## case-bc68765704d8ad6e - GET /sdd/projects - 响应结构
- status: `DRAFT`; risk: `readonly`; type: `api`
- environments: `production-like, isolated`
- evidence: `ev-2d5a3f43a22be600`
- human confirmation: confirm status codes and business assertions

### Steps

1. `apiClient` GET `env.api('/sdd/projects' )`

### Expected

- response has documented JSON shape

## case-bde01c25915aefc6 - GET /jobs - 响应结构
- status: `DRAFT`; risk: `readonly`; type: `api`
- environments: `production-like, isolated`
- evidence: `ev-9addfda6eee469b3`
- human confirmation: confirm status codes and business assertions

### Steps

1. `apiClient` GET `env.api('/jobs' )`

### Expected

- response has documented JSON shape

## case-c7a8549bfd175221 - GET /sdd/projects - 未认证访问
- status: `DRAFT`; risk: `readonly`; type: `api`
- environments: `production-like, isolated`
- evidence: `ev-2d5a3f43a22be600`
- human confirmation: confirm status codes and business assertions

### Steps

1. `anonClient` GET `env.api('/sdd/projects' )`

### Expected

- documented unauthenticated status

## case-c9b340ce3f9378c7 - GET /auth/login - 响应结构
- status: `DRAFT`; risk: `readonly`; type: `api`
- environments: `production-like, isolated`
- evidence: `ev-a9fd77c8d51d65ea`
- human confirmation: 已有测试覆盖，默认不重复生成; confirm status codes and business assertions

### Steps

1. `apiClient` GET `env.api('/auth/login' )`

### Expected

- response has documented JSON shape

## case-dd47a874c57157e9 - GET /requirements - 未认证访问
- status: `DRAFT`; risk: `readonly`; type: `api`
- environments: `production-like, isolated`
- evidence: `ev-8c7d90d6afb1431a`
- human confirmation: confirm status codes and business assertions

### Steps

1. `anonClient` GET `env.api('/requirements' )`

### Expected

- documented unauthenticated status

## case-ddb9838ceecdfcc4 - GET /auth/login - 请求可达性
- status: `DRAFT`; risk: `readonly`; type: `api`
- environments: `production-like, isolated`
- evidence: `ev-a9fd77c8d51d65ea`
- human confirmation: 已有测试覆盖，默认不重复生成; confirm status codes and business assertions

### Steps

1. `apiClient` GET `env.api('/auth/login' )`

### Expected


## case-f3b6ad7863c0579f - GET /auth/session - 响应结构
- status: `DRAFT`; risk: `readonly`; type: `api`
- environments: `production-like, isolated`
- evidence: `ev-6066b704592cb178`
- human confirmation: confirm status codes and business assertions

### Steps

1. `apiClient` GET `env.api('/auth/session' )`

### Expected

- response has documented JSON shape

## case-faf13d825519bff1 - GET /quality-gates - 未认证访问
- status: `DRAFT`; risk: `readonly`; type: `api`
- environments: `production-like, isolated`
- evidence: `ev-aeaf63539eabc42d`
- human confirmation: confirm status codes and business assertions

### Steps

1. `anonClient` GET `env.api('/quality-gates' )`

### Expected

- documented unauthenticated status
