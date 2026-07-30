import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = (ROOT / "WebMap" / "MapDataServer.cs").read_text(encoding="utf-8")
WEBMAP = (ROOT / "WebMap" / "WebMap.cs").read_text(encoding="utf-8")


def method_body(source, signature):
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[brace + 1:index]
    raise AssertionError(f"unterminated method: {signature}")


def constant(source, name):
    match = re.search(rf"const int {name}\s*=\s*(\d+);", source)
    assert match is not None, name
    return int(match.group(1))


class IdentityContractModel:
    """Executable specification for retained-owner identity behavior."""

    def __init__(self, maximum):
        self.maximum = maximum
        self.identities = {}
        self.used_ids = set()
        self.next_id = 1
        self.next_alias = 1

    def reconcile(self, retained_owners):
        for owner in set(self.identities) - set(retained_owners):
            identity = self.identities.pop(owner)
            self.used_ids.remove(identity[0])

    def try_for_owner(self, owner):
        if owner in self.identities:
            return self.identities[owner]
        if len(self.identities) >= self.maximum:
            return None
        identity = (self.next_id, f"Player {self.next_alias}")
        self.next_id += 1
        self.next_alias += 1
        self.identities[owner] = identity
        self.used_ids.add(identity[0])
        return identity

    def replace(self, records):
        accepted = []
        for owner, valid in records:
            if len(accepted) >= self.maximum:
                break
            if valid:
                accepted.append(owner)
        self.reconcile(set(accepted))
        return [(owner, self.try_for_owner(owner)) for owner in accepted]


def test_retained_owner_identity_survives_replacement_while_removed_owners_are_pruned():
    identities = IdentityContractModel(4)
    anchor = identities.try_for_owner("anchor")
    removed = identities.try_for_owner("removed")

    serialized = identities.replace([("anchor", True), ("new", True)])

    assert dict(serialized)["anchor"] == anchor
    assert "removed" not in identities.identities
    assert removed[0] not in identities.used_ids
    assert identities.try_for_owner("new") == dict(serialized)["new"]


def test_more_than_lifetime_cap_churn_cannot_block_new_retained_owners():
    maximum = 32
    identities = IdentityContractModel(maximum)
    anchor = identities.try_for_owner("anchor")

    for index in range(maximum + 17):
        current = f"owner-{index}"
        serialized = identities.replace([("anchor", True), (current, True)])
        assert len(identities.identities) == 2
        assert len(identities.used_ids) == 2
        assert dict(serialized)["anchor"] == anchor
        assert dict(serialized)[current] is not None

    identities.reconcile(set())
    assert identities.identities == {}
    assert identities.used_ids == set()
    assert identities.try_for_owner("after-churn") is not None


def test_replacement_accepts_the_full_cap_and_invalid_or_overflow_rows_consume_no_identities():
    maximum = 32
    identities = IdentityContractModel(maximum)
    records = [("invalid-before", False)]
    records += [(f"owner-{index}", True) for index in range(maximum)]
    records += [("overflow", True), ("invalid-after", False)]

    serialized = identities.replace(records)

    assert len(serialized) == maximum
    assert len(identities.identities) == maximum
    assert len(identities.used_ids) == maximum
    assert "invalid-before" not in identities.identities
    assert "invalid-after" not in identities.identities
    assert "overflow" not in identities.identities


def test_source_prunes_both_identity_dictionaries_without_resetting_active_mappings():
    assert "internal static void ReconcileOwners" in SERVER
    reconcile = method_body(SERVER, "internal static void ReconcileOwners")
    assert "lock (Sync)" in reconcile
    assert "retainedOwners.Contains" in reconcile
    assert "Identities.Remove" in reconcile
    assert "UsedIds.Remove" in reconcile
    assert "Identities.Clear()" not in reconcile
    assert "UsedIds.Clear()" not in reconcile
    assert "nextAlias = 1" not in reconcile


def test_source_reconciles_each_mutation_and_prevents_stale_snapshot_reallocation():
    retained = method_body(SERVER, "private HashSet<string> GetRetainedOwnersLocked")
    assert "privatePins" in retained and "TryGetPinOwner" in retained
    assert "owners.Add" in retained

    replace = method_body(SERVER, "public void ReplacePins")
    assert replace.index("privatePins.Add") < replace.index("PublicIdentity.ReconcileOwners")

    remove = method_body(SERVER, "public void RemovePin")
    assert remove.index("privatePins.RemoveAt") < remove.index("PublicIdentity.ReconcileOwners")

    publish = method_body(SERVER, "private void PublishPinSnapshot")
    assert "lock (pinSync)" in publish
    assert "source = privatePins.ToArray()" not in publish
    assert "foreach (string pin in privatePins)" in publish


def test_add_pin_fails_at_pin_cap_before_reconciliation_or_identity_allocation():
    add = method_body(SERVER, "public void AddPin")
    cap_check = add.index("privatePins.Count >= MaxPrivatePins")
    reconcile = add.index("PublicIdentity.ReconcileOwners")
    allocation = add.index("PublicIdentity.TryForOwner")
    insertion = add.index("privatePins.Add(record)")
    assert cap_check < reconcile < allocation < insertion


def test_add_live_broadcast_cannot_reallocate_after_the_pin_lock_is_released():
    add = method_body(SERVER, "public void AddPin")
    assert add.count("PublicIdentity.TryForOwner") == 1
    assert "TrySerializePublicPin(record" not in add
    assert "SerializePublicPin(parsed, identity)" in add


def test_replace_inspection_and_file_ingestion_are_bounded_before_validation():
    replace = method_body(SERVER, "public void ReplacePins")
    assert "int inspected = 0;" in replace
    assert "if (inspected++ >= MaxPrivatePins) break;" in replace
    assert replace.index("inspected++") < replace.index("TryParsePrivatePin")
    assert "File.ReadLines(" in WEBMAP
    assert "File.ReadAllLines(" not in WEBMAP


def test_identity_capacity_tracks_current_valid_retained_pin_owners():
    assert constant(SERVER, "MaxPublicIdentities") == constant(SERVER, "MaxPrivatePins")
    replace = method_body(SERVER, "public void ReplacePins")
    assert "TryParsePrivatePin" in replace
    assert replace.index("TryParsePrivatePin") < replace.index("privatePins.Add")
    assert "privatePins.Count >= MaxPrivatePins" in replace
    serializer = method_body(SERVER, "private void PublishPinSnapshot")
    assert "TrySerializePublicPin" in serializer
