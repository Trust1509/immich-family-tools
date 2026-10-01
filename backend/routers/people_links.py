"""Explicit cross-account identity links.

Links only describe equivalence between Immich face profiles.  Creating one
never mutates or renames a person in Immich.
"""
from fastapi import APIRouter, Request

import errors
from models.match import LinkedPerson, LinkedPersonCreate

router = APIRouter(prefix="/api/person-links", tags=["person-links"])


@router.get("", response_model=list[LinkedPerson])
async def list_person_links(request: Request):
    return request.app.state.store.get_linked_people()


@router.post("", response_model=LinkedPerson, status_code=201)
async def create_person_link(body: LinkedPersonCreate, request: Request):
    refs = list(dict.fromkeys((entry.account_id, entry.person_id) for entry in body.persons))
    if len({account_id for account_id, _ in refs}) < 2:
        raise errors.linked_person_min_accounts()
    if len({account_id for account_id, _ in refs}) != len(refs):
        raise errors.linked_person_one_per_account()

    store = request.app.state.store
    validated = []
    for account_id, person_id in refs:
        account = store.get_account(account_id)
        if not account:
            raise errors.account_id_not_found(account_id)
        try:
            person = await request.app.state.client_pool.get_for_account(account).get_person(person_id)
        except Exception:
            raise errors.person_validation_failed(account.name)
        validated.append((account_id, person_id, person.get("name") or ""))

    display_name = (body.display_name or "").strip()
    if not display_name:
        display_name = next((name for _, _, name in validated if name), "Linked person")
    person_refs = [{
        "account_id": account_id,
        "person_id": person_id,
        "person_name": name,
        "account_name": store.get_account(account_id).name,
        "account_color": store.get_account(account_id).color,
    } for account_id, person_id, name in validated]
    if store.linked_person_conflicts(person_refs):
        raise errors.linked_person_conflict()
    return store.ensure_linked_person(display_name, person_refs)


@router.delete("/{linked_person_id}", status_code=204)
async def delete_person_link(linked_person_id: str, request: Request):
    store = request.app.state.store
    if not store.get_linked_person(linked_person_id):
        raise errors.linked_person_not_found()
    store.delete_linked_person(linked_person_id)
