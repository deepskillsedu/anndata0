import requests
from requests.auth import HTTPBasicAuth
from app.history_service import save_actual_override
from app.ditto_reader import get_virtual, get_actual, thing_exists

DITTO_BASE_URL = "http://localhost:8080/api/2/things"
DITTO_POLICIES_URL = "http://localhost:8080/api/2/policies"
AUTH = HTTPBasicAuth("ditto", "ditto")
MERGE_HEADERS = {"Content-Type": "application/merge-patch+json"}

# The subject granted READ/WRITE on every thing/policy this app creates.
# This MUST match whatever your Ditto deployment treats as "you" on a
# request authenticated with AUTH above.
#   - nginx basic-auth in front of Ditto (the common quickstart setup,
#     matching the `ditto`/`ditto` HTTPBasicAuth above) -> "nginx:ditto"
#   - Ditto's own built-in devops/basic auth                -> "ditto:ditto"
#   - a pre-authenticated header from a different proxy name -> "<that proxy>:<subject>"
# If things get created but every later read/write to them comes back
# 403, this is almost always the mismatch to check first.
POLICY_SUBJECT = "nginx:ditto"


def _build_policy(thing_id: str) -> dict:
    """
    The actual Ditto policy document for one thing — created via a real
    PUT to /api/2/policies/{thing_id}, NOT embedded inside the thing
    payload (Ditto's things API has no "_policy" field; that was never
    read by Ditto, so things created the old way could end up with a
    policyId pointing at a policy that was never actually created).
    """
    return {
        "entries": {
            "owner": {
                "subjects": {
                    POLICY_SUBJECT: {
                        "type": "nginx basic auth user"
                    }
                },
                "resources": {
                    "thing:/": {"grant": ["READ", "WRITE"], "revoke": []},
                    "policy:/": {"grant": ["READ", "WRITE"], "revoke": []},
                    "message:/": {"grant": ["READ", "WRITE"], "revoke": []}
                }
            }
        }
    }


def create_policy(thing_id: str):
    """
    Create (or replace) the policy for a thing at its real endpoint.
    Idempotent — PUT replaces whatever's there, so calling this again
    for an existing thing_id just re-asserts the same access rules
    rather than erroring.

    Does NOT assume the response has a JSON body. raise_for_status()
    already confirms the call succeeded (a non-2xx raises immediately,
    well before this point) — calling .json() afterwards was only ever
    for a debug return value, and crashed outright whenever Ditto
    returned a success status with an empty body (a real, observed case:
    some Ditto deployments respond 201/204 to a policy PUT with no body
    at all). That crash was happening AFTER the policy had already been
    created successfully — so farm creation was failing on a logging
    statement, not on the actual policy write.
    """
    response = requests.put(
        f"{DITTO_POLICIES_URL}/{thing_id}",
        auth=AUTH,
        json=_build_policy(thing_id)
    )
    response.raise_for_status()
    if response.text.strip():
        try:
            return response.json()
        except ValueError:
            pass
    return {"status": "success", "thing_id": thing_id}


def create_thing(thing_id: str, name: str, field: str = None, crop: str = None):
    """
    Create a farm thing in Ditto, with a real policy backing it.

    Two-step, in the order Ditto actually requires: the policy has to
    exist before (or in the very same call as) the thing references it
    via policyId, otherwise the thing PUT is rejected. We create the
    policy explicitly first so failures here are loud and attributable,
    rather than silently producing a thing with a dangling policyId.
    """
    create_policy(thing_id)

    payload = {
        "policyId": thing_id,
        "attributes": {
            "name": name,
            "field": field,
            "crop": crop
        },
        "features": {
            "actual": {"properties": {}},
            "virtual": {"properties": {}},
            "scenarios": {"properties": {}}
        }
    }
    response = requests.put(
        f"{DITTO_BASE_URL}/{thing_id}",
        auth=AUTH,
        json=payload
    )
    response.raise_for_status()
    if response.text.strip():
        try:
            return response.json()
        except ValueError:
            pass
    return {"status": "success", "thing_id": thing_id}


def delete_thing(thing_id: str):
    response = requests.delete(f"{DITTO_BASE_URL}/{thing_id}", auth=AUTH)
    if response.status_code != 404:
        response.raise_for_status()

    policy_response = requests.delete(f"{DITTO_POLICIES_URL}/{thing_id}", auth=AUTH)
    if policy_response.status_code != 404:
        policy_response.raise_for_status()

    return {"status": "success", "thing_id": thing_id}


class FarmNotFoundError(Exception):
    """Raised when a write targets a farm thing that doesn't exist in
    Ditto. There is no auto-create fallback anymore — a farm only ever
    comes into existence through POST /farms (create_thing, with the
    name the user actually typed), never as a side effect of some other
    write silently materializing a stand-in with a placeholder name.
    That auto-create was the actual cause of farm names getting
    silently overwritten: a write that fired moments after farm
    creation could (under Ditto's eventual-consistency window) see the
    thing as "not yet existing" and recreate it with thing_id as the
    name, wiping out what the user typed.
    """
    pass


def require_thing(thing_id: str):
    """Confirm a thing genuinely exists before writing to it. Raises
    FarmNotFoundError instead of silently creating a placeholder — if
    no farm exists yet, no farm should be written to or shown, full
    stop, until one is actually created via POST /farms."""
    if not thing_exists(thing_id):
        raise FarmNotFoundError(f"{thing_id} does not exist — create the farm first via POST /farms")


def update_virtual_properties(properties: dict, thing_id: str):
    require_thing(thing_id)
    current = get_virtual(thing_id)
    response = requests.patch(
        f"{DITTO_BASE_URL}/{thing_id}/features/virtual/properties",
        auth=AUTH,
        json=properties,
        headers=MERGE_HEADERS
    )
    response.raise_for_status()
    changes = {}
    for name, value in properties.items():
        old_value = current.get(name)
        changes[name] = {"oldValue": old_value, "value": value}
    return {"status": "success", "changes": changes}


def update_actual_properties(properties: dict, thing_id: str):
    require_thing(thing_id)
    current = get_actual(thing_id)
    response = requests.patch(
        f"{DITTO_BASE_URL}/{thing_id}/features/actual/properties",
        auth=AUTH,
        json=properties,
        headers=MERGE_HEADERS
    )
    response.raise_for_status()
    changes = {}
    for name, value in properties.items():
        old_value = current.get(name)
        save_actual_override(name, old_value, value, thing_id=thing_id)
        changes[name] = {"oldValue": old_value, "value": value}
    return {"status": "success", "changes": changes}


def save_scenarios(scenarios: dict, thing_id: str):
    require_thing(thing_id)
    response = requests.put(
        f"{DITTO_BASE_URL}/{thing_id}/features/scenarios/properties",
        auth=AUTH,
        json=scenarios
    )
    response.raise_for_status()
    return {"status": "success", "scenarioCount": len(scenarios)}