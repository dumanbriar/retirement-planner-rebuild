#!/usr/bin/env python3
"""Deploy backend/ to Railway using a team/workspace token.

The Railway CLI's `link`/`init` flows require a personal token, but the
GraphQL API accepts team tokens directly. So: find-or-create the project,
service and domain via GraphQL, then hand the explicit IDs to `railway up`
for the code upload (CLI accepts IDs without a linked project).

Idempotent: safe to run on every push.
"""
import json
import os
import subprocess
import sys
import urllib.request

TOKEN = os.environ["RAILWAY_DEPLOY_TOKEN"]
ENDPOINT = os.environ.get("RAILWAY_ENDPOINT", "https://backboard.railway.com/graphql/v2")
PROJECT_NAME = os.environ.get("RAILWAY_PROJECT_NAME", "horizon-retirement-engine")
SERVICE_NAME = os.environ.get("RAILWAY_SERVICE_NAME", "backend")


def gql(query: str, variables: dict | None = None) -> dict:
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        ENDPOINT, data=body, method="POST",
        headers={"Authorization": f"Bearer {TOKEN}",
                 "Content-Type": "application/json",
                 # Railway's edge rejects the default Python-urllib UA
                 "User-Agent": "curl/8.5.0"})
    try:
        with urllib.request.urlopen(req) as r:
            out = json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} for query {query[:80]!r}: {e.read().decode(errors='replace')[:500]}")
        return {}
    if out.get("errors"):
        print(f"GraphQL errors for query {query[:80]!r}:", json.dumps(out["errors"], indent=1))
    return out


def introspect_input(type_name: str) -> None:
    """Print an input type's fields — emitted on failure to make the next
    debugging round deterministic."""
    q = """query($n:String!){ __type(name:$n){ name inputFields { name type
           { name kind ofType { name kind } } } } }"""
    print(f"introspection of {type_name}:",
          json.dumps(gql(q, {"n": type_name}).get("data"), indent=1))


def die(msg: str) -> None:
    print(f"::error::{msg}")
    sys.exit(1)


# ---- 1. find or create the project --------------------------------------
out = gql("query { projects { edges { node { id name environments "
          "{ edges { node { id name } } } } } } }")
projects = [e["node"] for e in (out.get("data") or {}).get("projects", {}).get("edges", [])]
print("existing projects:", [(p["id"], p["name"]) for p in projects])
project = next((p for p in projects if p["name"] == PROJECT_NAME), None)
if project is None:
    out = gql("mutation($name:String!){ projectCreate(input:{name:$name}) "
              "{ id name environments { edges { node { id name } } } } }",
              {"name": PROJECT_NAME})
    project = (out.get("data") or {}).get("projectCreate")
    if not project:
        introspect_input("ProjectCreateInput")
        die("projectCreate failed; see errors and introspection above")
    print("created project:", project["id"])
envs = [e["node"] for e in project["environments"]["edges"]]
env = next((e for e in envs if e["name"] == "production"), envs[0] if envs else None)
if env is None:
    die("no environment found on the project")
print("project:", project["id"], "environment:", env["id"], env["name"])

# ---- 2. find or create the service --------------------------------------
out = gql("query($id:String!){ project(id:$id){ services { edges { node "
          "{ id name } } } } }", {"id": project["id"]})
services = [e["node"] for e in (out.get("data") or {}).get("project", {})
            .get("services", {}).get("edges", [])]
print("existing services:", services)
service = next((s for s in services if s["name"] == SERVICE_NAME), None)
if service is None:
    out = gql("mutation($p:String!,$n:String!){ serviceCreate(input:"
              "{projectId:$p,name:$n}) { id name } }",
              {"p": project["id"], "n": SERVICE_NAME})
    service = (out.get("data") or {}).get("serviceCreate")
    if not service:
        introspect_input("ServiceCreateInput")
        die("serviceCreate failed; see errors and introspection above")
    print("created service:", service["id"])
print("service:", service["id"])

# ---- 3. upload & deploy the code via the CLI with explicit IDs ----------
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
env_vars = dict(os.environ, RAILWAY_API_TOKEN=TOKEN, CI="true")
cmd = ["railway", "up", "-p", project["id"], "-e", env["id"],
       "-s", service["id"], "-c", "--verbose"]
print("running:", " ".join(cmd))
proc = subprocess.run(cmd, cwd=backend_dir, env=env_vars)
if proc.returncode != 0:
    die(f"railway up exited with {proc.returncode}")

# ---- 4. find or create the public domain --------------------------------
out = gql("query($e:String!,$s:String!){ domains(environmentId:$e, serviceId:$s) "
          "{ serviceDomains { domain } customDomains { domain } } }",
          {"e": env["id"], "s": service["id"]})
domains = (out.get("data") or {}).get("domains") or {}
existing = [d["domain"] for d in (domains.get("serviceDomains") or [])]
if not existing:
    out = gql("mutation($e:String!,$s:String!){ serviceDomainCreate(input:"
              "{environmentId:$e, serviceId:$s}) { domain } }",
              {"e": env["id"], "s": service["id"]})
    created = (out.get("data") or {}).get("serviceDomainCreate")
    if not created:
        introspect_input("ServiceDomainCreateInput")
        die("serviceDomainCreate failed; see errors and introspection above")
    existing = [created["domain"]]
url = f"https://{existing[0]}"
print("Backend URL:", url)
gh_out = os.environ.get("GITHUB_OUTPUT")
if gh_out:
    with open(gh_out, "a") as f:
        f.write(f"backend_url={url}\n")
